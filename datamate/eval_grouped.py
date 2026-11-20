"""Shop-held-out evaluation.

Rows come from a full train run (one JSON per shop, each row has verdict and status).
Two splits, both keep every question of a shop on the same side:
  * GroupKFold over shops (k folds);
  * leave-one-schema-out: shops grouped by which concepts their data has
    (e.g. {sales_line} vs {order, sales_line, payment, purchase, ...}) so the
    held-out group is a *kind* of shop never seen while fitting the policy.
The abstain policy is fitted on the training side only and scored on the held-out side.

python -m datamate.eval_grouped --results results/ --folds 5
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .calibration import Calibrator


def score(rows):
    c = Counter(r['verdict'] for r in rows)
    return {'n': len(rows), 'correct': c['correct'], 'wrong': c['wrong'],
            'abstain': c['abstain'] + c.get('no_gold', 0), 'score': c['correct'] - c['wrong']}


def apply_policy(cal: Calibrator, rows):
    out = []
    for r in rows:
        d = cal.decide(r)
        if d.get('status') == 'abstain' and r.get('status') != 'abstain':
            d = dict(d, verdict='abstain')
        elif r.get('status') == 'abstain' and d.get('status') == 'unanswerable':     # rescued
            d = dict(d, verdict='correct' if r.get('gold_type') == 'unanswerable' else 'wrong')
        out.append(d)
    return out


def group_kfold(shops, k):
    shops = sorted(shops)
    return [shops[i::k] for i in range(k)]


def evaluate(by_shop: dict, signatures: dict, folds: int = 5, prior: float = 4.0, **cal_kw):
    report = {'raw': score([r for rows in by_shop.values() for r in rows])}
    for name, groups in (('group_kfold', group_kfold(by_shop, min(folds, len(by_shop)))),
                         ('leave_schema_out', [sorted(s for s, sig in signatures.items() if sig == g)
                                               for g in sorted(set(signatures.values()))])):
        held_rows, per_group = [], []
        for test in groups:
            train = [r for s, rows in by_shop.items() if s not in test for r in rows]
            cal = Calibrator(prior, **cal_kw).fit(train)
            test_rows = [r for s in test for r in by_shop[s]]
            decided = apply_policy(cal, test_rows)
            held_rows.extend(decided)
            per_group.append({'held_out': test, 'raw': score(test_rows), 'with_policy': score(decided)})
        report[name] = {'with_policy': score(held_rows), 'groups': per_group}
    return report


def load_results(folder):
    by_shop, signatures = {}, {}
    for path in sorted(p for p in Path(folder).glob('biz_*.json') if not p.name.endswith('.meta.json')):
        rows = json.loads(path.read_text(encoding='utf-8'))
        by_shop[path.stem] = rows
        meta = Path(folder) / f'{path.stem}.meta.json'
        if meta.exists():
            signatures[path.stem] = '+'.join(json.loads(meta.read_text(encoding='utf-8')).get('concepts', []))
        else:
            signatures[path.stem] = '?'
    return by_shop, signatures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--out')
    ap.add_argument('--no-agree', action='store_true')
    ap.add_argument('--no-ans', action='store_true')
    ap.add_argument('--no-rescue', action='store_true')
    args = ap.parse_args()
    by_shop, sigs = load_results(args.results)
    report = evaluate(by_shop, sigs, args.folds, use_agree=not args.no_agree, use_ans=not args.no_ans,
                      rescue=not args.no_rescue)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(json.dumps({k: (v if k == 'raw' else v['with_policy']) for k, v in report.items()}, indent=1))
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
