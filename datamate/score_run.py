"""Turn a predict.py run (logs/<biz>/<id>.json) into results/<biz>.json with verdicts.

python -m datamate.score_run --logs out/logs --answers answers.jsonl --out results_llm
Then: python -m datamate.eval_grouped --results results_llm   (shop-held-out score)
      python -m datamate.calibration --results results_llm --out calibration.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .scoring import is_correct, to_submission


SQL_KEYS = ('sql', 'sql_status', 'sql_value', 'sql_problems', 'agree', 'sql_error')


def strip_sql(row: dict) -> dict:
    """The same pipeline output without the SQL route (SQL-only answers go back to abstain)."""
    row = {k: v for k, v in row.items() if k not in SQL_KEYS}
    if row.get('route') == 'sql':
        for k in ('answer', 'type', 'route'):
            row.pop(k, None)
        row.update(status='abstain', reason=row.pop('metric_reason', 'no intent'))
        row.pop('original_status', None)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logs', required=True)
    ap.add_argument('--answers', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--strip-sql', action='store_true',
                    help='score the run as if the SQL route was off (before/after of step 2 from one GPU run)')
    ap.add_argument('--strip-ans', action='store_true', help='drop p_answerable (before/after of step 3)')
    args = ap.parse_args()
    gold = {r['id']: r for r in (json.loads(l) for l in Path(args.answers).read_text(encoding='utf-8').splitlines() if l.strip())}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total = Counter()
    for bdir in sorted(p for p in Path(args.logs).iterdir() if p.is_dir()):
        rows = []
        for f in sorted(bdir.glob('*.json')):
            if f.name == 'shop_report.json':
                continue
            row = json.loads(f.read_text(encoding='utf-8'))
            row.pop('llm_raw', None)
            row.pop('sql_raw', None)
            if args.strip_sql:
                row = strip_sql(row)
            if args.strip_ans:
                row.pop('p_answerable', None)
            g = gold.get(row['id'])
            if g is None:
                continue
            # score the raw decision (before calibration) so the policy can be refitted
            raw = dict(row, status=row.get('original_status', row.get('status')))
            sub = to_submission(raw)
            row['verdict'] = 'abstain' if sub['type'] == 'abstain' else ('correct' if is_correct(sub, g) else 'wrong')
            row['status'] = raw['status']
            row['gold_type'] = g['type']
            row['gold'] = g.get('answer') if g['type'] != 'unanswerable' else 'UNANSWERABLE'
            rows.append(row)
            total[row['verdict']] += 1
        if not rows:
            continue
        (out / f'{bdir.name}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        report = bdir / 'shop_report.json'
        rep = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
        (out / f'{bdir.name}.meta.json').write_text(json.dumps({'concepts': rep.get('concepts', []),
                                                                 'capabilities': rep.get('capabilities')},
                                                                ensure_ascii=False), encoding='utf-8')
        c = Counter(r['verdict'] for r in rows)
        print(f"{bdir.name}: {dict(c)} score {c['correct'] - c['wrong']}")
    print('TOTAL', dict(total), 'score', total['correct'] - total['wrong'])


if __name__ == '__main__':
    main()
