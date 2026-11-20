"""Offline entry point (Docker / Kaggle).

python -m datamate.predict --data-root /data --questions /data/questions.jsonl \
       --model /models/Qwen3.5-4B --out /result/submission.jsonl [--calibration calibration.json]
       [--adapter /models/intent_lora] [--sql] [--answerability /models/xlmr_ans]
       [--hint-model /models/vit5_norm] [--resume]

For every business: read tables -> mapping (heuristic + LLM JSON + fixed checks) -> views.
For every question: LLM intent JSON (validated, 1 repair) -> metric library; optional SQL route
(agreement feature), optional XLM-R P(answerable); calibrated answer/abstain.
Writes submission.jsonl, logs/<biz>/<id>.json and logs/<biz>/shop_report.json.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .calibration import Calibrator
from .normalize import norm
from .periods import Calendar
from .pipeline import answer, llm_intent_fn, load_shop, question_context
from .runstate import (atomic_write_text, code_fingerprint, compare_signature, fingerprint, read_jsonl_tolerant,
                       write_signature)
from .scoring import to_submission


def find_calendar(data_root: Path):
    for p in [data_root / 'calendar.csv', *data_root.rglob('calendar.csv')]:
        if p.exists():
            return p
    return None


def shop_folder(data_root: Path, biz: str):
    for cand in (data_root / 'data' / biz, data_root / biz):
        if cand.is_dir():
            return cand
    hits = [p for p in data_root.rglob(biz) if p.is_dir()]
    return hits[0] if hits else None


def log_record(out: dict, line: dict, folder, seconds: float) -> dict:
    """Per-question log in the format of the organisers' Docker guide (section 3.3) + our own fields.

    Required: id, answer (final answer = the submission line), elapsed_ms, thinking (null: Qwen runs with thinking
    disabled, every raw model output is kept in llm_raw / sql_raw), and for answers computed by code: code, inputs,
    output. The pipeline's own value (before calibration) stays in `pipeline_answer` for scoring tools."""
    log = dict(out)
    if 'answer' in out:
        log['pipeline_answer'] = out['answer']
    log['answer'] = {k: v for k, v in line.items() if k != 'id'}
    log['elapsed_ms'] = max(0, int(round(seconds * 1000)))
    log['thinking'] = None
    log['code'] = log['inputs'] = log['output'] = None
    if out.get('route') == 'sql' and out.get('sql'):
        log['code'] = out['sql']                                   # SQL written by Qwen, run with duckdb
        log['inputs'] = {'engine': 'duckdb', 'tables': 'canonical views of ' + str(folder)}
        log['output'] = out.get('sql_value')
    elif out.get('intent') and out.get('original_status', out.get('status')) in ('answered', 'unanswerable'):
        computed = out.get('original_status', out.get('status'))       # before the abstain threshold
        log['code'] = 'datamate/pipeline.py::answer -> datamate/metrics.py::run'
        log['inputs'] = {'data_dir': str(folder), 'intent': out.get('intent'), 'as_of_date': out.get('as_of')}
        log['output'] = out.get('answer') if computed == 'answered' else {'unanswerable': out.get('reason')}
    return log


def load_done(args, out_path: Path, meta_path: Path, log_dir: Path, signature: dict, questions: list) -> dict:
    """Answers that may be reused on --resume.

    Reused only when the run signature matches (else old logs of these shops move to <logs>_stale_<n>/ so
    score_run never mixes results of two code versions), the line parses, the id is still asked and its log
    file exists. Logs of ids no longer asked are moved aside too.
    """
    if not args.resume:
        return {}
    status, diff = compare_signature(meta_path, signature)
    if status == 'new' and out_path.exists():
        status, diff = 'changed', ['<no meta: run made by older code>']
    wanted = {q['id']: q['business_id'] for q in questions}
    if status == 'changed' and not args.force_resume:
        print(f'resume: signature changed {diff} -> rerun from scratch', flush=True)
        _move_stale(log_dir, set(wanted.values()), None)
        return {}
    rows, bad = read_jsonl_tolerant(out_path)
    done = {d['id']: d for d in rows if d.get('id') in wanted and (log_dir / wanted[d['id']] / f"{d['id']}.json").exists()}
    _move_stale(log_dir, set(wanted.values()), set(wanted))
    print(f'resume: reuse {len(done)} answers ({bad} torn lines, {len(rows) - len(done)} dropped)', flush=True)
    return done


def _move_stale(log_dir: Path, businesses: set, keep_ids):
    """Move log files of these businesses (all, or those not in keep_ids) out of the scored logs dir."""
    if not log_dir.exists():
        return
    n = 0
    while (log_dir.parent / f'{log_dir.name}_stale_{n}').exists():
        n += 1
    dest = log_dir.parent / f'{log_dir.name}_stale_{n}'
    moved = 0
    for biz in businesses:
        bdir = log_dir / biz
        for f in (sorted(bdir.glob('*.json')) if bdir.is_dir() else []):
            if f.name == 'shop_report.json' or (keep_ids is not None and f.stem in keep_ids):
                continue
            (dest / biz).mkdir(parents=True, exist_ok=True)
            f.replace(dest / biz / f.name)
            moved += 1
    if moved:
        print(f'resume: moved {moved} stale logs to {dest}', flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', required=True)
    ap.add_argument('--questions', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--calibration', default='')
    ap.add_argument('--log-dir', default='')
    ap.add_argument('--businesses', nargs='*', default=None)
    ap.add_argument('--no-llm-mapper', action='store_true', help='mapping from heuristics + checks only')
    ap.add_argument('--quantize-4bit', action='store_true')
    ap.add_argument('--adapter', default='', help='LoRA adapter dir (step 1); switches to the compact prompt')
    ap.add_argument('--prompt', choices=['full', 'compact'], default=None)
    ap.add_argument('--no-fixes', action='store_true', help='skip cue rules (measure the finetuned model alone)')
    ap.add_argument('--sql', action='store_true', help='step 2: SQL route + agreement feature')
    ap.add_argument('--answerability', default='', help='step 3: XLM-R model dir')
    ap.add_argument('--hint-model', default='', help='step 4: seq2seq normaliser dir (hint only)')
    ap.add_argument('--resume', action='store_true',
                    help='skip questions already answered by the SAME code/model/adapter/calibration (signature)')
    ap.add_argument('--force-resume', action='store_true', help='resume even if the signature changed')
    ap.add_argument('--rule-gate', action='store_true',
                    help='read <data-root>/rulebook.md and abstain on questions using new / uncovered rules. OFF by '
                         'default: on the public leaderboard (15/11) the gate cost ~0.02 (42 abstains, ~30 were right)')
    ap.add_argument('--no-rule-gate', action='store_true', help='kept for old scripts (the gate is off by default)')
    args = ap.parse_args(argv)

    from .llm import QwenBackend
    data_root = Path(args.data_root)
    out_path = Path(args.out)
    log_dir = Path(args.log_dir) if args.log_dir else out_path.parent / 'logs'
    questions = [json.loads(l) for l in Path(args.questions).read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    if args.businesses:
        questions = [q for q in questions if q['business_id'] in set(args.businesses)]
    cal_path = find_calendar(data_root)
    calendar = Calendar(cal_path) if cal_path else None
    gate = None
    rb_path = data_root / 'rulebook.md'
    if args.rule_gate and not args.no_rule_gate and rb_path.exists():
        from .rulebook import Gate
        try:
            gate = Gate.from_file(rb_path)
            print(f'rulebook gate: {len(gate.items)} trigger phrases of new / uncovered / modified rules', flush=True)
        except Exception as exc:                      # a rulebook we cannot parse must not stop the run
            print(f'!! rulebook gate off: {exc!r}', flush=True)
    calibrator = Calibrator.load(args.calibration) if args.calibration and Path(args.calibration).exists() else None
    test_backend = os.environ.get('DATAMATE_TEST_BACKEND')      # tests only (module:Class), never set in the image
    if test_backend:
        import importlib
        mod, cls = test_backend.split(':')
        QwenBackend = getattr(importlib.import_module(mod), cls)   # noqa: N806
    backend = QwenBackend(args.model, quantize_4bit=args.quantize_4bit, adapter=args.adapter or None)
    prompt = args.prompt or ('compact' if args.adapter else 'full')
    ans_model = None
    if args.answerability and Path(args.answerability).exists():
        from .answerability import AnswerabilityModel
        ans_model = AnswerabilityModel(args.answerability)
    hint_fn = None
    if args.hint_model and Path(args.hint_model).exists():
        from .neural_norm import GuardedNormalizer
        hint_fn = GuardedNormalizer(args.hint_model)
    print(f'prompt={prompt} adapter={bool(args.adapter)} sql={args.sql} answerability={ans_model is not None} '
          f'hint={hint_fn is not None} calibration={calibrator is not None}', flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    signature = {'code': code_fingerprint(), 'model': Path(str(args.model)).name,
                 'adapter': fingerprint(args.adapter), 'calibration': fingerprint(args.calibration),
                 'answerability': fingerprint(args.answerability), 'hint': fingerprint(args.hint_model),
                 'prompt': prompt, 'sql': args.sql, 'no_fixes': args.no_fixes, 'llm_mapper': not args.no_llm_mapper,
                 'quantize_4bit': args.quantize_4bit,
                 'rule_gate': fingerprint(str(rb_path)) if gate is not None else None}
    meta_path = out_path.with_name(out_path.stem + '.meta.json')
    done = load_done(args, out_path, meta_path, log_dir, signature, questions)
    write_signature(meta_path, signature, businesses=sorted({q['business_id'] for q in questions}))
    started = time.time()
    with out_path.open('w', encoding='utf-8') as sub:
        for d in done.values():
            sub.write(json.dumps(d, ensure_ascii=False, default=str) + '\n')
        sub.flush()
        for biz in dict.fromkeys(q['business_id'] for q in questions):
            todo = [q for q in questions if q['business_id'] == biz and q['id'] not in done]
            if not todo:
                continue
            bdir = log_dir / biz
            bdir.mkdir(parents=True, exist_ok=True)
            folder = shop_folder(data_root, biz)
            shop, sql_route, caps = None, None, None
            if folder is not None:
                try:
                    base = backend.base() if hasattr(backend, 'base') else backend      # adapter off for mapping / SQL
                    shop = load_shop(folder, biz, None if args.no_llm_mapper else base)
                    report = dict(shop.report)
                    from .answerability import capabilities
                    caps = capabilities(shop.views)
                    report['capabilities'] = caps
                    if args.sql:
                        from .sqlpath import SqlRoute
                        sql_route = SqlRoute(shop, base, calendar)
                    (bdir / 'shop_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1,
                                                                      default=str), encoding='utf-8')
                except Exception as exc:                      # a broken shop must not stop the run
                    (bdir / 'shop_report.json').write_text(json.dumps({'error': repr(exc)}), encoding='utf-8')
            for rec in todo:
                t0 = time.time()
                trace = []
                if shop is None:
                    out = {'id': rec['id'], 'status': 'abstain', 'reason': 'shop not loaded'}
                else:
                    fn = llm_intent_fn(backend, norm, trace=trace, prompt=prompt, hint_fn=hint_fn,
                                       apply_fixes=not args.no_fixes)
                    out = answer(shop, rec, fn, calendar, gate=gate)
                    # rule the code does not implement, or a shop that failed its self-check: abstain
                    gated = out.get('route') in ('rule_gate', 'shop_check')
                    out['repairs'] = trace[0]['repairs'] if trace else 0
                    out['llm_raw'] = trace[0]['raw'] if trace else []
                    out['fixes'] = trace[0]['fixes'] if trace else []
                    if trace and trace[0].get('hint'):
                        out['hint'] = trace[0]['hint']
                    if sql_route is not None and not gated:
                        from .sqlpath import attach_sql
                        try:
                            n, tagged, _ = question_context(rec['question'], rec.get('as_of_date'), shop.names, norm)
                            out = attach_sql(out, sql_route.ask(rec['question'], rec.get('as_of_date'), n, tagged))
                        except Exception as exc:
                            out['agree'] = 'nosql'
                            out['sql_error'] = repr(exc)
                    if ans_model is not None and caps is not None and not gated:
                        try:
                            out['p_answerable'] = round(ans_model.p_answerable(rec['question'], caps=caps), 4)
                        except Exception as exc:
                            out['answerability_error'] = repr(exc)
                    if calibrator and not gated:
                        out = calibrator.decide(out)
                out['business_id'] = biz
                out['elapsed_s'] = round(time.time() - t0, 3)
                line = to_submission(out)
                log = log_record(out, line, folder, time.time() - t0)
                atomic_write_text(bdir / f"{rec['id']}.json", json.dumps(log, ensure_ascii=False, indent=1, default=str))
                sub.write(json.dumps(line, ensure_ascii=False, default=str) + '\n')    # answer saved right away
                sub.flush()
            print(f'{biz}: done, elapsed {time.time() - started:.0f}s, llm calls {backend.calls}', flush=True)


if __name__ == '__main__':
    main()
