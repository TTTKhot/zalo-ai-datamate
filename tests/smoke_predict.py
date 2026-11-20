"""GPU-free end-to-end smoke test of datamate.predict (intent + SQL route + calibration + resume).

The Qwen backend is replaced by a fake that answers intent prompts with the scripted parser
and SQL prompts with a fixed revenue / order-count / best-day template, so every code path of
predict.py, sqlpath.py, score_run.py and the v6 calibration runs on CPU.

python tests/smoke_predict.py --train-root DATA/train --out /tmp/smoke [--sql] [--compact]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

import datamate.llm as llm                                    # noqa: E402
from datamate.pipeline import load_shop_cached                # noqa: E402
from scripted_intent import scripted_intent                   # noqa: E402

SHOPS = {}


def fake_generate(messages):
    user = messages[1]['content']
    q = user.rsplit('\nQ: ', 1)[1].split('\n', 1)[0]
    if messages[0]['content'].startswith('You write ONE DuckDB SQL'):
        per = json.loads(re.search(r'PERIODS found in the question: (\[.*?\])\n', user).group(1))
        if not per:
            return 'SELECT NULL'
        s, e = per[0]['start'], per[0]['end_exclusive']
        w = f"counts_for_revenue AND order_date >= DATE '{s}' AND order_date < DATE '{e}'"
        if re.search(r'đơn|don|bill', q, re.I):
            return f'SELECT COUNT(DISTINCT order_id) FROM orders WHERE {w}'
        if re.search(r'ngày nào|ngay nao', q, re.I):
            return f'SELECT order_date FROM orders WHERE {w} GROUP BY order_date ORDER BY SUM(revenue) DESC, order_date LIMIT 1'
        return f'```sql\nSELECT SUM(revenue) FROM orders WHERE {w};\n```'
    as_of = re.search(r'today[^:]*: (\S+)', user).group(1)
    names = next(iter(SHOPS.values())).names
    for shop in SHOPS.values():                                     # the shop whose names appear in the prompt
        if any(n in user for n in shop.names.get('products', [])[:5]):
            names = shop.names
    return json.dumps(scripted_intent(q, as_of, names), ensure_ascii=False)


class FakeQwen(llm.FnBackend):
    def __init__(self, *a, **k):
        super().__init__(fake_generate)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-root', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--sql', action='store_true')
    ap.add_argument('--compact', action='store_true')
    ap.add_argument('--calibration', default='')
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    root = Path(args.train_root)
    for d in sorted((root / 'data').iterdir()):
        SHOPS[d.name] = load_shop_cached(d, d.name, '/tmp/cache')
    llm.QwenBackend = FakeQwen
    from datamate import predict
    argv = ['--data-root', str(root), '--questions', str(root / 'questions.jsonl'), '--model', 'fake',
            '--out', str(Path(args.out) / 'submission.jsonl'), '--log-dir', str(Path(args.out) / 'logs'),
            '--no-llm-mapper']
    if args.sql:
        argv.append('--sql')
    if args.compact:
        argv += ['--prompt', 'compact']
    if args.calibration:
        argv += ['--calibration', args.calibration]
    if args.resume:
        argv.append('--resume')
    predict.main(argv)


if __name__ == '__main__':
    main()
