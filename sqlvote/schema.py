"""Schema text for the prompt + data values that match a question (accent-insensitive)."""
from __future__ import annotations

import math

from .text import tokens


def _fmt_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f'{v:.4g}'


def schema_text(meta: dict, max_listed_chars: int = 420) -> str:
    out = []
    for t in meta['tables']:
        head = f'TABLE {t["name"]}  -- {t["rows"]} dòng; nguồn: {", ".join(t["sources"][:3])}'
        if len(t['sources']) > 3:
            head += f' (+{len(t["sources"]) - 3} sheet/file cùng cấu trúc)'
        lines, empty = [head], []
        for c in t['columns']:
            p = c.get('profile', {})
            if t['rows'] and p.get('nulls') == t['rows']:
                empty.append(c['name'])
                continue
            doc = []
            if c.get('orig') and c['orig'] != c['name']:
                doc.append(f'"{c["orig"]}"')
            if c.get('desc'):
                doc.append(c['desc'])
            if c.get('status_map'):
                pairs = '; '.join(f'{k}→{v}' for k, v in c['status_map'].items())
                doc.append(f'ánh xạ: {pairs[:max_listed_chars]}')
            elif 'listed' in p:
                vals = '; '.join(f'{v} ({n})' for v, n in p['listed'])
                doc.append(f'giá trị: {vals[:max_listed_chars]}')
            elif 'examples' in p:
                doc.append(f'{p["distinct"]} giá trị khác nhau, vd: {"; ".join(e[:40] for e in p["examples"])}')
            elif 'min' in p:
                lo, hi = p['min'], p['max']
                doc.append(f'{lo} .. {hi}' if isinstance(lo, str) else f'{_fmt_num(lo)} .. {_fmt_num(hi)}')
            if p.get('nulls'):
                doc.append(f'{p["nulls"]} ô trống')
            lines.append(f'  {c["name"]} {c["type"]}' + (f'  -- {" | ".join(doc)}' if doc else ''))
        if empty:
            lines.append(f'  (cột rỗng hoàn toàn, bỏ qua: {", ".join(empty)})')
        for note in t.get('notes', []):
            lines.append(f'  # {note}')
        out.append('\n'.join(lines))
    return '\n\n'.join(out)


class ValueIndex:
    """Finds product / customer / supplier names in the data that the question mentions.

    Only columns too long to list in the schema are indexed. Matching ignores accents and case, so
    'mi omachi suon ham' finds 'Mì Omachi sườn hầm'."""

    def __init__(self, meta: dict):
        self.columns = []
        for t in meta['tables']:
            for c in t['columns']:
                p = c.get('profile', {})
                values = p.get('values')
                if not values or 'listed' in p or c.get('status_map'):
                    continue
                toks = [tokens(v) for v in values]
                df: dict = {}
                for ts in toks:
                    for tok in set(ts):
                        df[tok] = df.get(tok, 0) + 1
                n = len(values)
                idf = {tok: math.log(1 + n / k) for tok, k in df.items()}
                self.columns.append((f'{t["name"]}.{c["name"]}', values, toks, idf))

    def match(self, question: str, per_column: int = 5, min_score: float = 0.6, max_columns: int = 6) -> str:
        q = set(tokens(question))
        found = []
        for label, values, toks, idf in self.columns:
            scored = []
            for value, ts in zip(values, toks):
                if not ts or not (q & set(ts)):
                    continue
                total = sum(idf[t] for t in set(ts))
                hit = sum(idf[t] for t in set(ts) if t in q)
                score = hit / total if total else 0.0
                if score >= min_score:
                    scored.append((score, len(ts), value))
            if scored:
                scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
                found.append((scored[0][0], label, [v for _, _, v in scored[:per_column]]))
        found.sort(key=lambda x: (-x[0], x[1]))
        return '\n'.join(f'- {label}: ' + ' | '.join(f"'{v}'" for v in vals) for _, label, vals in found[:max_columns])
