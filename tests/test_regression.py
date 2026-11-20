"""Regression guard: libraries + scripted intent must not lose points on train shops.
Set DATAMATE_TRAIN=/path/to/train (with data/, questions.jsonl, calendar.csv, answers jsonl)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRAIN = Path(os.environ.get('DATAMATE_TRAIN', '/home/claude/data/train'))
FLOOR = {'biz_101': 40, 'biz_103': 113, 'biz_104': 119, 'biz_106': 119}


@pytest.mark.skipif(not (TRAIN / 'questions.jsonl').exists(), reason='train data not available')
def test_no_regression(tmp_path):
    answers = next(TRAIN.glob('answers*.jsonl'))
    shops = [b for b in FLOOR if (TRAIN / 'data' / b).exists()]
    subprocess.run([sys.executable, str(ROOT / 'tests/run_shops.py'), '--train-root', str(TRAIN), '--answers', str(answers),
                    '--out', str(tmp_path), '--cache', os.environ.get('DATAMATE_CACHE', '/tmp/shopcache'), *shops],
                   check=True, capture_output=True)
    for b in shops:
        rows = json.loads((tmp_path / f'{b}.json').read_text(encoding='utf-8'))
        score = sum(r['verdict'] == 'correct' for r in rows) - sum(r['verdict'] == 'wrong' for r in rows)
        assert score >= FLOOR[b], (b, score)
