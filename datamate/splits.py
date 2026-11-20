"""Deterministic shop-level splits (every question of a shop stays on one side).

The split depends only on the shop id hash, never on scores, so it is stable across runs
and machines. Optionally stratified by schema signature (which concepts the shop data has),
so the validation side contains every kind of shop that train has more than one of.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _h(name: str, seed: str) -> str:
    return hashlib.sha1(f'{seed}:{name}'.encode()).hexdigest()


def shop_split(shops, val_frac: float = 0.2, seed: str = 'datamate-v6', signatures: dict | None = None):
    """Return (train_shops, val_shops)."""
    shops = sorted(set(shops))
    if not shops:
        return [], []
    groups = {}
    for s in shops:
        groups.setdefault((signatures or {}).get(s, '*'), []).append(s)
    val = []
    for _, members in sorted(groups.items()):
        members = sorted(members, key=lambda s: _h(s, seed))
        n = round(len(members) * val_frac)
        if len(members) >= 2:
            n = max(n, 1) if len(members) >= 3 else n
        val += members[:n]
    if not val and len(shops) > 1:
        val = [sorted(shops, key=lambda s: _h(s, seed))[0]]
    return [s for s in shops if s not in val], sorted(val)


def kfold(shops, k: int, seed: str = 'datamate-v6'):
    shops = sorted(set(shops), key=lambda s: _h(s, seed))
    return [sorted(shops[i::k]) for i in range(k)]


def save_split(path, train, val, **meta):
    Path(path).write_text(json.dumps({'train': train, 'val': val, **meta}, indent=1), encoding='utf-8')


def load_split(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    return d['train'], d['val']
