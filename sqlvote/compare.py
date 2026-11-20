"""Side-by-side comparison of several runs on the SAME questions, scored against gold (rulebook §9).

  python -m sqlvote.compare --answers data/train/answers.jsonl \
      --run v6=runs/<stamp>/state/run_lora_sql --run sqlvote=runs/<stamp>/state/sqlvote \
      [--questions data/train/questions.jsonl] [--out runs/<stamp>/compare.md] [--max-examples 40]

A run is any of:
  * a submission.jsonl file (official format);
  * a folder that contains submission.jsonl (v6 `state/run_<name>/`, sqlvote `--out` folder);
  * a v6 `state/results_<name>/` folder of <biz>.json lists (items with id / status / answer / type).

Only questions present in EVERY run (and in the gold file) are scored, so the numbers are comparable.
With two runs or more, the report also estimates simple ways of combining the first two runs (A, B):
  * A, fall back to B when A abstains        * B, fall back to A when B abstains
  * answer only when A and B give the same answer (both scored with the scorer's comparison)
These estimates use gold only to SCORE fixed rules; they do not fit anything. Still, choose the final
rule on held-out (val) shops and report it there, not on the shops whose errors you studied.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import answer_key
from .scorer import is_correct, read_jsonl


# ---------------------------------------------------------------- loading
def _from_result_item(item: dict) -> dict:
    qid = item.get('id') or item.get('question_id')
    status = item.get('status')
    if status == 'unanswerable':
        return {'id': qid, 'type': 'unanswerable'}
    if status != 'answered':
        return {'id': qid, 'type': 'abstain'}
    answer = item.get('answer')
    kind = item.get('type') or item.get('answer_type') or 'string'
    if kind == 'table' and isinstance(answer, list) and answer and isinstance(answer[0], dict):
        cols = list(answer[0].keys())
        answer = {'columns': cols, 'rows': [[row.get(c) for c in cols] for row in answer]}
    return {'id': qid, 'type': kind, 'answer': answer}


def load_run(path) -> dict:
    """-> {question id: submission line}."""
    path = Path(path)
    if path.is_dir() and (path / 'submission.jsonl').exists():
        path = path / 'submission.jsonl'
    if path.is_file():
        return {r['id']: r for r in read_jsonl(path)}
    if path.is_dir():
        out = {}
        for f in sorted(path.glob('*.json')):
            if f.name.endswith('.meta.json'):
                continue
            data = json.loads(f.read_text(encoding='utf-8'))
            for item in data if isinstance(data, list) else data.get('results', []):
                line = _from_result_item(item)
                out[line['id']] = line
        if out:
            return out
    raise FileNotFoundError(f'không đọc được kết quả ở {path}')


# ---------------------------------------------------------------- scoring helpers
def verdict(line: dict | None, gold: dict) -> str:
    if line is None or line.get('type') == 'abstain':
        return 'abstain'
    return 'correct' if is_correct(line, gold) else 'wrong'


def key_of(line: dict | None):
    if line is None or line.get('type') in (None, 'abstain'):
        return None
    try:
        return answer_key(line['type'], line.get('answer'))
    except Exception:
        return ('?', json.dumps(line.get('answer'), ensure_ascii=False, default=str))


def tally(verdicts: list[str]) -> dict:
    c, w, a = verdicts.count('correct'), verdicts.count('wrong'), verdicts.count('abstain')
    n = max(len(verdicts), 1)
    return {'n': len(verdicts), 'correct': c, 'wrong': w, 'abstain': a, 'pa': (c - w) / n,
            'precision': c / (c + w) if c + w else 0.0}


def _fmt(t: dict) -> str:
    return f'{t["pa"]:+.4f} | {t["correct"]} | {t["wrong"]} | {t["abstain"]} | {t["precision"]:.1%}'


def _short(v, width: int = 70) -> str:
    text = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v
    return text if len(text) <= width else text[:width - 1] + '…'


def _show(line: dict | None) -> str:
    if line is None or line.get('type') == 'abstain':
        return '(bỏ trống)'
    if line['type'] == 'unanswerable':
        return 'unanswerable'
    return f'{line["type"]}: {_short(line.get("answer"))}'


# ---------------------------------------------------------------- report
def compare(runs: dict, golds: dict, questions: dict | None = None, max_examples: int = 40) -> tuple[str, dict]:
    names = list(runs)
    common = sorted(set(golds).intersection(*[set(r) for r in runs.values()]))
    lines = [f'# So sánh {len(names)} lần chạy trên {len(common)} câu chung', '']
    for name in names:
        lines.append(f'- **{name}**: {len(runs[name])} câu trong file, {len(set(runs[name]) & set(golds))} câu có gold')
    if not common:
        lines.append('\nKhông có câu nào chung giữa các lần chạy và gold.')
        return '\n'.join(lines), {}
    per = {n: {q: verdict(runs[n].get(q), golds[q]) for q in common} for n in names}
    summary = {n: tally(list(per[n].values())) for n in names}

    lines += ['', '## Tổng', '', 'lần chạy | PA | đúng | sai | bỏ trống | đúng / đã trả lời', '---|---|---|---|---|---']
    lines += [f'{n} | {_fmt(summary[n])}' for n in names]

    types = sorted({golds[q]['type'] for q in common})
    lines += ['', '## Theo loại đáp án gold (PA / đúng / sai)', '',
              'loại | số câu | ' + ' | '.join(names), '---|---|' + '---|' * len(names)]
    for t in types:
        qs = [q for q in common if golds[q]['type'] == t]
        cells = []
        for n in names:
            s = tally([per[n][q] for q in qs])
            cells.append(f'{s["pa"]:+.2f} / {s["correct"]} / {s["wrong"]}')
        lines.append(f'{t} | {len(qs)} | ' + ' | '.join(cells))

    if questions:
        shops = sorted({questions[q].get('business_id', '?') for q in common if q in questions})
        lines += ['', '## Theo shop (PA)', '', 'shop | số câu | ' + ' | '.join(names), '---|---|' + '---|' * len(names)]
        for shop in shops:
            qs = [q for q in common if questions.get(q, {}).get('business_id') == shop]
            lines.append(f'{shop} | {len(qs)} | ' + ' | '.join(f'{tally([per[n][q] for q in qs])["pa"]:+.2f}' for n in names))

    combos = {}
    if len(names) >= 2:
        a, b = names[0], names[1]
        ra, rb = runs[a], runs[b]
        pairs = {}
        for q in common:
            pairs[(per[a][q], per[b][q])] = pairs.get((per[a][q], per[b][q]), 0) + 1
        order = ('correct', 'wrong', 'abstain')
        lines += ['', f'## Bảng chéo: hàng = {a}, cột = {b}', '', ' | ' + ' | '.join(order), '---|---|---|---']
        for va in order:
            lines.append(f'{va} | ' + ' | '.join(str(pairs.get((va, vb), 0)) for vb in order))

        def pick_fallback(first, second):
            out = []
            for q in common:
                line = first.get(q)
                if line is None or line.get('type') == 'abstain':
                    line = second.get(q)
                out.append(verdict(line, golds[q]))
            return tally(out)

        agree = []
        for q in common:
            ka, kb = key_of(ra.get(q)), key_of(rb.get(q))
            agree.append(verdict(ra.get(q), golds[q]) if ka is not None and ka == kb else 'abstain')
        combos = {f'{a}, bỏ trống thì lấy {b}': pick_fallback(ra, rb),
                  f'{b}, bỏ trống thì lấy {a}': pick_fallback(rb, ra),
                  f'chỉ trả lời khi {a} và {b} trùng đáp án': tally(agree)}
        lines += ['', '## Ước lượng khi ghép hai đường (luật cố định, chỉ dùng gold để chấm)', '',
                  'cách ghép | PA | đúng | sai | bỏ trống | đúng / đã trả lời', '---|---|---|---|---|---']
        lines += [f'{k} | {_fmt(v)}' for k, v in combos.items()]

        def examples(title, cond):
            qs = [q for q in common if cond(q)]
            if not qs:
                return
            lines.extend(['', f'### {title} ({len(qs)} câu)', ''])
            for q in qs[:max_examples]:
                text = questions.get(q, {}).get('question', '') if questions else ''
                shop = questions.get(q, {}).get('business_id', '') if questions else ''
                gold = golds[q]
                gshow = 'unanswerable' if gold['type'] == 'unanswerable' else f'{gold["type"]}: {_short(gold.get("answer"))}'
                lines.append(f'- `{q}` {shop} — {text}\n  - gold {gshow}\n  - {a}: {_show(ra.get(q))}\n  - {b}: {_show(rb.get(q))}')
            if len(qs) > max_examples:
                lines.append(f'- … còn {len(qs) - max_examples} câu')

        lines += ['', '## Câu khác nhau (để phân tích lỗi)']
        examples(f'{b} đúng, {a} sai', lambda q: per[b][q] == 'correct' and per[a][q] == 'wrong')
        examples(f'{b} đúng, {a} bỏ trống', lambda q: per[b][q] == 'correct' and per[a][q] == 'abstain')
        examples(f'{a} đúng, {b} sai', lambda q: per[a][q] == 'correct' and per[b][q] == 'wrong')
        examples(f'{a} đúng, {b} bỏ trống', lambda q: per[a][q] == 'correct' and per[b][q] == 'abstain')
        examples('cả hai cùng sai', lambda q: per[a][q] == 'wrong' and per[b][q] == 'wrong')
    return '\n'.join(lines) + '\n', {'summary': summary, 'combos': combos, 'n_common': len(common)}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog='sqlvote.compare', description=__doc__.split('\n')[0])
    ap.add_argument('--answers', required=True)
    ap.add_argument('--run', action='append', required=True, help='NAME=PATH (repeat; the first two are A and B)')
    ap.add_argument('--questions', default=None, help='questions.jsonl, for question text and shop ids')
    ap.add_argument('--out', default=None, help='write the markdown report here')
    ap.add_argument('--max-examples', type=int, default=40)
    args = ap.parse_args(argv)
    runs = {}
    for spec in args.run:
        name, sep, path = spec.partition('=')
        if not sep:
            name, path = Path(spec).name, spec
        runs[name] = load_run(path)
    golds = {g['id']: g for g in read_jsonl(args.answers)}
    questions = {q['id']: q for q in read_jsonl(args.questions)} if args.questions else None
    report, _ = compare(runs, golds, questions, args.max_examples)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding='utf-8')
        print(f'đã ghi {args.out}')
    print(report if not args.out else report.split('## Câu khác nhau')[0])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
