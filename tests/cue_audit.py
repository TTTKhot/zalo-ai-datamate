"""How much each cue group of slots.apply_cues helps or hurts, on logged Qwen outputs (no GPU).

python tests/cue_audit.py runs/<stamp> [runs/<stamp2> ...] [--run v5_sql] [--show hurt|all|none]

For every logged question (held-out shops of kaggle/config.json `val_shops` are skipped), the logged llm_raw is
replayed through the current code (metric route only, no SQL) once with every cue and once per cue group with
that group switched off. A group "helps" a question when the answer is correct with it and not correct without it,
"hurts" in the opposite case. Score delta uses +1 / -1 / 0. Table mapping is rebuilt with heuristics (as replay.py).
"""
from __future__ import annotations

import argparse
import collections
import functools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import datamate.pipeline as pipeline                       # noqa: E402
from datamate import slots                                 # noqa: E402
from datamate.llm import ReplayBackend                     # noqa: E402
from datamate.normalize import norm                        # noqa: E402
from datamate.periods import Calendar                      # noqa: E402
from datamate.scoring import is_correct, to_submission     # noqa: E402

VALUE = {'correct': 1, 'wrong': -1, 'abstain': 0}


def verdict(out, g):
    raw = dict(out, status=out.get('original_status', out.get('status')))
    sub = to_submission(raw)
    if sub['type'] == 'abstain':
        return 'abstain'
    return 'correct' if is_correct(sub, g) else 'wrong'


def run_with(shop, q, raw, cal, skip):
    pipeline.apply_cues = functools.partial(slots.apply_cues, skip=skip)
    try:
        fn = pipeline.llm_intent_fn(ReplayBackend(raw), norm)
        return pipeline.answer(shop, q, fn, cal)
    finally:
        pipeline.apply_cues = slots.apply_cues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--run', dest='name', default='v5_sql')
    ap.add_argument('--train', default=str(ROOT / 'data' / 'train'))
    ap.add_argument('--show', choices=['hurt', 'all', 'none'], default='hurt')
    a = ap.parse_args()
    train = Path(a.train)
    hold = set(json.loads((ROOT / 'kaggle' / 'config.json').read_text(encoding='utf-8')).get('val_shops') or [])
    gold = {r['id']: r for r in map(json.loads, (train / 'answers.jsonl').read_text(encoding='utf-8').splitlines()) if r}
    qs = {q['id']: q for q in map(json.loads, (train / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines()) if q}
    cal = Calendar(train / 'calendar.csv')
    help_, hurt, delta, fired = (collections.Counter() for _ in range(4))
    shops, n = {}, 0
    for run in a.runs:
        logs = Path(run) / 'state' / f'run_{a.name}' / 'logs'
        for bdir in sorted(p for p in logs.iterdir() if p.is_dir() and p.name not in hold):
            if bdir.name not in shops:
                shops[bdir.name] = pipeline.load_shop(train / 'data' / bdir.name, bdir.name)
            shop = shops[bdir.name]
            for f in sorted(bdir.glob('*.json')):
                if f.name == 'shop_report.json':
                    continue
                log = json.loads(f.read_text(encoding='utf-8'))
                q, g = qs.get(log['id']), gold.get(log['id'])
                if q is None or g is None or not log.get('llm_raw'):
                    continue
                n += 1
                base = verdict(run_with(shop, q, log['llm_raw'], cal, ()), g)
                for grp in slots.CUE_GROUPS:
                    v = verdict(run_with(shop, q, log['llm_raw'], cal, (grp,)), g)
                    if v == base:
                        continue
                    fired[grp] += 1
                    delta[grp] += VALUE[base] - VALUE[v]
                    if base == 'correct':
                        help_[grp] += 1
                    elif v == 'correct':
                        hurt[grp] += 1
                    if a.show == 'all' or (a.show == 'hurt' and v == 'correct'):
                        print(f'  [{grp}] {bdir.name} {Path(run).name}: có cue {base}, bỏ cue {v} | {q["question"][:90]}')
    print(f'\n{n} câu (bỏ shop giữ kín {sorted(hold)})')
    print(f'{"nhóm cue":16s} {"đổi kq":>6s} {"giúp":>5s} {"hại":>5s} {"điểm ròng":>9s}')
    for grp in slots.CUE_GROUPS:
        print(f'{grp:16s} {fired[grp]:6d} {help_[grp]:5d} {hurt[grp]:5d} {delta[grp]:+9d}')


if __name__ == '__main__':
    main()
