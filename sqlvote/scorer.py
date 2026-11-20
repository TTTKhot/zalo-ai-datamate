"""Rulebook §9 scorer: +1 correct, -1 wrong, 0 abstain. Strict on type and format."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .text import norm_key


def read_jsonl(path) -> list[dict]:
    with Path(path).open(encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _num_eq(a, b) -> bool:
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        return False
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-6 + 1e-9 * abs(float(b)))


def _name_eq(a, expected, aliases) -> bool:
    return isinstance(a, str) and norm_key(a) in {norm_key(expected), *(norm_key(x) for x in aliases or [])}


def _cell_eq(a, expected, aliases) -> bool:
    if isinstance(expected, bool):
        return a is expected
    if isinstance(expected, (int, float)):
        return _num_eq(a, expected)
    return _name_eq(a, expected, aliases)


def is_correct(pred: dict, gold: dict) -> bool:
    gtype, ptype = gold['type'], pred.get('type')
    if gtype == 'unanswerable':
        return ptype == 'unanswerable'
    if ptype != gtype:
        return False
    answer, expected, aliases = pred.get('answer'), gold['answer'], gold.get('alias') or []
    if gtype in ('number', 'percent'):
        return _num_eq(answer, expected)
    if gtype == 'boolean':
        return answer is expected
    if gtype == 'date':
        return answer == expected
    if gtype == 'string':
        return _name_eq(answer, expected, aliases)
    if gtype == 'list':
        if not isinstance(answer, list) or len(answer) != len(expected):
            return False
        return all(_cell_eq(a, e, aliases[i] if i < len(aliases) and isinstance(aliases[i], list) else [])
                   for i, (a, e) in enumerate(zip(answer, expected)))
    if gtype == 'table':
        if not isinstance(answer, dict) or not isinstance(answer.get('rows'), list):
            return False
        rows, want = list(answer['rows']), expected['rows']
        if len(rows) != len(want):
            return False
        for i, w in enumerate(want):                 # row order is free: match each gold row once
            alias = aliases[i] if i < len(aliases) and isinstance(aliases[i], list) else []
            hit = next((r for r in rows if isinstance(r, list) and len(r) == len(w) and _cell_eq(r[0], w[0], alias)
                        and all(_cell_eq(a, e, []) for a, e in zip(r[1:], w[1:]))), None)
            if hit is None:
                return False
            rows.remove(hit)
        return True
    return False


def score(preds: list[dict], golds: list[dict]) -> dict:
    by_id = {p['id']: p for p in preds}
    out = {'n': len(golds), 'correct': 0, 'wrong': 0, 'abstain': 0, 'by_type': {}}
    for g in golds:
        p = by_id.get(g['id'])
        bucket = out['by_type'].setdefault(g['type'], {'n': 0, 'correct': 0, 'wrong': 0, 'abstain': 0})
        bucket['n'] += 1
        if p is None or p.get('type') == 'abstain':
            verdict = 'abstain'
        else:
            verdict = 'correct' if is_correct(p, g) else 'wrong'
        out[verdict] += 1
        bucket[verdict] += 1
    out['pa'] = round((out['correct'] - out['wrong']) / max(out['n'], 1), 4)
    return out
