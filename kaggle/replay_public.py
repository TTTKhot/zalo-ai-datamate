"""Replay logged Qwen outputs of a run on a split WITHOUT answers through the current code (no GPU).

python kaggle/replay_public.py <split dir> <out.jsonl> <logs dir> [<logs dir> ...]

<logs dir> = .../run_public/logs (one folder per shop with <id>.json holding llm_raw). Table mapping is rebuilt by the
heuristic mapper (like kaggle/replay.py), so mapper-LLM differences are not reproduced. Writes submission lines in the
order of questions.jsonl (questions without a log -> abstain). Prints counts only.
"""
import collections
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.llm import ReplayBackend                      # noqa: E402
from datamate.normalize import norm                         # noqa: E402
from datamate.periods import Calendar                       # noqa: E402
from datamate.pipeline import answer, llm_intent_fn, load_shop  # noqa: E402
from datamate.scoring import to_submission                  # noqa: E402


def main():
    split, out = Path(sys.argv[1]), Path(sys.argv[2])
    qs = [json.loads(l) for l in (split / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    by_id = {q['id']: q for q in qs}
    cal = Calendar(split / 'calendar.csv')
    lines, reasons = {}, {}
    for logs in map(Path, sys.argv[3:]):
        for bdir in sorted(p for p in logs.iterdir() if p.is_dir()):
            files = [f for f in sorted(bdir.glob('*.json')) if f.name != 'shop_report.json']
            if not files:
                continue
            try:
                shop = load_shop(split / 'data' / bdir.name, bdir.name)
            except Exception as exc:
                print(bdir.name, 'không nạp được shop:', type(exc).__name__)
                continue
            c = collections.Counter()
            for f in files:
                log = json.loads(f.read_text(encoding='utf-8'))
                q = by_id.get(log['id'])
                if q is None:
                    continue
                fn = llm_intent_fn(ReplayBackend(log.get('llm_raw') or []), norm)
                try:
                    res = answer(shop, q, fn, cal)
                except Exception as exc:
                    res = {'id': q['id'], 'status': 'abstain', 'reason': repr(exc)}
                res['id'] = q['id']
                lines[q['id']] = to_submission(res)
                reasons[q['id']] = {'id': q['id'], 'shop': bdir.name, 'status': res.get('status'),
                                    'reason': res.get('reason'), 'route': res.get('route'),
                                    'metric': (res.get('intent') or {}).get('metric'), 'intent': res.get('intent'),
                                    'answer': res.get('answer')}
                c[lines[q['id']]['type'] if lines[q['id']]['type'] in ('abstain', 'unanswerable') else 'có đáp án'] += 1
            print(bdir.name, dict(c), flush=True)
    with out.open('w', encoding='utf-8', newline='\n') as f:
        for q in qs:
            f.write(json.dumps(lines.get(q['id'], {'id': q['id'], 'type': 'abstain'}), ensure_ascii=False, default=str) + '\n')
    side = out.with_suffix('.reasons.jsonl')
    with side.open('w', encoding='utf-8', newline='\n') as f:
        for q in qs:
            if q['id'] in reasons:
                f.write(json.dumps(reasons[q['id']], ensure_ascii=False, default=str) + '\n')
    print('ghi', out, len(qs), 'dòng; lý do:', side)


if __name__ == '__main__':
    main()
