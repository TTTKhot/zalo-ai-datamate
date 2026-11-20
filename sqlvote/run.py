"""Command line + per-shop runner.

  python -m sqlvote.run ingest  --split DIR [--cache DIR] [--show biz_xxx]
  python -m sqlvote.run predict --split DIR --out DIR --base-url http://127.0.0.1:8000/v1 --model NAME
                                [--answers answers.jsonl] [--bank bank.jsonl] [--save-bank bank.jsonl] ...
  python -m sqlvote.run score   --answers answers.jsonl --submission submission.jsonl
  python -m sqlvote.run calib   --logs OUT/logs
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .bank import Bank
from .clean import load_or_build
from .dates import date_facts, load_calendar
from .engine import ShopDB, check_sql, is_zero, parse_reply, to_answer, vote
from .prompt import build_messages, repair_messages, shop_prefix
from .schema import ValueIndex, schema_text
from .scorer import is_correct, read_jsonl, score


@dataclass
class Config:
    k: int = 8                         # drafts per question (1 greedy + k-1 sampled)
    temperature: float = 0.7
    threshold: float = 0.5             # answer when the winning group has at least this share of ALL drafts
    unans_threshold: float = 0.5
    zero_threshold: float = 1.01       # > 1 = never answer 0 / empty (4 of 2462 numeric gold answers in train are 0)
    shots: int = 4
    max_tokens: int = 700
    repairs: int = 2                   # failed drafts that get one repair turn
    sql_timeout: float = 20.0
    workers: int = 8
    variants: tuple = ('A', 'B')
    allow_same_shop: bool = False      # few-shot examples from the shop being answered (leaks on train)
    time_budget: float = 0.0           # seconds; 0 = no limit. Past it, remaining questions are abstained
    extra: dict = field(default_factory=dict)


def seed_of(question: str, as_of: str) -> int:
    return zlib.crc32(f'{question}|{as_of}'.encode('utf-8')) & 0x7FFFFFFF


def submission_line(qid: str, decision: dict) -> dict:
    if decision['decision'] == 'answer':
        return {'id': qid, 'type': decision['type'], 'answer': decision['answer']}
    if decision['decision'] == 'unanswerable':
        return {'id': qid, 'type': 'unanswerable', 'reason': str(decision.get('reason') or '')}
    return {'id': qid, 'type': 'abstain'}


class ShopRunner:
    def __init__(self, shop_dir, shop_id: str, cache_dir, rulebook: str, calendar: dict, backend, cfg: Config,
                 bank: Bank | None = None, extra_tables=None, rebuild: bool = False):
        self.shop_id, self.cal, self.backend, self.cfg, self.bank = shop_id, calendar, backend, cfg, bank
        db_path = Path(cache_dir) / f'{shop_id}.duckdb'
        self.meta = load_or_build(shop_dir, db_path, extra_tables, rebuild)
        self.db = ShopDB(str(db_path))
        self.schema = schema_text(self.meta)
        self.prefix = shop_prefix(rulebook, self.meta, self.schema)
        self.values = ValueIndex(self.meta)
        self.data_start = dt.date.fromisoformat(self.meta['data_start']) if self.meta.get('data_start') else None
        self.data_end = dt.date.fromisoformat(self.meta['data_end']) if self.meta.get('data_end') else None

    def close(self):
        self.db.close()

    # one model reply -> one sample
    def evaluate(self, raw: str) -> dict:
        r = parse_reply(raw)
        s = {'raw': raw, 'type': r['type'], 'sql': r['sql'], 'note': r['note'], 'reason': r['reason'],
             'period': [d.isoformat() for d in r['period']] if r['period'] else None,
             'status': 'error', 'error': None, 'answer': None}
        if r['type'] is None:
            s['error'] = 'thiếu dòng TYPE hợp lệ'
        elif r['type'] == 'unanswerable':
            s['status'] = 'unanswerable'
        else:
            problem = check_sql(r['sql'])
            if problem:
                s['error'] = problem
            else:
                try:
                    cols, rows = self.db.run(r['sql'], self.cfg.sql_timeout)
                    status, answer = to_answer(cols, rows, r['type'])
                    s['status'], s['answer'] = status, answer
                    if status == 'shape':
                        s['error'] = (f'kết quả có {len(rows)} dòng x {len(cols)} cột, không hợp với TYPE {r["type"]} '
                                      f'(hoặc giá trị sai kiểu)')
                except Exception as exc:
                    s['error'] = f'{type(exc).__name__}: {str(exc)[:400]}'
        # rulebook "không trả lời được": the asked period lies wholly outside the shop's data. Applied in code only
        # when the draft has no usable non-zero result, so a mis-stated PERIOD cannot erase a real answer.
        if r['period'] and r['type'] != 'unanswerable' and (self.data_start or self.data_end):
            start, end = r['period']
            outside = (self.data_start and end < self.data_start) or (self.data_end and start > self.data_end)
            weak = s['status'] != 'ok' or is_zero(s['type'], s['answer'])
            if outside and weak:
                s.update(status='unanswerable', gated=True,
                         reason='Kỳ hỏi nằm hoàn toàn ngoài khoảng ngày có dữ liệu của shop')
        return s

    def answer(self, q: dict, gold: dict | None = None) -> dict:
        cfg, started = self.cfg, time.time()
        qid, question, as_of = q['id'], q['question'], str(q.get('as_of_date') or '')[:10]
        rec = {'id': qid, 'business_id': self.shop_id, 'question': question, 'as_of_date': as_of, 'samples': []}
        try:
            facts = date_facts(as_of, self.cal) if as_of else '(không có as_of_date)'
            matches = self.values.match(question)
            exclude = () if cfg.allow_same_shop else (self.shop_id,)
            shots = self.bank.retrieve(question, cfg.shots, exclude, (qid,)) if self.bank else []
            rec['shots'] = [s.get('id') for s in shots]
            rec['matches'] = matches
            msgs = {v: build_messages(self.prefix, question, as_of, facts, matches, shots, v) for v in cfg.variants}
            seed = seed_of(question, as_of)
            plan = [(cfg.variants[0], 1, 0.0)]
            left = cfg.k - 1
            for i, v in enumerate(cfg.variants):
                n = left // len(cfg.variants) + (1 if i < left % len(cfg.variants) else 0)
                if n:
                    plan.append((v, n, cfg.temperature))
            for j, (variant, n, temp) in enumerate(plan):
                try:
                    raws = self.backend.generate(msgs[variant], n=n, temperature=temp, seed=seed + j,
                                                 max_tokens=cfg.max_tokens)
                except Exception as exc:               # e.g. GPU OOM on one draft: keep the drafts we already have
                    rec.setdefault('gen_errors', []).append(f'{type(exc).__name__}: {str(exc)[:200]}')
                    if not rec['samples'] and j == len(plan) - 1:
                        raise
                    continue
                for raw in raws:
                    s = self.evaluate(raw)
                    s.update(variant=variant, temperature=temp)
                    rec['samples'].append(s)
            repaired = 0
            for i, s in enumerate(rec['samples']):
                if repaired >= cfg.repairs:
                    break
                if s['status'] == 'error' and s.get('error'):
                    repaired += 1
                    raw = self.backend.generate(repair_messages(msgs[s['variant']], s['raw'], s['error']), n=1,
                                                temperature=0.0, seed=seed, max_tokens=cfg.max_tokens)[0]
                    fixed = self.evaluate(raw)
                    if fixed['status'] in ('ok', 'unanswerable'):
                        fixed.update(variant=s['variant'], temperature=s['temperature'], repaired=True,
                                     first_error=s['error'])
                        rec['samples'][i] = fixed
            decision = vote(rec['samples'], cfg.threshold, cfg.unans_threshold, cfg.zero_threshold)
        except Exception as exc:                       # never crash the run: an unanswered question is an abstain
            rec['error'] = f'{type(exc).__name__}: {str(exc)[:400]}'
            decision = {'decision': 'abstain', 'confidence': 0.0, 'type': None, 'answer': None, 'reason': None,
                        'n_samples': len(rec['samples']), 'n_valid': 0, 'n_groups': 0}
        rec['vote'] = decision
        rec['submission'] = submission_line(qid, decision)
        if gold is not None:
            for s in rec['samples']:
                s['correct'] = (s['status'] == 'unanswerable') if gold['type'] == 'unanswerable' else \
                    (s['status'] == 'ok' and is_correct({'type': s['type'], 'answer': s['answer']}, gold))
            top = {'type': decision['type'], 'answer': decision['answer']} if decision['type'] else None
            rec['gold'] = {'type': gold['type'], 'answer': gold.get('answer')}
            rec['top_correct'] = bool(top) and is_correct(top, gold)
            sub = rec['submission']
            rec['verdict'] = 'abstain' if sub['type'] == 'abstain' else ('correct' if is_correct(sub, gold) else 'wrong')
        rec['elapsed'] = round(time.time() - started, 3)
        return rec


def bank_entry(rec: dict) -> dict | None:
    """First draft that reproduced the gold answer -> a verified few-shot / SFT example."""
    for s in rec['samples']:
        if s.get('correct') and (s['status'] == 'unanswerable' or s.get('sql')):
            return {'id': rec['id'], 'shop': rec['business_id'], 'question': rec['question'], 'as_of': rec['as_of_date'],
                    'type': 'unanswerable' if s['status'] == 'unanswerable' else s['type'], 'note': s.get('note'),
                    'period': '..'.join(s['period']) if s.get('period') else None, 'sql': s.get('sql'),
                    'reason': s.get('reason')}
    return None


def predict(split_dir, out_dir, backend, cfg: Config, cache_dir=None, bank: Bank | None = None, answers=None,
            shops=None, limit_per_shop: int = 0, save_bank=None, extra_tables_fn=None, resume: bool = True,
            rebuild: bool = False, log=print, questions_path=None) -> dict:
    """Answer every question of a split. extra_tables_fn(shop_dir, shop_id) may add canonical tables per shop.
    questions_path: another questions file (e.g. the val subset another pipeline was scored on)."""
    split_dir, out_dir = Path(split_dir), Path(out_dir)
    cache_dir = Path(cache_dir) if cache_dir else out_dir / 'cache'
    (out_dir / 'logs').mkdir(parents=True, exist_ok=True)
    started = time.time()
    questions = read_jsonl(questions_path or split_dir / 'questions.jsonl')
    rulebook_path = split_dir / 'rulebook.md'
    rulebook = rulebook_path.read_text(encoding='utf-8-sig') if rulebook_path.exists() else ''
    calendar = load_calendar(split_dir / 'calendar.csv')
    golds = {g['id']: g for g in (read_jsonl(answers) if answers else [])}
    by_shop: dict = {}
    for q in questions:
        by_shop.setdefault(q['business_id'], []).append(q)
    lines: dict = {}
    sub_path = out_dir / 'submission.jsonl'

    def flush():
        tmp = sub_path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as fh:
            for q in questions:
                if q['id'] in lines:
                    fh.write(json.dumps(lines[q['id']], ensure_ascii=False) + '\n')
        tmp.replace(sub_path)

    bank_fh = Path(save_bank).open('a', encoding='utf-8') if save_bank else None
    for shop_id, qs in by_shop.items():
        if shops and shop_id not in shops:
            continue
        if limit_per_shop:
            qs = qs[:limit_per_shop]
        log_dir = out_dir / 'logs' / shop_id
        log_dir.mkdir(parents=True, exist_ok=True)
        todo = []
        for q in qs:
            path = log_dir / f'{q["id"]}.json'
            if resume and path.exists():
                try:
                    lines[q['id']] = json.loads(path.read_text(encoding='utf-8'))['submission']
                    continue
                except Exception:
                    pass
            todo.append(q)
        if not todo:
            continue
        if cfg.time_budget and time.time() - started > cfg.time_budget:
            for q in todo:
                lines[q['id']] = {'id': q['id'], 'type': 'abstain'}
            continue
        t0 = time.time()
        try:
            extra = extra_tables_fn(split_dir / 'data' / shop_id, shop_id) if extra_tables_fn else None
            runner = ShopRunner(split_dir / 'data' / shop_id, shop_id, cache_dir, rulebook, calendar, backend, cfg,
                                bank, extra, rebuild)
        except Exception as exc:
            log(f'[{shop_id}] cannot load shop: {type(exc).__name__}: {exc}')
            for q in todo:
                lines[q['id']] = {'id': q['id'], 'type': 'abstain'}
            flush()
            continue

        def work(q):
            if cfg.time_budget and time.time() - started > cfg.time_budget:
                return {'id': q['id'], 'business_id': shop_id, 'question': q['question'], 'samples': [],
                        'submission': {'id': q['id'], 'type': 'abstain'}, 'error': 'time budget', 'elapsed': 0.0}
            return runner.answer(q, golds.get(q['id']))

        tally = {'correct': 0, 'wrong': 0, 'abstain': 0}
        with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
            for rec in pool.map(work, todo):
                (log_dir / f'{rec["id"]}.json').write_text(json.dumps(rec, ensure_ascii=False, default=str),
                                                           encoding='utf-8')
                lines[rec['id']] = rec['submission']
                if 'verdict' in rec:
                    tally[rec['verdict']] += 1
                    entry = bank_entry(rec) if bank_fh else None
                    if entry:
                        bank_fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
                        bank_fh.flush()
        runner.close()
        flush()
        note = f' | +{tally["correct"]} -{tally["wrong"]} ~{tally["abstain"]}' if golds else ''
        log(f'[{shop_id}] {len(todo)} câu, {time.time() - t0:.0f}s{note}')
    if bank_fh:
        bank_fh.close()
    flush()
    result = {'questions': len(lines), 'seconds': round(time.time() - started, 1)}
    if golds:
        result['score'] = score(list(lines.values()), [golds[i] for i in lines if i in golds])
    return result


# ---------------------------------------------------------------- calibration table
def calibration(log_dir) -> str:
    recs = []
    for path in Path(log_dir).rglob('*.json'):
        try:
            rec = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if 'gold' in rec:
            recs.append(rec)
    if not recs:
        return 'Không có log nào có đáp án (chạy predict với --answers).'
    n = len(recs)
    rows = ['ngưỡng | trả lời | đúng | sai | PA nếu dùng ngưỡng này (0/rỗng: luôn bỏ trống) | PA (0/rỗng: trả lời như thường)']
    for thr in (0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0):
        stats = []
        for skip_zero in (True, False):
            right = wrong = 0
            for r in recs:
                v = r['vote']
                if not v.get('type') or v['confidence'] < thr:
                    continue
                if skip_zero and v['type'] != 'unanswerable' and is_zero(v['type'], v['answer']):
                    continue
                right += bool(r.get('top_correct'))
                wrong += not r.get('top_correct')
            stats.append((right, wrong))
        (r1, w1), (r2, w2) = stats
        rows.append(f'{thr:5.3f} | {r1 + w1:5d} | {r1:5d} | {w1:5d} | {(r1 - w1) / n:+.4f} | {(r2 - w2) / n:+.4f}')
    oracle = sum(any(s.get('correct') for s in r['samples']) for r in recs)
    greedy = sum(bool(r['samples'] and r['samples'][0].get('correct')) for r in recs)
    by_type: dict = {}
    for r in recs:
        b = by_type.setdefault(r['gold']['type'], [0, 0, 0])
        b[0] += 1
        b[1] += bool(r.get('top_correct'))
        b[2] += any(s.get('correct') for s in r['samples'])
    rows.append(f'\n{n} câu | bản nháp greedy đúng: {greedy} ({greedy / n:.1%}) | có ít nhất một bản nháp đúng: {oracle} ({oracle / n:.1%})')
    rows.append('theo loại đáp án (số câu / phiếu thắng đúng / có bản nháp đúng): ' +
                '; '.join(f'{t}: {a}/{b}/{c}' for t, (a, b, c) in sorted(by_type.items())))
    return '\n'.join(rows)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog='sqlvote')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('ingest', help='clean every shop into DuckDB and print the schema (no model needed)')
    p.add_argument('--split', required=True)
    p.add_argument('--cache', default=None)
    p.add_argument('--show', default=None, help='print the full prompt schema of this shop')
    p.add_argument('--rebuild', action='store_true')
    p = sub.add_parser('predict')
    p.add_argument('--split', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--cache', default=None)
    p.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    p.add_argument('--model', default='default')
    p.add_argument('--api-key', default='EMPTY')
    p.add_argument('--hf-model', default=None,
                   help='load this local model in-process with datamate.llm.QwenBackend instead of calling a server')
    p.add_argument('--quantize-4bit', action='store_true', help='with --hf-model: 4-bit NF4 (same as v6)')
    p.add_argument('--no-thinking', action='store_true', help='send chat_template_kwargs.enable_thinking=false (Qwen3 / Qwen3.5 on vLLM)')
    p.add_argument('--extra-body', default=None, help='JSON merged into every request')
    p.add_argument('--answers', default=None)
    p.add_argument('--questions', default=None, help='questions file to answer instead of <split>/questions.jsonl')
    p.add_argument('--bank', default=None)
    p.add_argument('--save-bank', default=None)
    p.add_argument('--shops', default=None, help='comma-separated business ids')
    p.add_argument('--limit-per-shop', type=int, default=0)
    p.add_argument('--no-resume', action='store_true')
    p.add_argument('--rebuild', action='store_true')
    for name, typ, default in (('k', int, 8), ('temperature', float, 0.7), ('threshold', float, 0.5),
                               ('unans-threshold', float, 0.5), ('zero-threshold', float, 1.01), ('shots', int, 4),
                               ('max-tokens', int, 700), ('repairs', int, 2), ('workers', int, 8),
                               ('time-budget', float, 0.0)):
        p.add_argument(f'--{name}', type=typ, default=default)
    p.add_argument('--allow-same-shop', action='store_true')
    p = sub.add_parser('score')
    p.add_argument('--answers', required=True)
    p.add_argument('--submission', required=True)
    p = sub.add_parser('calib', help='accuracy / PA by confidence threshold from logs written with --answers')
    p.add_argument('--logs', required=True)
    args = ap.parse_args(argv)

    if args.cmd == 'ingest':
        split = Path(args.split)
        cache = Path(args.cache) if args.cache else Path('sqlvote_cache')   # never inside the split: /data is read-only
        for shop in sorted(p for p in (split / 'data').iterdir() if p.is_dir()):
            t0 = time.time()
            meta = load_or_build(shop, cache / f'{shop.name}.duckdb', rebuild=args.rebuild)
            print(f'{shop.name}: {len(meta["tables"])} bảng, {sum(t["rows"] for t in meta["tables"])} dòng, '
                  f'dữ liệu {meta["data_start"]} → {meta["data_end"]} ({time.time() - t0:.1f}s)')
            if args.show == shop.name:
                print(schema_text(meta))
        return 0
    if args.cmd == 'score':
        result = score(read_jsonl(args.submission), read_jsonl(args.answers))
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == 'calib':
        print(calibration(args.logs))
        return 0
    if args.hf_model:                                  # in-process model of DataMate v6 (thinking is off in chat_ids)
        from datamate.llm import QwenBackend
        from .adapters import HFSamplingBackend
        backend = HFSamplingBackend(QwenBackend(args.hf_model, quantize_4bit=args.quantize_4bit))
        if args.workers != 1:
            print('--hf-model: workers đặt về 1 (một model trong tiến trình)', flush=True)
            args.workers = 1
    else:
        from .backends import OpenAIBackend
        extra = json.loads(args.extra_body) if args.extra_body else {}
        if args.no_thinking:
            extra.setdefault('chat_template_kwargs', {})['enable_thinking'] = False
        backend = OpenAIBackend(args.base_url, args.model, args.api_key, extra_body=extra)
    cfg = Config(k=args.k, temperature=args.temperature, threshold=args.threshold,
                 unans_threshold=args.unans_threshold, zero_threshold=args.zero_threshold, shots=args.shots,
                 max_tokens=args.max_tokens, repairs=args.repairs, workers=args.workers,
                 allow_same_shop=args.allow_same_shop, time_budget=args.time_budget)
    bank = Bank.load(args.bank) if args.bank else None
    result = predict(args.split, args.out, backend, cfg, args.cache, bank, args.answers,
                     set(args.shops.split(',')) if args.shops else None, args.limit_per_shop, args.save_bank,
                     resume=not args.no_resume, rebuild=args.rebuild, questions_path=args.questions)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
