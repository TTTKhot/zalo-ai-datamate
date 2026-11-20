"""Shop-level sanity cap on "unanswerable" answers, applied to an existing submission (no GPU run).

python kaggle/apply_unans_cap.py <submission.jsonl> <split dir with questions.jsonl> <out.jsonl> [cap=0.2]

Why: "unanswerable" costs -1 when wrong, and the pipeline says it whenever the mapped data lacks a concept
(no order number, no payments table ...). When the table mapping of a shop is wrong, that claim repeats for a large
share of the shop's questions. On train (24 non-held-out shops) the TRUE share of unanswerable questions per shop is
0% median, 10.2% max (2.5% overall). A shop whose answers are "unanswerable" for more than `cap` (default 20% =
twice the train maximum) cannot be right on most of them even in the most favourable case -> expected score of
those answers is negative -> turn them into abstain (0). Shops under the cap are left untouched.
The rule uses no shop name and no question id; the constant comes from train only. Prints counts only.
"""
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    sub_path, split, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    cap = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
    shop = {}
    for line in (split / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            q = json.loads(line)
            shop[q['id']] = q['business_id']
    rows = [json.loads(l) for l in sub_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    total, unans = Counter(), Counter()
    for r in rows:
        total[shop[r['id']]] += 1
        unans[shop[r['id']]] += r.get('type') == 'unanswerable'
    over = {b for b in total if unans[b] / total[b] > cap}
    changed = 0
    with out.open('w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            if r.get('type') == 'unanswerable' and shop[r['id']] in over:
                r = {'id': r['id'], 'type': 'abstain'}
                changed += 1
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'{len(rows)} dòng; ngưỡng {cap:.0%}; {len(over)}/{len(total)} shop vượt ngưỡng; '
          f'unanswerable -> abstain: {changed}/{sum(unans.values())} -> {out}')


if __name__ == '__main__':
    main()
