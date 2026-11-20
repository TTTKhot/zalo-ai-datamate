"""Per-shop agreement between the metric route and the SQL route of public runs made with --sql (counts only).

python kaggle/agree_by_shop.py <run_public dir> [<run_public dir> ...]

For each shop: questions, share answered / unanswerable / abstain, share of answered questions where SQL agrees, and
(by the ChatGPT reference, a measuring stick only) match / differ of the answered questions split by agree / not agree.
Used to judge whether "SQL agreement rate of the shop" is a better whole-shop guard than the 20% unanswerable cap.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'kaggle'))
from datamate.scoring import is_correct          # noqa: E402
from score_public_ref import REF, load           # noqa: E402


def main():
    ref = {r['id']: r for r in load(REF)}
    print(f'{"shop":8s} {"câu":>4s} {"trả lời":>8s} {"unans":>6s} {"bỏ":>5s} {"agree/trả lời":>14s} | agree: khớp/khác | không agree: khớp/khác')
    tot = collections.Counter()
    for run in map(Path, sys.argv[1:]):
        subs = {r['id']: r for r in load(run / 'submission.jsonl')}
        for bdir in sorted(p for p in (run / 'logs').iterdir() if p.is_dir()):
            c = collections.Counter()
            for f in bdir.glob('*.json'):
                if f.name == 'shop_report.json':
                    continue
                d = json.loads(f.read_text(encoding='utf-8'))
                r = subs.get(d['id'], {'type': 'abstain'})
                kind = r['type'] if r['type'] in ('abstain', 'unanswerable') else 'answered'
                c['n'] += 1
                c[kind] += 1
                if kind == 'answered':
                    ag = d.get('agree') == 'agree'
                    try:
                        good = bool(is_correct(r, ref[d['id']]))
                    except Exception:
                        good = False
                    c[(ag, good)] += 1
            n, a = max(c['n'], 1), max(c['answered'], 1)
            agree = c[(True, True)] + c[(True, False)]
            print(f'{bdir.name:8s} {c["n"]:4d} {100 * c["answered"] / n:7.0f}% {100 * c["unanswerable"] / n:5.0f}% '
                  f'{100 * c["abstain"] / n:4.0f}% {100 * agree / a:13.0f}% | {c[(True, True)]}/{c[(True, False)]} | '
                  f'{c[(False, True)]}/{c[(False, False)]}')
            tot.update({k: v for k, v in c.items() if isinstance(k, tuple)})
    print(f'tổng: agree khớp/khác {tot[(True, True)]}/{tot[(True, False)]} | không agree khớp/khác {tot[(False, True)]}/{tot[(False, False)]}')


if __name__ == '__main__':
    main()
