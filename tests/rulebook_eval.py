"""Measure the rulebook gate (datamate.rulebook.Gate) on train questions of the non-held-out shops. CPU only.

python tests/rulebook_eval.py --results <dir of tests/run_shops.py results> [--loro] [--show]

--loro  leave-one-rule-out: each train rule implemented by a metric is treated in turn as 'new' (its own words removed
        from the train vocabulary) -> how many questions of that metric the gate catches (recall) and how many other
        questions it catches by mistake (false catch rate). Labels = metric of the scripted intent (not clean).
default the real gate of the train rulebook (only 'uncovered' rules) -> which questions it catches and their current
        scripted verdicts (what abstaining on them would change).
Held-out shops of kaggle/config.json are refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.intent import METRIC_DOC                              # noqa: E402
from datamate.normalize import norm                                # noqa: E402
from datamate.rulebook import Gate, compare, load_base, parse      # noqa: E402

VALUE = {'correct': 1, 'wrong': -1, 'abstain': 0}


def load_rows(results: Path, hold: set) -> list[dict]:
    rows = []
    for f in sorted(results.glob('biz_*.json')):
        if f.name.endswith('.meta.json') or f.stem in hold:
            continue
        for r in json.loads(f.read_text(encoding='utf-8')):
            r['biz'] = f.stem
            r['qn'] = norm(r['question'])
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    ap.add_argument('--rulebook', default=str(ROOT / 'data' / 'train' / 'rulebook.md'))
    ap.add_argument('--loro', action='store_true')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--t-hi', type=float, default=0.8)
    a = ap.parse_args()
    hold = set(json.loads((ROOT / 'kaggle' / 'config.json').read_text(encoding='utf-8')).get('val_shops') or [])
    rows = load_rows(Path(a.results), hold)
    base = load_base()
    status, _ = compare(parse(Path(a.rulebook)), base)
    print(f'{len(rows)} câu, {len({r["biz"] for r in rows})} shop (bỏ shop giữ kín)')
    if not a.loro:
        gate = Gate(status, base, t_hi=a.t_hi)
        hits = [(r, gate.check(r['qn'])) for r in rows]
        hits = [(r, h) for r, h in hits if h]
        c = Counter(r['verdict'] for r, _ in hits)
        lost = sum(VALUE[r['verdict']] for r, _ in hits)
        print(f'cổng (rulebook train, chỉ mục chưa phủ) bắt {len(hits)} câu: {dict(c)} → bỏ trống đổi điểm {-lost:+d}')
        for rule, n in Counter(h['rule'] for _, h in hits).most_common():
            print(f'  {n:4d}  {rule}')
        if a.show:
            for r, h in hits:
                print(f"  [{h['phrase']}] {r['biz']} {r['verdict']}: {r['question'][:100]}")
        return
    metrics = set(METRIC_DOC)
    tot_fp, tot_q, recalls = 0, 0, []
    print(f'{"mục luật":45s} {"metric":28s} {"câu":>5s} {"bắt đúng":>8s} {"bắt nhầm":>8s}')
    for s in status:
        r = s['rule']
        mets = set((s['base'] or {}).get('covered_by') or []) & metrics
        if not mets or r.section_no in (7, 8, 9):
            continue
        base_minus = {'rules': [b for b in base['rules'] if b['key'] != r.key]}
        gate = Gate(status, base_minus, t_hi=a.t_hi, only={r.key})
        pos = [x for x in rows if (x.get('intent') or {}).get('metric') in mets]
        tp = sum(bool(gate.check(x['qn'])) for x in pos)
        fp_rows = [x for x in rows if (x.get('intent') or {}).get('metric') not in mets and gate.check(x['qn'])]
        tot_fp += len(fp_rows)
        tot_q += len(rows) - len(pos)
        if pos and mets != {'revenue'}:
            recalls.append(tp / len(pos))
        name = (r.title or r.body)[:45]
        print(f'{name:45s} {",".join(sorted(mets))[:28]:28s} {len(pos):5d} {tp:8d} {len(fp_rows):8d}')
        if a.show:
            for x in fp_rows[:3]:
                print(f"      nhầm: {(x.get('intent') or {}).get('metric')} | {x['question'][:90]}")
    print(f'\nbắt đúng trung bình (bỏ mục chỉ có revenue): {sum(recalls) / max(len(recalls), 1):.2f} trên {len(recalls)} mục')
    print(f'bắt nhầm: {tot_fp} lượt / {tot_q} lượt câu-khác = {100 * tot_fp / max(tot_q, 1):.2f}%')


if __name__ == '__main__':
    main()
