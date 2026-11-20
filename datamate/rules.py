"""Rule library: canonical tables built once from a validated mapping.

Every rule below is a sentence of the rulebook applied to concepts, never to a
named shop: inherited blank cells (§8), totals rows, duplicate lines in an order (§8),
four statuses and whole-order returns (§1), base units (§3, §10), customer identity (§3),
walk-in customers, debts per order (§4), purchases and stock (§5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from .concepts import ENTITIES
from .mapper import TableMapping, TypedTables
from .values import name_key, parse_numbers, plain

WALK_IN = {'', 'khachle', 'khachvanglai', 'vanglai', 'le', 'walkin', 'khach', 'khachhangle', 'kl', 'khle', 'kvl'}
TOTAL_ROW = re.compile(r'^\s*(tong|cong|total|subtotal|tong cong|tong ngay|tong thang)\b')
PHONE_SUFFIX = re.compile(r'\s*(?:[-–(]\s*)?\(?\+?\d[\d .]{7,}\d\)?\s*$')
SERVICE_FEE = re.compile(r'^phi phuc vu|^service (fee|charge)')
NON_ITEM_LINE = re.compile(r'^(?:phi (?:ship|giao|van chuyen|gui hang)|tien (?:ship|giao hang|van chuyen)|ship(?:ping)?\b|'
                           r'van chuyen|voucher|ma giam gia|giam gia|khuyen mai|chiet khau|dung diem|tru diem|doi diem|'
                           r'discount|coupon)')


def canonical_status(value) -> str | None:
    text = plain(value)
    if not text:
        return None
    # whole words only: "huy" is inside "van CHUYen", "tra" inside many payment words ("tra sau", "tra gop")
    if re.search(r'tra hang|doi tra|hoan tra|hoan hang|tra lai|tra ve|return|refund|'
                 r'\bkhach (?:hang )?(?:da )?tra\b(?! (?:tien|no|truoc|sau|gop|du|het|them|coc))|'
                 r'^(?:da |bi )?(?:tra|hoan)$|\bhoan (?:don|lai)\b', text):
        return 'trả hàng'
    if re.search(r'\b(?:huy|cancel\w*|void\w*|bom|fail\w*)\b|that bai|khong giao duoc|khong thanh cong', text):
        return 'huỷ'
    if re.search(r'\bda (?:giao|nhan|chot)\b|giao thanh cong|\bdelivered\b', text):     # "Đã giao hàng", "Đã chốt"
        return 'hoàn thành'
    if re.search(r'dang giao|giao hang|van chuyen|shipping|delivering|dang xu ly|\bcho\b', text):
        return 'đang giao'
    return 'hoàn thành'


STATUS_FILTER = (('trả hàng', r'tra hang|tra lai|hoan tra|hoan hang|doi tra|\b(?:return\w*|refund\w*)\b'),
                 ('huỷ', r'\b(?:huy|cancel\w*|bom)\b'),
                 ('đang giao', r'dang giao|van chuyen|dang xu ly|\b(?:shipping|delivering|pending|processing)\b'),
                 ('hoàn thành', r'hoan thanh|hoan tat|thanh cong|\b(?:xong|complete\w*|done|success\w*|finished|delivered)\b'))


def status_filter_value(value) -> str | None:
    """A status named in an intent filter -> one of the four canonical statuses; None when it names none of them
    (an invented value must not silently select zero orders)."""
    text = plain(value).replace('_', ' ')
    return next((name for name, rx in STATUS_FILTER if re.search(rx, text)), None)


def display_name(value):
    """Customer display name without a trailing phone number (both forms are accepted, §9)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return value
    return PHONE_SUFFIX.sub('', str(value)).strip() or str(value)


def is_cod_or_marketplace(value) -> bool:
    return bool(re.search(r'\bcod\b|thu ho|shopee|lazada|tiki|tiktok|san tmdt|grab|be food|shopeefood',
                          plain(value)))


@dataclass
class Views:
    frames: dict = field(default_factory=dict)
    data_end: date | None = None
    data_start: date | None = None
    notes: list = field(default_factory=list)
    has: set = field(default_factory=set)            # concepts available (for answerability)
    no_order_id: bool = False                         # sales book without order numbers
    no_line_items: bool = False                       # invoice list without item lines
    service_book: bool = False                        # one row per service ticket (repair log), jobs as free text


def _col(m: TableMapping, typed: TypedTables, fname: str, kind: str | None = None):
    if m is None or fname not in m.columns:
        return None
    entity = ENTITIES[m.entity]
    kind = kind or entity.field(fname).kind
    return typed.get(m.table, m.columns[fname], kind)


# ------------------------------------------------ service books (repair / spa ...)
HONORIFIC = re.compile(r'^\s*(?:anh|chị|chi|em|cô|co|chú|chu|bác|bac|ông|ong|bà|ba|thợ|tho|ktv|a|c|e)\s*[.\s]\s*(?=\S)',
                       re.I)
WARRANTY_TEXT = re.compile(r'\bbao hanh\b|\bbh\b')
# Vietnamese plate: province 2 digits, series letter(s) [+digit], 4-5 digits ("59B6-219.16", "50K2-994.07", "29A 12345")
PLATE = re.compile(r'\b(\d{2})\s*-?\s*([A-Z]{1,2}\d?)\s*[-.\s]?\s*(\d{3}\.?\d{2}|\d{4})\b', re.I)


def given_name(raw) -> str | None:
    """'a Phúc', 'A.Phúc', 'anh Phúc' -> 'Phúc' (what a hand-kept book writes for a worker)."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    s = HONORIFIC.sub('', str(raw)).strip()
    return s or None


def resolve_staff_names(values: pd.Series, full_names) -> pd.Series:
    """Nicknames of the book -> full names of the staff list: same last word (given name) and only one worker with it."""
    by_given = {}
    for n in full_names:
        if isinstance(n, str) and n.strip():
            by_given.setdefault(plain(n.split()[-1]), set()).add(n.strip())

    def one(v):
        g = given_name(v)
        if g is None:
            return None
        if any(plain(g) == plain(n) for names in by_given.values() for n in names):
            return next(n for names in by_given.values() for n in names if plain(g) == plain(n))
        hit = by_given.get(plain(g.split()[-1])) if len(g.split()) == 1 else None
        return next(iter(hit)) if hit and len(hit) == 1 else g
    return values.map(one)


def split_vehicle(raw):
    """'Wave Alpha 59N9-950.06' -> ('59N995006', 'wave alpha'); no plate -> (None, model text)."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None, None
    s = str(raw)
    m = PLATE.search(s)
    plate = re.sub(r'[^0-9A-Z]', '', m.group(0).upper()) if m else None
    model = plain(PLATE.sub(' ', s) if m else s)
    model = re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', model)).strip() or None
    return plate, model


def _service_columns(lines, service, typed, by, views):
    """Warranty flag, plate / model of the vehicle, full staff names, staff commission rates (service books)."""
    text = lines['product_name'].map(plain) if 'product_name' in lines else pd.Series('', index=lines.index)
    note = _col(service, typed, 'note')
    if note is not None:
        text = text + ' ' + note.reindex(lines.index).map(lambda v: plain(v) if isinstance(v, str) else '')
    free = lines['line_total'].fillna(0) == 0
    lines['warranty'] = free & text.map(lambda s: bool(WARRANTY_TEXT.search(s)))
    veh = _col(service, typed, 'vehicle')
    if veh is not None:
        pm = veh.reindex(lines.index).map(split_vehicle)
        lines['plate'] = pm.map(lambda t: t[0])
        lines['vehicle_model'] = pm.map(lambda t: t[1])
    staff = by.get('staff')
    if staff is not None and 'staff_name' in staff.columns:
        names = _col(staff, typed, 'staff_name')
        if 'staff' in lines:
            lines['staff'] = resolve_staff_names(lines['staff'], names.dropna().tolist())
        if 'commission_pct' in staff.columns:
            rates = pd.DataFrame({'staff': names, 'pct': _col(staff, typed, 'commission_pct')}).dropna()
            views.frames['staff_rates'] = rates.drop_duplicates('staff')
    elif 'staff' in lines:
        lines['staff'] = lines['staff'].map(given_name)
    views.notes.append(f'service book: {int(lines["warranty"].sum())} warranty tickets (money 0 + "bảo hành")')


ORDER_LEVEL_FIELDS = ('order_total', 'order_discount', 'goods_total', 'shipping_fee', 'paid_amount')
# headers seen on one-sheet exports and hand-kept books ("Bớt" = discount on the whole order, "Khách trả" = what the
# customer pays for the whole order); "khách trả lại" / "trả hàng" are returns, never the order total
ORDER_EXTRA_SYN = {'order_discount': ('tien giam', 'giam don', 'giam hoa don', 'bot', 'tien bot'),
                   'order_total': ('khach tra',)}
NOT_ORDER_FIELD = re.compile(r'\btra (?:lai|hang)\b')


def header_from_lines(t, sm: TableMapping, typed: TypedTables, lines: pd.DataFrame, views=None):
    """One sheet holding both the invoice and its lines ("thông tin hóa đơn lặp lại trên mọi dòng"): order-level money
    columns (order total after the order discount, order discount, shipping, paid) are not line fields. A column is
    taken as an order field when its header names that field (concepts synonyms) AND it holds one value per order on
    the orders with several lines. Returns order_id + those fields (attrs['order_discount_col'] = header), or None."""
    entity = ENTITIES['order']
    used = {h for f, h in sm.columns.items() if f != 'line_discount'}
    oid = lines['order_id']
    size = oid.groupby(oid).transform('size')
    multi = size > 1
    if oid[multi].nunique() < 5:
        return None                                    # too few multi-line orders to tell order- from line-level
    picked, taken = {}, set()
    for fname in ORDER_LEVEL_FIELDS:
        syns = entity.field(fname).syn + ORDER_EXTRA_SYN.get(fname, ())
        best = None
        for h in t.headers:
            if h in used or h in taken:
                continue
            ph = plain(str(h))
            if NOT_ORDER_FIELD.search(ph):
                continue
            hit = max((len(s) for s in syns if re.search(rf'(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])', ph)), default=0)
            if hit and (best is None or hit > best[0]):
                best = (hit, h)
        if best is None:
            continue
        h = best[1]
        v = typed.get(sm.table, h, 'money').reindex(lines.index)
        if v.groupby(oid).first().notna().mean() < 0.5:
            continue                                   # filled on most orders (a book may write it on the first line only)
        per = v[multi].groupby(oid[multi]).nunique(dropna=True)
        if (per <= 1).mean() < 0.98:
            continue                                   # varies inside an order: a line field
        picked[fname] = h
        taken.add(h)
    if 'order_total' not in picked and 'order_discount' not in picked:
        return None
    hdr = pd.DataFrame({'order_id': oid})
    for fname, h in picked.items():
        hdr[fname] = typed.get(sm.table, h, 'money').reindex(lines.index)
    hdr = hdr.groupby('order_id', sort=False).first().reset_index()
    hdr.attrs['order_discount_col'] = picked.get('order_discount')
    if views is not None:
        views.notes.append(f'order fields read from the line sheet: {picked}')
    return hdr


def sheet_scoped_order_ids(lines: pd.DataFrame, views=None) -> pd.Series:
    """Order numbers that restart in each sheet / monthly file (STT 1, 2, 3 ... again every month): the same number in
    two sheets is two orders, so the key is sheet + number. Only for plain numbers shared by several sheets on a
    real share of the lines (an order code like 'HD0012', or one order spilling over two sheets, keeps its id)."""
    ids = lines['order_id']
    known = ids.notna()
    text = ids[known].astype(str).str.strip()
    where = (lines['_file'].astype(str) + ':' + lines['_sheet'].astype(str))[known]
    if where.nunique() < 2 or not len(text) or pd.to_numeric(text, errors='coerce').notna().mean() < 0.98:
        return ids
    sheets = pd.DataFrame({'id': text, 'where': where}).drop_duplicates().groupby('id')['where'].size()
    shared = text.map(sheets) > 1
    if shared.mean() < 0.2:
        return ids
    if views is not None:
        views.notes.append(f'order numbers restart per sheet/file: order key = sheet + number '
                           f'({int(shared.sum())} lines share a number with another sheet)')
    out = ids.astype(object).copy()
    out[known] = where + '#' + text
    return out


def _inherit_blank_cells(frame: pd.DataFrame, group_cols: list[str], order_fields: list[str]) -> pd.DataFrame:
    """§8: blank cells in later rows of an order repeat the first row's value."""
    frame = frame.copy()
    if 'order_id' in frame:
        blank_id = frame['order_id'].isna()
        if blank_id.any() and blank_id.mean() < 0.95:
            frame['order_id'] = frame.groupby(group_cols, sort=False)['order_id'].ffill()
    for col in order_fields:
        if col in frame and 'order_id' in frame:
            g = frame.groupby('order_id', sort=False)[col]
            frame[col] = frame[col].fillna(g.transform('first'))
    return frame


TRUE_WORDS = {'true', '1', 'co', 'x', 'yes', 'y', 'rx', 'kedon', 'thuockedon', 'dung'}


def _flag(v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v):
        return v == 1
    return re.sub(r'[^a-z0-9]', '', plain(str(v))) in TRUE_WORDS if v is not None and not pd.isna(v) else False


def _attach_product_attrs(products: pd.DataFrame, attrs, tables, views) -> pd.DataFrame:
    """Join side tables of product attributes (drug list: code, active ingredient, prescription) by product code."""
    if not attrs or 'product_code' not in products or not len(products):
        return products
    codes = products['product_code'].map(lambda c: str(c).strip() if c is not None and not pd.isna(c) else None)
    known = set(codes.dropna())
    clean = lambda c: str(c).strip() if c is not None and not pd.isna(c) else None
    for a in attrs:
        f = tables[a['table']].frame
        cands = [h for h in (a.get('codes') or [a['code']]) if h in f]
        rate = {h: f[h].map(clean).dropna().isin(known).mean() if f[h].notna().any() else 0.0 for h in cands}
        best = max(cands, key=lambda h: rate[h], default=None)   # the code column is the one that matches the catalogue
        key = f[best].map(clean) if best else pd.Series(dtype=object)
        if not best or rate[best] < 0.5:
            views.notes.append(f"{a['table']}: product attributes not joined (codes do not match the catalogue)")
            continue
        if 'is_prescription' in a:
            rx = dict(zip(key, f[a['is_prescription']].map(_flag)))
            products['is_prescription'] = codes.map(rx).fillna(False).astype(bool)
        if 'active_ingredient' in a:
            ai = dict(zip(key, f[a['active_ingredient']].map(
                lambda v: str(v).strip() if v is not None and not pd.isna(v) and str(v).strip() else None)))
            products['active_ingredient'] = codes.map(ai)
        views.notes.append(f"{a['table']}: product attributes {sorted(k for k in a if k not in ('table', 'code', 'codes'))}")
    return products


def build_views(tables, mapping: dict[str, TableMapping], typed: TypedTables, readme: dict | None = None,
                product_attrs=None) -> Views:
    views = Views()
    by = {m.entity: m for m in mapping.values() if m.entity}
    views.has = set(by)

    # ------------------------------------------------ catalogue + conversions
    products = pd.DataFrame(columns=['product_code', 'product', 'base_unit', 'group', 'unit_cost',
                                     'sale_price', 'is_prescription', 'active_ingredient', 'item_kind'])
    pm = by.get('product')
    if pm:
        products = pd.DataFrame({f: _col(pm, typed, f) for f in
                                 ['product_code', 'product_name', 'base_unit', 'group', 'unit_cost', 'sale_price',
                                  'is_prescription', 'active_ingredient', 'item_kind'] if f in pm.columns})
        products = products.rename(columns={'product_name': 'product'})
    products = _attach_product_attrs(products, product_attrs, tables, views)
    conv =pd.DataFrame(columns=['product_code', 'product_name', 'unit', 'factor', 'base_unit'])
    cm = by.get('unit_conversion')
    if cm:
        conv = pd.DataFrame({f: _col(cm, typed, f) for f in
                             ['product_code', 'product_name', 'unit', 'factor', 'base_unit'] if f in cm.columns})
    conv_by_code = {(str(r.get('product_code')), plain(r['unit'])): float(r['factor'])
                    for r in conv.to_dict('records') if r.get('product_code') and pd.notna(r.get('factor'))}
    conv_by_name = {(name_key(r.get('product_name')), plain(r['unit'])): float(r['factor'])
                    for r in conv.to_dict('records') if r.get('product_name') and pd.notna(r.get('factor'))}
    conv_base = {}
    for r in conv.to_dict('records'):
        if r.get('base_unit'):
            if r.get('product_code'):
                conv_base[str(r['product_code'])] = r['base_unit']
            if r.get('product_name'):
                conv_base[name_key(r['product_name'])] = r['base_unit']

    # ------------------------------------------------ sales lines
    sm, om = by.get('sales_line'), by.get('order')
    if sm is None and om is not None and 'order_id' in om.columns and             ({'goods_total', 'order_total'} & set(om.columns)):
        # invoice list without item lines: one pseudo line per order, worth the order's goods total (§1)
        cols = {f: om.columns[f] for f in ('order_id', 'order_date', 'order_time', 'status', 'customer_name',
                                           'customer_code', 'staff', 'payment_method', 'channel') if f in om.columns}
        cols['line_total'] = om.columns.get('goods_total') or om.columns['order_total']
        sm = TableMapping(om.table, 'sales_line', cols, om.score, {}, 'order-only')
        views.no_line_items = True
        views.notes.append('no item lines: each order is one line worth its goods total; product questions unanswerable')
    service = by.get('service_ticket') if sm is None and om is None else None
    if service is not None:
        # service book (repair / spa ...): one row = one ticket = one sale; the money cell is the ticket total, the
        # job cell is free text (several jobs in one cell, no price per job) -> one pseudo line per ticket
        cols = {'order_date': service.columns['ticket_date'], 'product_name': service.columns['work'],
                'line_total': service.columns['amount']}
        for src, dst in (('technician', 'staff'), ('customer_name', 'customer_name')):
            if src in service.columns:
                cols[dst] = service.columns[src]
        sm = TableMapping(service.table, 'sales_line', cols, service.score, {}, 'service-book')
        views.service_book = True
        views.notes.append('service book: one ticket per row, its total is the sale; jobs are free text')
    if sm is None:
        views.notes.append('no sales line table')
        return views
    t = tables[sm.table]
    fields = list(ENTITIES['sales_line'].fields)
    lines = pd.DataFrame({f.name: _col(sm, typed, f.name) for f in fields if f.name in sm.columns})
    lines['_file'] = t.frame['_file'].values
    lines['_sheet'] = t.frame['_sheet'].values
    lines['_row'] = t.frame['_row'].values
    if 'qty' in sm.columns:                                   # '3 chai' -> qty 3, unit 'chai'
        _, units_in_qty = parse_numbers(t.frame[sm.columns['qty']])
        if 'unit' not in lines:
            lines['unit'] = units_in_qty
        else:
            lines['unit'] = lines['unit'].fillna(units_in_qty)
    # totals / footer rows: no product and a 'tổng ...' label somewhere in the row
    product_cols = [c for c in ('product_name', 'product_code') if c in lines]
    no_product = lines[product_cols].isna().all(axis=1) if product_cols else lines['order_id'].isna()
    label = np.zeros(len(t.frame), dtype=bool)
    for h in t.headers:
        col = t.frame[h]
        text = col[col.map(lambda v: isinstance(v, str))]
        if len(text):
            hit = text.map(lambda v: bool(TOTAL_ROW.match(plain(v))))
            label[t.frame.index.get_indexer(hit[hit].index)] = True
    qty_blank = lines['qty'].isna() if 'qty' in lines else pd.Series(True, index=lines.index)
    footer = no_product & (label | qty_blank)
    if 'order_id' in lines:          # 'TỔNG NGÀY 29/08' written in the product column: no order, no qty
        footer |= pd.Series(label, index=lines.index) & lines['order_id'].isna() & qty_blank
    dropped = int(footer.sum())
    lines = lines[~footer]
    if dropped:
        views.notes.append(f'dropped {dropped} subtotal/footer rows')
    # order-level money written as a line of the order ("Phí ship" 15 000, "Voucher" -10 000): no quantity, no unit
    # price, a shipping / discount / points word as the item. Rulebook §1: revenue is the item lines only, without the
    # shipping fee and without order discounts -> not a sales line. ("Phí phục vụ" stays: it counts in revenue.)
    if product_cols:
        name = lines[product_cols[0]].map(lambda v: plain(v) if isinstance(v, str) else '')
        no_price = lines['unit_price'].isna() if 'unit_price' in lines else pd.Series(True, index=lines.index)
        qty_none = lines['qty'].isna() if 'qty' in lines else pd.Series(True, index=lines.index)
        fee = name.map(lambda v: bool(NON_ITEM_LINE.match(v))) & qty_none & no_price
        if fee.any():
            views.notes.append(f'dropped {int(fee.sum())} shipping / voucher lines (not items, not revenue)')
            lines = lines[~fee]
    if views.no_line_items:                # after the footer filter: subtotal rows have no order either
        lines = lines[lines['order_id'].notna()].copy()
        lines['product_name'] = '(đơn hàng)'
    order_level = [c for c in ('order_date', 'status', 'customer_name', 'customer_code', 'staff',
                               'payment_method', 'channel', 'order_time') if c in lines]
    if {'qty', 'line_total', 'unit_price'} <= set(lines.columns):     # unreadable qty: total / price
        derived = (lines['line_total'] / lines['unit_price']).where(lines['unit_price'] > 0)
        lines['qty'] = lines['qty'].fillna(derived.round(6))
    synthetic_ids = 'order_id' not in lines
    if synthetic_ids:                      # sales book without order numbers: each line is one sale
        lines = lines.copy()
        lines['order_id'] = ['L' + str(i) for i in lines.index]
        if service is None:                # a service book row IS a ticket: tickets can be counted
            views.no_order_id = True
            views.notes.append('no order id: each line counted as its own sale; order counts unanswerable')
    else:
        if om is None:                     # numbers restarting per sheet: scope them BEFORE inheriting by order
            lines = _inherit_blank_cells(lines, ['_file', '_sheet'], [])
            lines['order_id'] = sheet_scoped_order_ids(lines, views)
        lines = _inherit_blank_cells(lines, ['_file', '_sheet'], order_level)
    lines = lines[lines['order_id'].notna()].copy()
    lines['order_id'] = lines['order_id'].astype(str).str.strip()
    if service is not None:
        _service_columns(lines, service, typed, by, views)
    order_level = [c for c in order_level if c in lines]
    # §8: two lines of one order identical in EVERY cell are an export error -> count once.
    # Order-level cells left blank in later rows are compared after inheritance.
    raw = t.frame.loc[lines.index, t.headers].astype(str)
    for fname in order_level + ['order_id']:
        if fname in sm.columns:
            raw[sm.columns[fname]] = lines[fname].astype(str)
    before = len(lines)
    if not synthetic_ids:                  # identical lines of one sales book are separate sales
        lines = lines[~raw.duplicated()]
    if before - len(lines):
        views.notes.append(f'removed {before - len(lines)} duplicate lines inside orders')

    # join the order header (header-detail exports)
    orders_hdr = None
    if om is not None:
        hdr_fields = [f.name for f in ENTITIES['order'].fields if f.name in om.columns]
        orders_hdr = pd.DataFrame({f: _col(om, typed, f) for f in hdr_fields})
        orders_hdr['order_id'] = orders_hdr['order_id'].astype(str).str.strip()
        orders_hdr = orders_hdr.drop_duplicates('order_id')
        take = [c for c in ('order_date', 'order_time', 'status', 'customer_name', 'customer_code',
                            'staff', 'payment_method', 'channel') if c in orders_hdr]
        lines = lines.drop(columns=[c for c in take if c in lines], errors='ignore').merge(
            orders_hdr[['order_id'] + take], on='order_id', how='left')

    if orders_hdr is None and 'order_id' in lines:
        orders_hdr = header_from_lines(t, sm, typed, lines, views)
        if orders_hdr is not None and 'line_discount' in lines and 'order_discount' in orders_hdr \
                and sm.columns.get('line_discount') == orders_hdr.attrs.get('order_discount_col'):
            lines = lines.drop(columns=['line_discount'])

    # product identity: code when the shop has codes, else spelling-insensitive name
    keyed_by_code = 'product_code' in lines and lines['product_code'].notna().mean() > 0.9
    if keyed_by_code:
        lines['product_key'] = lines['product_code'].astype(str)
        names = products.set_index('product_code')['product'].to_dict() if 'product_code' in products else {}
        freq = lines.groupby(['product_key', 'product_name']).size().reset_index(name='n') \
            if 'product_name' in lines else None
        best = (freq.sort_values(['product_key', 'n'], ascending=[True, False]).drop_duplicates('product_key')
                .set_index('product_key')['product_name'].to_dict()) if freq is not None else {}
        lines['product'] = lines['product_key'].map(lambda k: names.get(k) or best.get(k) or k)
    else:
        lines['product_key'] = lines['product_name'].map(name_key)
        freq = lines.groupby(['product_key', 'product_name']).size().reset_index(name='n')
        best = freq.sort_values(['product_key', 'n', 'product_name'], ascending=[True, False, True]) \
            .drop_duplicates('product_key').set_index('product_key')['product_name']
        lines['product'] = lines['product_key'].map(best)
        if 'product_code' not in lines:
            lines['product_code'] = None
    lines['is_item'] = ~lines['product'].map(lambda v: bool(SERVICE_FEE.search(plain(v))))

    # units: factor from conversion table, else the line is already in base units
    lines['unit_plain'] = lines['unit'].map(plain) if 'unit' in lines else ''

    code_s = lines['product_code'].astype(str) if 'product_code' in lines else pd.Series('None', index=lines.index)
    name_s = (lines['product_name'] if 'product_name' in lines else lines['product']).map(name_key)
    by_code = pd.Series([conv_by_code.get(k) for k in zip(code_s, lines['unit_plain'])], index=lines.index, dtype='float64')
    by_name = pd.Series([conv_by_name.get(k) for k in zip(name_s, lines['unit_plain'])], index=lines.index, dtype='float64')
    qty = lines['qty'] if 'qty' in lines else pd.Series(1.0, index=lines.index)
    if 'qty_base' in lines and lines['qty_base'].notna().mean() > 0.9:
        lines['qty_base'] = lines['qty_base'].fillna(qty)
        lines['factor'] = (lines['qty_base'] / qty).where(qty > 0)
    else:
        lines['factor'] = by_code.fillna(by_name).fillna(1.0)
        lines['qty_base'] = qty * lines['factor']
    # base unit per product: catalogue, conversion table, else unit of factor-1 lines
    cat_base = products.set_index('product_code')['base_unit'].to_dict() \
        if {'product_code', 'base_unit'} <= set(products.columns) else {}
    if 'unit' in lines:
        ones = lines[lines['factor'].round(6) == 1].dropna(subset=['unit'])
        unit_one = ones.groupby(['product_key', 'unit']).size().reset_index(name='n') \
            .sort_values(['product_key', 'n'], ascending=[True, False]).drop_duplicates('product_key') \
            .set_index('product_key')['unit'].to_dict()
    else:
        unit_one = {}
    per_key = {}
    for key, code, nkey in lines[['product_key']].assign(code=code_s, nkey=name_s).drop_duplicates('product_key').itertuples(index=False):
        per_key[key] = cat_base.get(code) or conv_base.get(code) or conv_base.get(nkey) or unit_one.get(key)
    lines['base_unit'] = lines['product_key'].map(per_key)
    if 'line_total' not in lines:
        lines['line_total'] = qty * lines['unit_price'] - lines.get('line_discount', 0)
    lines['unit_price_base'] = (lines['unit_price'] / lines['factor']) if 'unit_price' in lines else np.nan
    if 'unit_cost' in lines:
        lines['line_cost'] = qty * lines['unit_cost']

    # statuses (§1): one canonical status; any returned line -> whole order returned
    lines['line_status'] = lines['status'].map(canonical_status) if 'status' in lines else 'hoàn thành'
    lines['line_status'] = lines['line_status'].fillna('hoàn thành')
    rank = {'trả hàng': 3, 'huỷ': 2, 'đang giao': 1, 'hoàn thành': 0}
    inv = {v: k for k, v in rank.items()}
    order_status = lines.groupby('order_id')['line_status'].agg(lambda s: inv[max(rank[x] for x in s)])
    lines['order_status'] = lines['order_id'].map(order_status)
    lines['counts_for_revenue'] = ~lines['order_status'].isin(['huỷ', 'trả hàng'])
    if 'order_date' not in lines and 'order_time' in lines:      # only a timestamp column: its day is the order day
        stamp = pd.to_datetime(lines['order_time'], errors='coerce')
        if stamp.notna().mean() >= 0.9 and (stamp.dropna().dt.year > 2000).all():
            lines['order_date'] = stamp
            views.notes.append('order_date taken from order_time')
    lines['order_date'] = pd.to_datetime(lines['order_date']).dt.normalize() if 'order_date' in lines else pd.NaT

    # customers (§3): code when the shop has codes, else spelling-insensitive name; walk-ins excluded
    cust = by.get('customer')
    groups = {}
    if cust is not None and 'customer_group' in cust.columns:
        groups = dict(zip(_col(cust, typed, 'customer_code'), _col(cust, typed, 'customer_group')))
    cust_names = dict(zip(_col(cust, typed, 'customer_code'), _col(cust, typed, 'customer_name'))) \
        if cust is not None and 'customer_name' in cust.columns else {}
    has_codes = 'customer_code' in lines and lines['customer_code'].notna().any()
    if has_codes:
        lines['customer_key'] = lines['customer_code'].where(lines['customer_code'].notna(), None)
        name_by_code = lines.dropna(subset=['customer_code']).groupby('customer_code')['customer_name'] \
            .agg(lambda s: s.value_counts().index[0]) if 'customer_name' in lines else {}
        lines['customer'] = lines['customer_key'].map(lambda k: cust_names.get(k) or (name_by_code.get(k)
                                                     if k is not None else None))
    elif 'customer_name' in lines:
        key = lines['customer_name'].map(name_key)
        lines['customer_key'] = key.where(~key.isin(WALK_IN), None)
        best = lines.dropna(subset=['customer_key']).groupby(['customer_key', 'customer_name']).size() \
            .reset_index(name='n').sort_values(['customer_key', 'n'], ascending=[True, False]) \
            .drop_duplicates('customer_key').set_index('customer_key')['customer_name']
        lines['customer'] = lines['customer_key'].map(best)
    else:
        lines['customer_key'] = None
        lines['customer'] = None
    lines['customer'] = lines['customer'].map(display_name)
    lines['customer_group'] = lines['customer_key'].map(groups) if groups else None

    keep = ['order_id', 'order_date', 'order_time', 'order_status', 'line_status', 'counts_for_revenue',
            'product_key', 'product', 'product_code', 'is_item', 'unit', 'qty', 'factor', 'base_unit', 'qty_base',
            'unit_price', 'unit_price_base', 'line_discount', 'line_total', 'unit_cost', 'line_cost',
            'customer_key', 'customer', 'customer_group', 'staff', 'payment_method', 'channel', 'delivery_date',
            'warranty', 'plate', 'vehicle_model']
    sales_lines = lines[[c for c in keep if c in lines]].copy()
    sales_lines['order_date'] = sales_lines['order_date'].dt.date

    # ------------------------------------------------ orders
    agg = lines.groupby('order_id').agg(
        order_date=('order_date', 'min'), order_status=('order_status', 'first'),
        counts_for_revenue=('counts_for_revenue', 'first'), revenue=('line_total', 'sum'),
        n_lines=('product', 'size'), customer_key=('customer_key', 'first'), customer=('customer', 'first'))
    for opt in ('order_time', 'staff', 'payment_method', 'channel', 'customer_group', 'warranty', 'plate',
                'vehicle_model'):
        if opt in lines:
            agg[opt] = lines.groupby('order_id')[opt].first()
    if orders_hdr is not None:
        extra = [c for c in ('goods_total', 'order_discount', 'order_total', 'paid_amount', 'shipping_fee', 'vat')
                 if c in orders_hdr]
        agg = agg.join(orders_hdr.set_index('order_id')[extra], how='left')
        # header-only orders (no detail line) still exist for status counts
        missing = orders_hdr[~orders_hdr['order_id'].isin(agg.index)]
        if len(missing):
            views.notes.append(f'{len(missing)} header orders without detail lines')
    if 'order_total' not in agg:
        agg['order_total'] = agg['revenue']
    agg = agg.reset_index()
    agg['order_date'] = pd.to_datetime(agg['order_date']).dt.date
    if 'order_time' in agg:
        agg['hour'] = pd.to_datetime(agg['order_time']).dt.hour
    views.frames['sales_lines'] = sales_lines
    views.frames['orders'] = agg

    # ------------------------------------------------ products view (catalogue ∪ sold items)
    sold = sales_lines.groupby('product_key').agg(product=('product', 'first'), product_code=('product_code', 'first'),
                                                  base_unit=('base_unit', 'first')).reset_index()
    if len(products) and 'product_code' in products:
        catalog = products.copy()
        # same key as the sales lines: a catalogue with codes next to a sales book without them is joined by name
        catalog['product_key'] = catalog['product_code'].astype(str) if keyed_by_code or 'product' not in catalog             else catalog['product'].map(name_key)
        catalog = catalog.drop_duplicates('product_key')
        prod_view = catalog.merge(sold[['product_key']], on='product_key', how='outer')
        prod_view['product'] = prod_view['product'].fillna(prod_view['product_key'].map(sold.set_index('product_key')['product']))
    else:
        prod_view = sold
        if len(products):
            catalog = products.copy()
            catalog['product_key'] = catalog['product'].map(name_key)
            prod_view = sold.merge(catalog.drop(columns=['product'], errors='ignore'), on='product_key', how='left')
    views.frames['products'] = prod_view

    # ------------------------------------------------ payments and debts (§4)
    pay = by.get('payment')
    if pay is not None:
        payments = pd.DataFrame({'order_id': _col(pay, typed, 'order_id').astype(str).str.strip(),
                                 'pay_time': _col(pay, typed, 'payment_time'),
                                 'amount': _col(pay, typed, 'amount')})
        if 'method' in pay.columns:
            payments['method'] = _col(pay, typed, 'method')
        payments['pay_date'] = pd.to_datetime(payments['pay_time']).dt.date
        views.frames['payments'] = payments

    # ------------------------------------------------ deliveries (rulebook "Giao nhiều đợt")
    dm = by.get('delivery')
    if dm is not None:
        dl = pd.DataFrame({'order_id': _col(dm, typed, 'order_id').astype(str).str.strip(),
                           'batch': _col(dm, typed, 'batch'),
                           'delivery_date': pd.to_datetime(_col(dm, typed, 'delivery_date'), errors='coerce').dt.date})
        views.frames['deliveries'] = dl.dropna(subset=['delivery_date'])

    # ------------------------------------------------ purchases (§5)
    ph, pl = by.get('purchase'), by.get('purchase_line')
    if pl is not None or ph is not None:
        if pl is not None:
            plines = pd.DataFrame({f: _col(pl, typed, f) for f in pl.columns})
            if ph is not None and 'purchase_id' in plines:
                hdr = pd.DataFrame({f: _col(ph, typed, f) for f in ph.columns})
                plines = plines.drop(columns=[c for c in ('purchase_date', 'supplier') if c in plines and c in hdr]) \
                    .merge(hdr[[c for c in ('purchase_id', 'purchase_date', 'supplier', 'status', 'note') if c in hdr]],
                           on='purchase_id', how='left')
            if 'product_code' in plines:
                plines['product_key'] = plines['product_code'].astype(str)
            else:
                plines['product_key'] = plines['product_name'].map(name_key)
            plines['unit_plain'] = plines['unit'].map(plain) if 'unit' in plines else ''
            plines['factor'] = [conv_by_code.get((str(r.get('product_code')), r['unit_plain'])) or
                                conv_by_name.get((name_key(r.get('product_name')), r['unit_plain'])) or 1.0
                                for r in plines.to_dict('records')]
            plines['qty_base'] = plines['qty'] * plines['factor']
            if 'line_total' not in plines and 'unit_cost' in plines:
                plines['line_total'] = plines['qty'] * plines['unit_cost']
            plines['cancelled'] = plines['status'].map(lambda v: bool(re.search(r'\bhuy\b|cancel', plain(v)))) \
                if 'status' in plines else False
            plines['purchase_date'] = pd.to_datetime(plines['purchase_date']).dt.date
            plines['product'] = plines['product_key'].map(sales_lines.groupby('product_key')['product'].first()) \
                .fillna(plines['product_key'].map(prod_view.set_index('product_key')['product']) if 'product' in prod_view else None)
            views.frames['purchase_lines'] = plines
        if ph is not None:
            hdr = pd.DataFrame({f: _col(ph, typed, f) for f in ph.columns})
            hdr['cancelled'] = hdr['status'].map(lambda v: bool(re.search(r'\bhuy\b|cancel', plain(v)))) \
                if 'status' in hdr else False
            hdr['purchase_date'] = pd.to_datetime(hdr['purchase_date']).dt.date
            plf = views.frames.get('purchase_lines')
            if 'total' not in hdr and plf is not None and {'purchase_id', 'line_total'} <= set(plf.columns) \
                    and 'purchase_id' in hdr:
                hdr = hdr.merge(views.frames['purchase_lines'].groupby('purchase_id')['line_total'].sum()
                                .rename('total').reset_index(), on='purchase_id', how='left')
            views.frames['purchases'] = hdr
        elif 'purchase_lines' in views.frames:
            pls = views.frames['purchase_lines']
            if 'purchase_id' in pls:
                agg = dict(purchase_date=('purchase_date', 'min'), cancelled=('cancelled', 'first'))
                if 'line_total' in pls:          # lines without any money column (e.g. delivery notes)
                    agg['total'] = ('line_total', 'sum')
                views.frames['purchases'] = pls.groupby('purchase_id').agg(**agg).reset_index()

    # ------------------------------------------------ stock snapshot
    st = by.get('stock_snapshot')
    if st is not None:
        stock = pd.DataFrame({f: _col(st, typed, f) for f in st.columns})
        stock['product_key'] = stock['product_code'].astype(str) if 'product_code' in stock \
            else stock['product_name'].map(name_key)
        views.frames['stock_snapshot'] = stock

    # ------------------------------------------------ coverage
    dates = pd.to_datetime(pd.Series(sales_lines['order_date'])).dropna()
    views.data_start = dates.min().date() if len(dates) else None
    views.data_end = dates.max().date() if len(dates) else None
    if readme:
        m = re.search(r'đến hết (?:ngày )?(\d{1,2})/(\d{1,2})/(\d{4})', readme.get('text', ''))
        if m:
            views.data_end = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return views
