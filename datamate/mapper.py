"""Table/column -> rulebook concept mapping.

1. `propose_heuristic` scores every (table, entity) and (column, field) pair from
   generic header vocabulary, README descriptions, value kinds and value cues.
2. `LLMMapper` shows README + schema cards + the heuristic draft to an LLM and asks
   for a JSON mapping (offline Qwen in the Docker image).
3. `validate_mapping` runs fixed checks on the real values (parse rates, key
   uniqueness, join overlap, arithmetic identities). A field the LLM proposed that
   fails is replaced by the best heuristic candidate that passes, else dropped.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .concepts import ENTITIES, Entity
from .ingest import RawTable, sheet_years
from .values import date_cue, parse_datetimes, parse_numbers, plain, split_camel

KIND_OK = {
    'id': {'id': 1.0, 'text': 0.6, 'number': 0.2, 'category': 0.4},
    'date': {'date': 1.0, 'datetime': 0.8},
    'datetime': {'datetime': 1.0, 'date': 0.3},
    'money': {'number': 1.0},
    'number': {'number': 1.0},
    'text': {'text': 1.0, 'category': 0.7, 'id': 0.2},
    'category': {'category': 1.0, 'text': 0.6, 'id': 0.2},
    'bool': {'category': 1.0, 'number': 0.5},
}
# whole words only: "tra" must not match "Trả sau" (a payment term), "the" must not match "thêm đá" (a note)
# order statuses are a closed class: every common Vietnamese / English way of writing them counts as value evidence,
# so a column whose values are all statuses beats a header that merely shares a word with "kết quả" (found by
# tests/perturb_shops.py noreadme: completed / cancelled / returned / shipping lost to the sales-channel column)
STATUS_WORDS = (r'\b(?:huy|hoan thanh|hoan tat|xong|giao|van chuyen|thanh cong|da lay|cho xac nhan|dang xu ly|done|'
                r'cancel\w*|return\w*|refund\w*|complete\w*|deliver\w*|shipping|shipped|pending|processing|success\w*)\b'
                r'|\btra\b(?! (?:sau|truoc|gop|tien|no|bang|qua)\b)')
PAYMENT_WORDS = r'\b(?:tien mat|chuyen khoan|ghi no|cod|vi dien tu|the|momo|banking|cash)\b'
UNIT_WORDS = r'^(ly|coc|chai|lon|goi|hop|cai|kg|g|thung|phan|vien|vi|bao|cay|loc|qua|bo|cuc|tuyp|lo|ong|m|m2|met|tan|cuon|to|dia|suat|phan|chiec|doi|bich)( \d+\w*)?$'


def _tokens(text: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', plain(split_camel(text)))


def header_similarity(header: str, synonyms) -> float:
    h = ' '.join(_tokens(header))
    if not h:
        return 0.0
    best = 0.0
    htoks = set(h.split())
    for syn in synonyms:
        s = ' '.join(_tokens(syn))
        if not s:
            continue
        if s == h:
            return 1.0
        stoks = set(s.split())
        if f' {s} ' in f' {h} ':
            best = max(best, 0.75 + 0.2 * len(stoks) / len(htoks))
        common = len(htoks & stoks)
        if common:
            best = max(best, 0.7 * common / max(len(htoks), len(stoks)))
    return min(best, 1.0)


def value_cue(card: dict, fld) -> float:
    vals = [plain(v) for v in (card.get('all_values') or card.get('samples') or [])]
    if not vals:
        return 0.0
    share = lambda pattern: sum(bool(re.search(pattern, v)) for v in vals) / len(vals)
    cue = 0.0
    if fld.name == 'status':
        cue += 1.5 * share(STATUS_WORDS)
    if fld.name in ('payment_method', 'method'):
        cue += 1.5 * share(PAYMENT_WORDS)
    if fld.name in ('unit', 'base_unit'):
        cue += 1.0 * share(UNIT_WORDS)
    if fld.name == 'customer_name':
        cue += 0.8 * share(r'khach le|vang lai') + 0.3 * share(r'^\w+ \w+ \w+')
    if fld.kind == 'money' and card.get('kind') == 'number':
        cue += 0.4 if card.get('hundreds_ratio', 0) > 0.8 and card.get('median', 0) >= 1000 else -0.6
    if fld.name in ('line_discount', 'order_discount') and card.get('kind') == 'number':
        # a discount column is blank or 0 on most rows; a filled money column is an amount, not a discount
        cue += 0.3 if card.get('null_ratio', 0) > 0.5 or card.get('median', 1) == 0 else -0.8
    if fld.kind == 'number' and fld.name in ('qty', 'qty_base', 'factor', 'qty_on_hand') and card.get('kind') == 'number':
        cue += 0.3 if card.get('median', 1e9) < 1000 else -0.8
    if fld.name in ('order_id', 'purchase_id', 'payment_id') and card.get('kind') in ('id', 'text'):
        cue += 0.4 if card.get('distinct', 0) > 50 else -0.5
    if fld.name in ('product_code', 'customer_code', 'supplier', 'staff') and card.get('kind') == 'id':
        cue += 0.2
    return cue


def field_score(card: dict, fld, table_rows: int) -> float:
    if card.get('kind') == 'empty' or card.get('non_null', 0) == 0:
        return -9.0
    ok = KIND_OK.get(fld.kind, {}).get(card.get('kind'), 0.0)
    if ok == 0.0:
        return -9.0
    if fld.kind in ('money', 'number') and card.get('date_rate', 0) >= 0.9:
        return -9.0                                   # a date column never plays a quantity / money role
    if card.get('kind') == 'number' and card.get('unit_rate', 0) > 0.05 and fld.name not in ('qty', 'qty_base'):
        ok *= 0.5
    head = header_similarity(card['header'], fld.syn + (fld.name.replace('_', ' '),))
    desc = header_similarity(card.get('readme', ''), fld.syn) if card.get('readme') else 0.0
    return 2.2 * head + 0.8 * desc + ok + value_cue(card, fld) - 1.0 * card.get('null_ratio', 0) * (fld.required)


@dataclass
class TableMapping:
    table: str
    entity: str | None
    columns: dict = field(default_factory=dict)     # field -> header
    score: float = 0.0
    candidates: dict = field(default_factory=dict)  # field -> [(header, score), ...]
    source: str = 'heuristic'


def required_missing(entity: Entity, columns) -> list[str]:
    """Required fields of `entity` that `columns` (field -> header) does not cover."""
    missing = [f.name for f in entity.fields if f.required and f.name not in columns]
    if entity.name == 'sales_line' and 'order_id' in missing and 'order_date' in columns:
        missing.remove('order_id')          # a hand-kept sales book: dated lines, no order number
    # entities whose required key is a product/order identity may use name OR code
    if entity.name in ('product', 'unit_conversion', 'stock_snapshot', 'purchase_line', 'price_history', 'sales_line'):
        if not ({'product_code', 'product_name'} & set(columns)):
            missing.append('product_code|product_name')
    if entity.name == 'sales_line' and not ({'line_total', 'unit_price'} & set(columns)):
        missing.append('line_total|unit_price')
    # a staff list kept by name only (service shops: full name + commission %, no code) is still a staff list,
    # but only with a commission column: a bare name list is more likely customers
    if entity.name == 'staff' and 'staff_code' in missing and {'staff_name', 'commission_pct'} <= set(columns):
        missing.remove('staff_code')
    # a service book names who did the ticket or what was serviced; an expense book (date + item + amount) does not
    if entity.name == 'service_ticket' and not ({'technician', 'vehicle'} & set(columns)):
        missing.append('technician|vehicle')
    return missing


def map_entity(profile: dict, entity: Entity) -> TableMapping:
    rows = profile['rows']
    cards = profile['columns']
    scored, candidates = [], {}
    for fld in entity.fields:
        ranked = sorted(((field_score(c, fld, rows), c['header']) for c in cards), reverse=True)
        candidates[fld.name] = [(h, round(s, 2)) for s, h in ranked[:4] if s > 0.8]
        scored.extend((s, fld.name, h) for s, h in ranked if s > 1.4)
    columns, used = {}, set()
    for s, fname, header in sorted(scored, reverse=True):
        if fname in columns or header in used:
            continue
        columns[fname] = header
        used.add(header)
    score = sum(max((s for s, f, h in scored if f == fname and h == columns[fname]), default=0)
                for fname in columns)
    missing = required_missing(entity, columns)
    name_hint = max((header_similarity(profile['table'], (h,)) for h in entity.table_hints), default=0)
    score += 2.0 * name_hint - 4.0 * len(missing)
    if entity.one_row_per and entity.one_row_per in columns:
        card = next(c for c in cards if c['header'] == columns[entity.one_row_per])
        if card.get('unique_ratio', 0) < 0.98:
            score -= 6.0
    if entity.name == 'sales_line' and 'order_id' in columns:
        card = next(c for c in cards if c['header'] == columns['order_id'])
        score += 1.0 if card.get('unique_ratio', 1) < 0.98 else 0.0
    return TableMapping(profile['table'], entity.name if not missing else None, columns,
                        round(score, 2), candidates)


SINGLETON = {'sales_line', 'order', 'product', 'unit_conversion', 'customer', 'purchase',
             'purchase_line', 'stock_snapshot', 'payment', 'expense', 'supplier', 'staff', 'price_history',
             'delivery', 'service_ticket'}


def propose_heuristic(profiles: dict) -> dict[str, TableMapping]:
    options = {}
    for name, profile in profiles.items():
        ranked = []
        for entity in ENTITIES.values():
            m = map_entity(profile, entity)
            if m.entity:
                ranked.append(m)
        options[name] = sorted(ranked, key=lambda m: -m.score)
    result, taken = {}, {}
    # resolve conflicts: each entity type at most once. Greedy over (table, entity) pairs by the pair's own score,
    # so a table's fallback role cannot take an entity from a table that fits it better.
    pairs = sorted(((m.score, name, i) for name, opts in options.items() for i, m in enumerate(opts)),
                   key=lambda t: (-t[0], t[1], t[2]))
    for score, name, i in pairs:
        m = options[name][i]
        if name in result or score < 2.0 or (m.entity in SINGLETON and m.entity in taken):
            continue
        result[name] = m
        taken[m.entity] = name
    for name in profiles:
        result.setdefault(name, TableMapping(name, None))
    return result


# ------------------------------------------------------------------ typed access
class TypedTables:
    """Parse a mapped column once, by the kind of the field it plays."""

    def __init__(self, tables: dict[str, RawTable]):
        self.tables = tables
        self.cache = {}

    def get(self, table: str, header: str, kind: str):
        key = (table, header, kind)
        if key not in self.cache:
            t = self.tables[table]
            raw = t.frame[header]
            if kind in ('date', 'datetime'):
                value = parse_datetimes(raw, sheet_years(t), allow_serial=True if date_cue(header) else None)
            elif kind in ('money', 'number'):
                value = parse_numbers(raw)[0]
            else:
                value = raw.map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v))
                                or not str(v).strip() else re.sub(r'\s+', ' ', str(v)).strip())
            self.cache[key] = value
        return self.cache[key]


# ------------------------------------------------------------------ validation
HEADER_OF_LINES = {('sales_line', 'order'), ('purchase_line', 'purchase')}


def validate_mapping(mapping: dict[str, TableMapping], typed: TypedTables) -> dict:
    """Fixed checks; returns {'issues': [...], 'dropped': [(table, field, reason)]} and edits mapping."""
    issues, dropped = [], []
    by_entity = {m.entity: m for m in mapping.values() if m.entity}

    def drop(m, fname, reason):
        dropped.append((m.table, fname, reason))
        m.columns.pop(fname, None)

    for m in by_entity.values():
        entity = ENTITIES[m.entity]
        for fname, header in list(m.columns.items()):
            fld = entity.field(fname)
            values = typed.get(m.table, header, fld.kind)
            raw = typed.tables[m.table].frame[header]
            present = raw.map(lambda v: v is not None and not (isinstance(v, float) and np.isnan(v)) and str(v).strip() != '')
            if present.sum() == 0:
                drop(m, fname, 'empty column')
                continue
            if fld.kind in ('date', 'datetime', 'money', 'number'):
                rate = float(values[present].notna().mean())
                if rate < 0.9:
                    drop(m, fname, f'only {rate:.0%} parse as {fld.kind}')
        if entity.one_row_per and entity.one_row_per in m.columns:
            key = typed.get(m.table, m.columns[entity.one_row_per], 'id').dropna()
            if key.duplicated().mean() > 0.02:
                issues.append(f'{m.table}.{entity.one_row_per} not unique')

    def overlap(child, cfield, parent, pfield):
        if child not in by_entity or parent not in by_entity:
            return None
        c, p = by_entity[child], by_entity[parent]
        if cfield not in c.columns or pfield not in p.columns:
            return None
        if required_missing(ENTITIES[parent], p.columns):
            return None      # this parent is dropped right after the checks: it must not veto the child's key
        return _ratio(c, cfield, p, pfield)

    def _ratio(c, cfield, p, pfield):
        cv = set(typed.get(c.table, c.columns[cfield], 'id').dropna().map(plain))
        pv = set(typed.get(p.table, p.columns[pfield], 'id').dropna().map(plain))
        return len(cv & pv) / max(len(cv), 1)

    for child, cf, parent, pf in [('sales_line', 'order_id', 'order', 'order_id'),
                                  ('payment', 'order_id', 'order', 'order_id'),
                                  ('sales_line', 'product_code', 'product', 'product_code'),
                                  ('purchase_line', 'purchase_id', 'purchase', 'purchase_id'),
                                  ('purchase_line', 'product_code', 'product', 'product_code'),
                                  ('stock_snapshot', 'product_code', 'product', 'product_code'),
                                  ('sales_line', 'customer_code', 'customer', 'customer_code'),
                                  ('order', 'customer_code', 'customer', 'customer_code')]:
        ratio = overlap(child, cf, parent, pf)
        if ratio is not None and ratio < 0.8:
            issues.append(f'{child}.{cf} matches only {ratio:.0%} of {parent}.{pf}')
            if (child, parent) in HEADER_OF_LINES:
                # a real header table lists (almost) every document of its lines. A "header" whose ids are all found
                # in the lines but covers only a part of them is a SUBSET table (debts, deliveries, returns...):
                # its header role is wrong; the line table (the facts) keeps its key
                back = _ratio(by_entity[parent], pf, by_entity[child], cf)
                if back >= 0.8:
                    issues.append(f'{parent}.{pf}: a subset of {child} ({back:.0%} found) -> not the {parent} of these lines')
                    drop(by_entity[parent], pf, f'not the header of {child} ({back:.0%})')
                    continue
            drop(by_entity[child], cf, f'join overlap {ratio:.0%}')

    sl = by_entity.get('sales_line')
    if sl and {'qty', 'unit_price', 'line_total'} <= set(sl.columns):
        q = typed.get(sl.table, sl.columns['qty'], 'number')
        p = typed.get(sl.table, sl.columns['unit_price'], 'money')
        t = typed.get(sl.table, sl.columns['line_total'], 'money')
        d = typed.get(sl.table, sl.columns['line_discount'], 'money').fillna(0) if 'line_discount' in sl.columns else 0
        ok = ((q * p - d - t).abs() <= 1) | ((q * p - t).abs() <= 1)
        rate = float(ok[t.notna()].mean())
        if rate < 0.6:
            issues.append(f'sales_line: line_total = qty*unit_price-discount holds for only {rate:.0%}')
    return {'issues': issues, 'dropped': dropped}


# ------------------------------------------------------------------ LLM
MAP_SYSTEM = ('You map the tables of one Vietnamese shop export to fixed business concepts. '
              'Return only JSON: {"tables": {"<table>": {"entity": "<entity or null>", '
              '"columns": {"<field>": "<exact header>"}}}}. Use only listed entities, fields and headers. '
              'Read the README: it says which column is the line total, the order total, the unit cost, etc. '
              'Leave a field out when no column fits.')


def concept_catalogue() -> str:
    lines = []
    for e in ENTITIES.values():
        fields = '; '.join(f'{f.name}({f.kind}{", required" if f.required else ""}): {f.desc}' for f in e.fields)
        lines.append(f'- {e.name}: {e.desc} Fields: {fields}')
    return '\n'.join(lines)


def mapping_to_json(mapping: dict[str, TableMapping]) -> dict:
    return {'tables': {n: {'entity': m.entity, 'columns': dict(m.columns)} for n, m in mapping.items()}}


README_PROMPT_CHARS = 3000
COLUMN_SECTION = re.compile(r'##\s*(?:cột|cot|columns?)\b', re.I)


def readme_for_prompt(text: str, limit: int = README_PROMPT_CHARS, conventions_first: bool | None = None) -> str:
    """README text shown to the mapping LLM, cut at `limit` characters.

    A long README loses its END to the cut, and the "## Quy ước" section (how orders span lines, data end date ...)
    is usually last, after the "## Cột trong ..." sections whose column descriptions the schema cards already carry.
    With `conventions_first` (env DATAMATE_README_CONVENTIONS_FIRST=1) a README longer than `limit` is reordered:
    text before the first section, then every section that is not a column list, then the column lists; then cut.
    OFF by default until a GPU run shows the LLM mapping of long-README shops is not worse (the heuristic mapper,
    hence every CPU measure, never reads this prompt). A README within `limit` gives exactly the old text."""
    text = text or ''
    if conventions_first is None:
        conventions_first = os.environ.get('DATAMATE_README_CONVENTIONS_FIRST', '0') == '1'
    if len(text) <= limit or not conventions_first:
        return text[:limit]
    parts = re.split(r'(?m)^(?=##\s)', text)
    head, sections = parts[0], parts[1:]
    columns = [s for s in sections if COLUMN_SECTION.match(s)]
    other = [s for s in sections if not COLUMN_SECTION.match(s)]
    return (head + ''.join(other) + ''.join(columns))[:limit]


def build_prompt(profiles: dict, readme: dict, draft: dict[str, TableMapping]) -> list[dict]:
    from .profile import card_text
    cards = '\n'.join(card_text(p) for p in profiles.values())
    user = (f'README:\n{readme_for_prompt(readme.get("text", ""))}\n\nCONCEPTS:\n{concept_catalogue()}\n\n'
            f'TABLES:\n{cards}\n\nDRAFT (from header matching, may be wrong):\n'
            f'{json.dumps(mapping_to_json(draft), ensure_ascii=False)}\n\nReturn the corrected JSON.')
    return [{'role': 'system', 'content': MAP_SYSTEM}, {'role': 'user', 'content': user}]


def parse_llm_mapping(text: str) -> dict | None:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S)
    decoder = json.JSONDecoder()
    for m in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get('tables'), dict):
            return value
    return None


def merge_llm(draft: dict[str, TableMapping], llm: dict | None, profiles: dict) -> dict[str, TableMapping]:
    """Accept LLM choices that reference real tables/headers/fields; keep draft elsewhere."""
    if not llm:
        return draft
    merged = {}
    for name, m in draft.items():
        proposal = llm['tables'].get(name)
        headers = {c['header'] for c in profiles[name]['columns']}
        if not isinstance(proposal, dict):
            merged[name] = m
            continue
        entity = proposal.get('entity')
        if entity not in ENTITIES:
            entity = None if entity in (None, 'null', '') else m.entity
        cols = {}
        if entity:
            valid_fields = {f.name for f in ENTITIES[entity].fields}
            for fname, header in (proposal.get('columns') or {}).items():
                if fname in valid_fields and header in headers and header not in cols.values():
                    cols[fname] = header
            if entity == m.entity:
                for fname, header in m.columns.items():      # keep draft fields the LLM omitted
                    if fname not in cols and header not in cols.values():
                        cols[fname] = header
        merged[name] = TableMapping(name, entity, cols, m.score, m.candidates, 'llm')
    return merged


ATTR_FIELDS = {'is_prescription': re.compile(r'\bke don\b|\bban theo don\b|^rx$'),
               'active_ingredient': re.compile(r'\bhoat chat\b|\bthanh phan\b')}
ATTR_CODE = re.compile(r'^(?:ma|sku|id)\b|\bsku\b|^ma (?:hang|sp|san pham|thuoc|hh|vt)\b')


def product_attribute_tables(profiles: dict, mapping: dict[str, TableMapping], log=None) -> list[dict]:
    """Side tables that only add product attributes (e.g. a drug list: code, active ingredient, prescription flag).
    They have no product name, so they cannot play `product`; they are joined to the catalogue by code."""
    attrs = []
    for name, p in profiles.items():
        m = mapping.get(name)
        if m is None or m.entity == 'product':
            continue
        headers = [c['header'] for c in p['columns']]
        found = {}
        for fname, rx in ATTR_FIELDS.items():
            h = next((h for h in headers if rx.search(plain(split_camel(h)))), None)
            if h:
                found[fname] = h
        codes = [h for h in headers if ATTR_CODE.search(plain(split_camel(h))) and h not in found.values()]
        code = codes[0] if codes else None             # rules picks among `codes` by overlap with the catalogue
        if not found or not code or (m.entity and len(m.columns) > 2):
            continue                                   # a real table of another kind keeps its role
        if m.entity and log is not None:
            log.append(f'{name}: product attribute table (was {m.entity})')
        mapping[name] = TableMapping(name, None, {}, m.score, m.candidates, m.source)
        attrs.append({'table': name, 'code': code, 'codes': codes, **found})
    return attrs


# "STT", "Số TT", "Số thứ tự", "TT", "Thứ tự", "HĐ", "Số HĐ", "Số đơn", "Đơn số" (+ "đơn" / "hoá đơn" / "phiếu")
ORDER_NUMBER_HEADER = re.compile(r'(?:so )?(?:stt|tt|thu tu|so thu tu|hd|so hd|so don|don so)'
                                 r'(?: (?:don|hoa don|hd|phieu|don hang))?')


def order_number_blocks(values: pd.Series, groups: pd.Series) -> dict:
    """Shape of a numbered column inside each file/sheet (blank cells repeat the cell above, §8). An order number
    of a hand-kept book is one contiguous block of rows per number, numbers going up; a line number inside an order
    (1, 2, 1, 1, 2, 3 ...) repeats the same few numbers in many separate blocks; a row number never repeats."""
    v = pd.to_numeric(values, errors='coerce').groupby(groups, sort=False).ffill()
    runs = dist = rows = multi_rows = multi_runs = up = steps = 0
    for _, s in v.groupby(groups, sort=False):
        s = s.dropna()
        if len(s) < 2:
            continue
        size = (s != s.shift()).cumsum().value_counts()
        runs += len(size)
        dist += s.nunique()
        rows += len(s)
        multi_rows += int(size[size > 1].sum())
        multi_runs += int((size > 1).sum())
        d = s.diff().dropna()
        d = d[d != 0]
        steps += len(d)
        up += int((d > 0).sum())
    return {'filled': round(float(v.notna().mean()), 3) if len(v) else 0.0,
            'one_block_per_number': round(dist / max(runs, 1), 3), 'increasing': round(up / max(steps, 1), 3),
            'multi_line_orders': multi_runs, 'multi_line_rows': round(multi_rows / max(rows, 1), 3)}


def order_number_column(tables, profile: dict, m: TableMapping, typed: TypedTables) -> str | None:
    """A sales book without an order id whose order-number column ("STT: số thứ tự đơn") was not recognised:
    a header of the STT / HĐ family whose values form one block of rows per number, numbers going up, with enough
    orders of several lines. The README description, when it says the number is a LINE number ("số thứ tự dòng"),
    rules the column out. The key is made per file/sheet later (rules.build_views) when numbers restart."""
    t = tables[m.table]
    # a column the draft gave a required role keeps it; an optional role (an "STT" read as qty_base) is given up
    required = {f.name for f in ENTITIES[m.entity].fields if f.required}
    used = {h for f, h in m.columns.items() if f in required}
    groups = t.frame['_file'].astype(str) + ':' + t.frame['_sheet'].astype(str)
    for card in profile['columns']:
        h = card['header']
        if h in used or not ORDER_NUMBER_HEADER.fullmatch(' '.join(_tokens(h))):
            continue
        if re.search(r'\bdong\b', plain(card.get('readme') or '')):
            continue
        shape = order_number_blocks(typed.get(m.table, h, 'number'), groups)
        if shape['filled'] >= 0.9 and shape['one_block_per_number'] >= 0.98 and shape['increasing'] >= 0.95 \
                and shape['multi_line_orders'] >= 5 and shape['multi_line_rows'] >= 0.1:
            return h
    return None


def resolve_mapping(tables, profiles, readme, backend=None, log=None) -> tuple[dict, dict]:
    draft = propose_heuristic(profiles)
    mapping = draft
    if backend is not None:
        try:
            raw = backend.generate(build_prompt(profiles, readme, draft))
            mapping = merge_llm(draft, parse_llm_mapping(raw), profiles)
        except Exception as exc:                       # the draft still stands
            if log is not None:
                log.append(f'LLM mapping failed: {type(exc).__name__}: {exc}')
    attrs = product_attribute_tables(profiles, mapping, log)
    typed = TypedTables(tables)
    report = validate_mapping(mapping, typed)
    # refill dropped fields from heuristic candidates that pass the same checks
    for table, fname, _ in report['dropped']:
        m = mapping[table]
        used = set(m.columns.values())
        for header, _score in m.candidates.get(fname, []):
            if header in used:
                continue
            m.columns[fname] = header
            again = validate_mapping({table: m, **{k: v for k, v in mapping.items() if k != table}}, typed)
            if not any(d[0] == table and d[1] == fname for d in again['dropped']):
                break
            m.columns.pop(fname, None)
    # a table that lost a required column in the checks no longer plays its entity (views need those keys)
    for m in mapping.values():
        if m.entity:
            missing = required_missing(ENTITIES[m.entity], m.columns)
            if missing:
                report['issues'].append(f'{m.table}: dropped as {m.entity}, missing {missing} after checks')
                if log is not None:
                    log.append(f'{m.table}: not used as {m.entity} (missing {missing})')
                m.entity = None
    # a sales book numbering its orders (STT) instead of an order code: that number is the order id
    if not any(m.entity == 'order' for m in mapping.values()):
        for m in mapping.values():
            if m.entity == 'sales_line' and 'order_id' not in m.columns:
                h = order_number_column(tables, profiles[m.table], m, typed)
                if h is not None:
                    for f in [f for f, x in m.columns.items() if x == h]:
                        m.columns.pop(f)
                        report['issues'].append(f'{m.table}: {h!r} is an order number, not {f}')
                    m.columns['order_id'] = h
                    report['issues'].append(f'{m.table}: order number column {h!r} used as order id')
                    if log is not None:
                        log.append(f'{m.table}: order id = order number column {h!r} (one block of lines per number)')
    return mapping, {'report': report, 'typed': typed, 'product_attrs': attrs}
