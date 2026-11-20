"""Schema cards: what an LLM (and the heuristic proposer) sees about each table."""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from .ingest import RawTable, readme_description
from .values import date_cue, is_blank, parse_datetimes, parse_numbers, plain, has_time_component

ID_PATTERN = re.compile(r'^[A-Za-z]{1,8}[-_ ]?\d{2,}$')


def profile_column(series: pd.Series, header: str, readme_desc: str = '', sample_rows: int = 5000) -> dict:
    values = series[~series.map(is_blank)]
    n = len(series)
    sample = values.head(sample_rows)
    card = {'header': header, 'non_null': int(len(values)),
            'null_ratio': round(1 - len(values) / n, 3) if n else 1.0}
    if sample.empty:
        card.update(kind='empty', distinct=0, samples=[])
        return card
    as_text = sample.map(lambda v: str(v).strip())
    distinct = int(values.map(lambda v: str(v).strip()).nunique())
    numbers, units = parse_numbers(sample)
    num_rate = float(numbers.notna().mean())
    unit_rate = float(units.notna().mean())
    dates = parse_datetimes(sample)
    date_rate = float(dates.notna().mean())
    if date_rate < 0.9 and date_cue(header, readme_desc):
        # column named as a date: Excel serial days and mixed formats (1/1, 45658, 1 thg 1 2025)
        serial = parse_datetimes(sample, allow_serial=True)
        if serial.notna().mean() >= 0.9:
            dates, date_rate, num_rate = serial, float(serial.notna().mean()), 0.0
    id_rate = float(as_text.str.match(ID_PATTERN).mean())
    if date_rate >= 0.9 and not (num_rate >= 0.9 and unit_rate < 0.05 and numbers.max() < 20000):
        kind = 'datetime' if has_time_component(dates) else 'date'
    elif num_rate >= 0.9:
        kind = 'number'
    elif id_rate >= 0.9:
        kind = 'id'
    elif distinct <= 30 and distinct < 0.2 * max(len(values), 1):
        kind = 'category'
    else:
        kind = 'text'
    card.update(kind=kind, distinct=distinct, unique_ratio=round(distinct / max(len(values), 1), 3),
                num_rate=round(num_rate, 3), date_rate=round(date_rate, 3), id_rate=round(id_rate, 3),
                unit_rate=round(unit_rate, 3))
    if kind == 'number':
        nums = numbers.dropna()
        card.update(min=float(nums.min()), max=float(nums.max()), median=float(nums.median()),
                    integer_ratio=round(float((nums == nums.round()).mean()), 3),
                    hundreds_ratio=round(float((nums % 100 == 0).mean()), 3))
        if unit_rate > 0:
            card['units_in_values'] = sorted(units.dropna().map(str).unique().tolist())[:10]
    if kind in ('date', 'datetime'):
        card.update(min=str(dates.min())[:19], max=str(dates.max())[:19])
    counts = Counter(as_text)
    card['samples'] = [v for v, _ in counts.most_common(6)]
    if distinct <= 15:
        card['all_values'] = sorted(values.map(lambda v: str(v).strip()).unique().tolist())
    if kind == 'id':
        prefixes = Counter(re.match(r'^[A-Za-z]*', v).group(0).upper() for v in as_text)
        card['prefix'] = prefixes.most_common(1)[0][0]
    if readme_desc:
        card['readme'] = readme_desc
    return card


def profile_table(table: RawTable, readme: dict | None = None) -> dict:
    columns = [profile_column(table.frame[h], h, readme_description(readme or {}, table.name, h))
               for h in table.headers]
    return {'table': table.name, 'rows': int(len(table.frame)), 'sources': table.sources[:6],
            'n_sources': len(table.sources), 'columns': columns}


def profile_business(tables: dict[str, RawTable], readme: dict | None = None) -> dict:
    return {name: profile_table(t, readme) for name, t in tables.items()}


def card_text(profile: dict, max_samples: int = 4) -> str:
    """Compact text card for an LLM prompt."""
    lines = [f"TABLE {profile['table']} ({profile['rows']} rows; files: {', '.join(profile['sources'][:3])})"]
    for c in profile['columns']:
        extra = ''
        if c['kind'] == 'number':
            extra = f" range {c.get('min'):g}..{c.get('max'):g}"
        elif c['kind'] in ('date', 'datetime'):
            extra = f" {c.get('min')}..{c.get('max')}"
        vals = c.get('all_values') or c.get('samples', [])[:max_samples]
        text = f"  - \"{c['header']}\" [{c['kind']}, distinct={c.get('distinct')}, null={c['null_ratio']}]{extra} e.g. {vals}"
        if c.get('readme'):
            text += f"  README: {c['readme']}"
        lines.append(text)
    return '\n'.join(lines)
