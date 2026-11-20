"""Few-shot bank: training questions with a SQL that reproduced the gold answer (rejection sampling).

Retrieval is character-trigram TF-IDF on accent-free text with digits masked, so 'thang 6/2025' and
'tháng 7/2026' look alike and the neighbours are questions of the same shape. No model, no parameters.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .text import plain


def _grams(text: str) -> dict:
    s = ' ' + re.sub(r'\d', '0', plain(text)) + ' '
    out: dict = {}
    for i in range(len(s) - 2):
        g = s[i:i + 3]
        out[g] = out.get(g, 0) + 1
    return out


class Bank:
    def __init__(self, entries: list[dict]):
        self.entries = entries
        grams = [_grams(e['question']) for e in entries]
        df: dict = {}
        for g in grams:
            for k in g:
                df[k] = df.get(k, 0) + 1
        n = max(len(entries), 1)
        self.idf = {k: math.log(1 + n / v) for k, v in df.items()}
        self.vecs = [self._vec(g) for g in grams]

    @classmethod
    def load(cls, path) -> 'Bank':
        path = Path(path)
        entries = []
        if path.exists():
            with path.open(encoding='utf-8') as fh:
                entries = [json.loads(line) for line in fh if line.strip()]
        return cls(entries)

    def _vec(self, grams: dict) -> dict:
        vec = {k: c * self.idf.get(k, 0.0) for k, c in grams.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    def retrieve(self, question: str, k: int = 4, exclude_shops=(), exclude_ids=()) -> list[dict]:
        """k nearest verified examples, most similar LAST (closest to the question in the prompt).
        At most 2 examples per shop so that one shop's column names do not dominate."""
        if not self.entries or k <= 0:
            return []
        q = self._vec(_grams(question))
        scored = []
        for i, (entry, vec) in enumerate(zip(self.entries, self.vecs)):
            if entry.get('shop') in exclude_shops or entry.get('id') in exclude_ids:
                continue
            small, large = (q, vec) if len(q) < len(vec) else (vec, q)
            scored.append((sum(v * large.get(g, 0.0) for g, v in small.items()), -i))
        scored.sort(reverse=True)
        picked, per_shop = [], {}
        for _, neg in scored:
            entry = self.entries[-neg]
            shop = entry.get('shop')
            if per_shop.get(shop, 0) >= 2:
                continue
            per_shop[shop] = per_shop.get(shop, 0) + 1
            picked.append(entry)
            if len(picked) == k:
                break
        return picked[::-1]
