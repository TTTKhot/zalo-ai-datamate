"""Metric library over the canonical views (rulebook §1-§6, §9 formats).

`run(views, intent, today, calendar)` executes one validated intent and returns
{'answer', 'type'} or raises Unanswerable / NeedsReview.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from .periods import Calendar, Period, previous_period, resolve
from .rules import Views, is_cod_or_marketplace, status_filter_value
from .values import name_key, plain


class Unanswerable(Exception):
    pass


class NeedsReview(Exception):
    """Inputs could not be grounded (unknown product, ambiguous filter)."""


# shared vocabulary for order-level categorical filters (raw values differ per shop: 'cash', 'Tiền mặt', 'TM')
PAYMENT_SYN = {'cash': ('cash', 'tienmat', 'tm'), 'transfer': ('transfer', 'chuyenkhoan', 'ck', 'bank', 'nganhang'),
               'ewallet': ('ewallet', 'vidientu', 'momo', 'zalopay', 'vnpay', 'shopeepay'),
               'card': ('card', 'the', 'pos', 'quetthe')}
CHANNEL_SYN = {'zalo': ('zalo',), 'phone': ('phone', 'dienthoai', 'goidien', 'hotline'),
               'store': ('store', 'cuahang', 'taiquay', 'offline', 'tructiep'),
               'facebook': ('facebook', 'fb', 'messenger'), 'shopee': ('shopee',), 'grab': ('grab',)}


LINE_KEYS = ('product', 'group', 'size', 'unit', 'prescription', 'active_ingredient')   # filters on item lines


def _set(v) -> bool:
    return v is not None and not (isinstance(v, (str, list, dict)) and len(v) == 0)


def _vkey(s) -> str:
    return re.sub(r'[^a-z0-9]', '', plain(str(s)))


def vocab_match(value, syn: dict):
    """Predicate raw -> bool: same synonym class as `value` (else substring of the squashed text)."""
    v = _vkey(value)
    toks = next((t for t in syn.values() if any(v == x or (len(x) > 2 and x in v) for x in t)), None)

    def hit(raw):
        r = _vkey(raw)
        if not r:
            return False
        if toks is None:
            return v in r
        return any(r == x or (len(x) > 2 and x in r) for x in toks)
    return hit


def money(x):
    return int(Decimal(str(float(x))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def pct(x):
    return float(Decimal(str(float(x))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def num(x):
    x = float(x)
    return int(round(x)) if abs(x - round(x)) < 1e-9 else round(x, 2)


# ------------------------------------------------------------------ grounding
def _grams(text, n=3):
    t = f' {plain(text)} '
    return Counter(t[i:i + n] for i in range(len(t) - n + 1))


def match_name(query: str, names: list[str], min_score=0.55) -> str | None:
    if not query:
        return None
    key = name_key(query)
    exact = [n for n in names if name_key(n) == key]
    if exact:
        return exact[0]
    q = _grams(query)
    best, best_s = None, 0.0
    for n in names:
        g = _grams(n)
        s = 2 * sum((q & g).values()) / max(sum(q.values()) + sum(g.values()), 1)
        if s > best_s:
            best, best_s = n, s
    return best if best_s >= min_score else None


class Ctx:
    def __init__(self, views: Views, today, calendar=None):
        self.v = views
        self.today = today if isinstance(today, date) else date.fromisoformat(str(today)[:10])
        self.cal = calendar or Calendar()
        self._lines = views.frames.get('sales_lines')
        self._orders = views.frames.get('orders')

    # a shop whose files hold no sales table (or whose sales table was not recognised) cannot answer a sales metric:
    # abstain cleanly instead of failing on None (dev shop with a repair log read as expenses: every question crashed)
    @property
    def lines(self):
        if self._lines is None:
            raise NeedsReview('shop has no sales table')
        return self._lines

    @property
    def orders(self):
        if self._orders is None:
            raise NeedsReview('shop has no sales table')
        return self._orders

    # ---- periods
    def period(self, spec) -> Period:
        p = resolve(spec, self.today, self.cal)
        return self.clip(p)

    def clip(self, p: Period) -> Period:
        """Records after today have not happened yet (rulebook header)."""
        end = min(p.end, self.today + timedelta(days=1))
        if p.kind != 'as_of' and self.v.data_start and self.v.data_end:
            if end <= self.v.data_start or p.start > self.v.data_end:
                raise Unanswerable(f'{p.label} is outside data coverage {self.v.data_start}..{self.v.data_end}')
        return Period(p.start, max(end, p.start), p.label, p.kind)

    # ---- filters
    def product_keys(self, name):
        names = self.lines.drop_duplicates('product_key')[['product_key', 'product']]
        found = match_name(name, names['product'].dropna().tolist())
        if found is None:
            codes = names[names['product_key'].map(plain) == plain(name)]
            if len(codes):
                return set(codes['product_key'])
            raise NeedsReview(f'unknown product {name!r}')
        return set(names[names['product'] == found]['product_key'])

    def customer_keys(self, name):
        cust = self.lines.dropna(subset=['customer_key']).drop_duplicates('customer_key')[['customer_key', 'customer']]
        found = match_name(name, cust['customer'].dropna().tolist(), 0.7)
        if found is None:
            raise NeedsReview(f'unknown customer {name!r}')
        return set(cust[cust['customer'] == found]['customer_key'])

    def sel_lines(self, p: Period, f: dict, revenue_only=True):
        x = self.lines
        d = pd.to_datetime(x['order_date'])
        m = (d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end))
        if revenue_only:
            m &= x['counts_for_revenue']
        x = x[m]
        return self.apply_filters(x, f, level='line')

    def sel_orders(self, p: Period, f: dict, revenue_only=True):
        o = self.orders
        d = pd.to_datetime(o['order_date'])
        m = (d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end))
        if revenue_only:
            m &= o['counts_for_revenue']
        o = o[m]
        line_filters = {k: v for k, v in f.items() if k in LINE_KEYS and _set(v)}
        if line_filters:
            ids = set(self.apply_filters(self.lines[self.lines['order_id'].isin(o['order_id'])], line_filters, 'line')['order_id'])
            o = o[o['order_id'].isin(ids)]
        return self.apply_filters(o, {k: v for k, v in f.items() if k not in line_filters}, level='order')

    def apply_filters(self, x, f: dict, level):
        for key, value in (f or {}).items():
            if value in (None, '', []):
                continue
            if key == 'product':
                x = x[x['product_key'].isin(self.product_keys(value))]
            elif key == 'group':
                groups = self.v.frames['products'][['product_key', 'group']].dropna() \
                    if 'group' in self.v.frames['products'] else None
                if groups is None or groups.empty:
                    raise Unanswerable('shop has no product groups')
                names = groups['group'].drop_duplicates().tolist()
                g = next((n for n in names if plain(n) == plain(value)), None)
                if g is None:
                    raise NeedsReview(f'unknown group {value!r}')
                x = x[x['product_key'].isin(set(groups[groups['group'] == g]['product_key']))]
            elif key == 'size':
                rx = re.compile(rf'\(\s*{re.escape(str(value))}\s*\)\s*$', re.I)
                if not self.lines['product'].map(lambda n: bool(rx.search(str(n)))).any():
                    # the size is not written in the product names (another column, another notation): 0 would be a guess
                    raise NeedsReview(f'size {value!r} not found in product names')
                x = x[x['product'].map(lambda n: bool(rx.search(str(n)))).astype(bool)]
            elif key == 'unit':
                x = x[x['base_unit'].map(plain) == plain(value)]
            elif key == 'payment_method':
                if 'payment_method' not in x:
                    raise Unanswerable('no payment method column')
                pv = plain(value)
                if pv in ('cod', 'thu ho'):
                    x = x[x['payment_method'].map(is_cod_or_marketplace)]
                else:
                    x = x[x['payment_method'].map(vocab_match(value, PAYMENT_SYN))]
            elif key == 'prescription':
                prods = self.v.frames['products']
                if 'is_prescription' not in prods or not prods['is_prescription'].any():
                    raise Unanswerable('shop does not record prescription drugs')
                want = value if isinstance(value, bool) else plain(str(value)) in ('true', '1', 'co', 'yes')
                rx = set(prods[prods['is_prescription'].fillna(False).astype(bool)]['product_key'])
                x = x[x['product_key'].isin(rx) == want]       # rulebook: everything not marked is non-prescription
            elif key == 'active_ingredient':
                prods = self.v.frames['products']
                if 'active_ingredient' not in prods or prods['active_ingredient'].isna().all():
                    raise Unanswerable('shop does not record active ingredients')
                names = prods['active_ingredient'].dropna().drop_duplicates()
                g = next((n for n in names if _vkey(n) == _vkey(value)), None)   # exact (combinations are separate)
                if g is None:
                    raise NeedsReview(f'unknown active ingredient {value!r}')
                x = x[x['product_key'].isin(set(prods[prods['active_ingredient'] == g]['product_key']))]
            elif key == 'channel':
                if 'channel' not in x or x['channel'].isna().all():
                    raise Unanswerable('no sales channel column')
                x = x[x['channel'].map(vocab_match(value, CHANNEL_SYN))]
            elif key == 'shift':
                if 'hour' not in x and 'order_time' not in x:
                    raise Unanswerable('no order time')
                hour = x['hour'] if 'hour' in x else pd.to_datetime(x['order_time']).dt.hour
                sv = plain(str(value))
                if re.search(r'\bsang\b|morning', sv):          # rulebook: ca sáng 06:00-13:59, ca chiều 14:00-21:59
                    lo, hi = 6, 13
                elif re.search(r'\bchieu\b|afternoon', sv):
                    lo, hi = 14, 21
                else:
                    raise NeedsReview(f'unknown shift {value!r}')
                x = x[(hour >= lo) & (hour <= hi)]
            elif key == 'customer':
                x = x[x['customer_key'].isin(self.customer_keys(value))]
            elif key == 'customer_group':
                if 'customer_group' not in x or x['customer_group'].isna().all():
                    raise Unanswerable('no customer groups')
                known = {plain(g) for g in self.lines['customer_group'].dropna().unique()}
                if plain(value) not in known:
                    raise Unanswerable(f'shop does not record customer group {value!r}')
                x = x[x['customer_group'].map(plain) == plain(value)]
            elif key == 'staff':
                if 'staff' not in x:
                    raise Unanswerable('no staff column')
                if not (x['staff'].map(plain) == plain(value)).any() and not any(
                        (d['staff'].map(plain) == plain(value)).any() for d in (self.lines, self.orders) if 'staff' in d):
                    # name vs code, another spelling: 0 would be a guess
                    raise NeedsReview(f'staff {value!r} not found in the data')
                x = x[x['staff'].map(plain) == plain(value)]
            elif key == 'status':
                want = status_filter_value(value)      # 'cancelled', 'Đã huỷ', 'hoan_thanh' ... -> canonical status
                if want is None:
                    raise NeedsReview(f'unknown status {value!r}')
                x = x[x['order_status'] == want]
        return x


# ------------------------------------------------------------------ metrics
def _rank(df, value_col, key_col, ascending=False, tie_col=None):
    tie_col = tie_col or key_col
    return df.sort_values([value_col, tie_col], ascending=[ascending, True])


def m_revenue(c: Ctx, p, f, q):
    if any(_set(f.get(k)) for k in LINE_KEYS):
        return c.sel_lines(p, f)['line_total'].sum()
    return c.sel_orders(p, f)['revenue'].sum()


def m_order_count(c, p, f, q):
    o = c.sel_orders(p, f)
    thr = q.get('min_value')
    if thr is not None:
        o = o[o['revenue'] > thr] if q.get('strict') else o[o['revenue'] >= thr]
    return o['order_id'].nunique()


def m_cancelled_count(c, p, f, q):
    return int((c.sel_orders(p, f, revenue_only=False)['order_status'] == 'huỷ').sum())


def m_cancel_rate(c, p, f, q):
    o = c.sel_orders(p, f, revenue_only=False)
    if len(o) == 0:
        raise Unanswerable('no orders in period')
    return 100.0 * (o['order_status'] == 'huỷ').sum() / len(o)


def m_avg_order_value(c, p, f, q):
    o = c.sel_orders(p, f)
    if 'warranty' in o:                    # service book: average over tickets with money (warranty tickets are free)
        o = o[o['revenue'] > 0]
    if len(o) == 0:
        raise Unanswerable('no orders')
    return o['revenue'].sum() / len(o)


def m_quantity(c, p, f, q):
    return c.sel_lines(p, f)['qty_base'].sum()


def m_unit_price(c, p, f, q):
    x = c.sel_lines(p, f, revenue_only=False)
    if x.empty:
        raise Unanswerable('product not sold that day')
    return Counter(x['unit_price_base'].round(2)).most_common(1)[0][0]


def _top(c, p, f, q, by='qty'):
    x = c.sel_lines(p, f)
    x = x[x['is_item']]
    if by == 'revenue':
        g = x.groupby('product_key').agg(v=('line_total', 'sum'), name=('product', 'first'))
    elif by == 'orders':                               # rulebook "được ưa chuộng nhất": in the most orders
        g = x.groupby('product_key').agg(v=('order_id', 'nunique'), name=('product', 'first'))
    elif by == 'profit':
        if 'line_cost' not in x:
            raise Unanswerable('no cost on sales lines')
        g = x.assign(pf=x['line_total'] - x['line_cost']).groupby('product_key').agg(v=('pf', 'sum'), name=('product', 'first'))
    else:
        g = x.groupby('product_key').agg(v=('qty_base', 'sum'), name=('product', 'first'))
    g = g.reset_index()
    g = _rank(g, 'v', 'product_key', ascending=q.get('order') == 'asc')
    return g


def m_top_products(c, p, f, q):
    g = _top(c, p, f, q, q.get('by', 'qty'))
    k = int(q.get('k') or 1)
    names = g['name'].head(k).tolist()
    if not names:
        raise Unanswerable('no sales')
    return names if q.get('as_list') or k > 1 else names[0]


def m_top_customers(c, p, f, q):
    o = c.sel_orders(p, f, revenue_only=q.get('by') != 'cancelled').dropna(subset=['customer_key'])
    if q.get('by') == 'cancelled':                     # rulebook "khách hay đổi ý nhất": most cancelled orders
        o = o[o['order_status'] == 'huỷ']
    if o.empty:
        raise Unanswerable('no identified customers')
    if q.get('by') in ('orders', 'cancelled'):
        g = o.groupby('customer_key').agg(v=('order_id', 'nunique'), name=('customer', 'first'))
    elif q.get('by') == 'days':                        # rulebook "trung thành nhất": most days with a purchase
        g = o.groupby('customer_key').agg(v=('order_date', 'nunique'), name=('customer', 'first'))
    elif q.get('by') == 'avg_order':                   # rulebook "sộp nhất": average order value, >= 3 orders
        g = o.groupby('customer_key').agg(rev=('revenue', 'sum'), n=('order_id', 'nunique'), name=('customer', 'first'))
        g = g[g['n'] >= 3]
        if g.empty:
            raise Unanswerable('no customer with 3 orders or more')
        g['v'] = g['rev'] / g['n']
    else:
        g = o.groupby('customer_key').agg(v=('revenue', 'sum'), name=('customer', 'first'))
    g = _rank(g.reset_index(), 'v', 'customer_key')
    k = int(q.get('k') or 1)
    names = g['name'].head(k).tolist()
    return names if q.get('as_list') or k > 1 else names[0]


def m_best_day(c, p, f, q):
    o = c.sel_orders(p, f)
    if q.get('by') == 'hour':                          # rulebook "giờ cao điểm": one-hour slot with the most orders
        x = c.lines[c.lines['order_id'].isin(o['order_id'])]
        if 'order_time' not in x or x['order_time'].isna().all():
            raise Unanswerable('no order time')
        t = pd.to_datetime(x.groupby('order_id')['order_time'].first().astype(str), errors='coerce', format='mixed')
        hours = t.dt.hour.dropna().astype(int)
        if hours.empty:
            raise Unanswerable('no order time')
        n = hours.value_counts()
        return int(min(h for h, v in n.items() if v == n.max()))
    if q.get('by') == 'orders':                        # rulebook "ngày đắt khách nhất": the most orders
        g = o.groupby('order_date')['order_id'].nunique().rename('revenue').reset_index()
    else:
        g = o.groupby('order_date')['revenue'].sum().reset_index()
    g = g.sort_values(['revenue', 'order_date'], ascending=[q.get('order') == 'asc', True])
    if g.empty:
        raise Unanswerable('no sales')
    return g['order_date'].iloc[0].isoformat()


def m_products_min_orders(c, p, f, q):
    x = c.sel_lines(p, f)
    x = x[x['is_item']]
    n = x.groupby('product_key')['order_id'].nunique()
    thr = q['threshold']
    return int((n > thr).sum() if q.get('strict') else (n >= thr).sum())


def m_customers_min_orders(c, p, f, q):
    o = c.sel_orders(p, f).dropna(subset=['customer_key'])
    n = o.groupby('customer_key')['order_id'].nunique()
    thr = q['threshold']
    hit = (n > thr).sum() if q.get('strict') else (n >= thr).sum()
    if q.get('as_percent'):
        return 100.0 * hit / max(len(n), 1)
    return int(hit)


def m_unsold_products(c, p, f, q):
    """§5 ế: sold before the period (orders that count) but in no counted order inside it."""
    x = c.lines[c.lines['counts_for_revenue'] & c.lines['is_item']]
    d = pd.to_datetime(x['order_date'])
    before = set(x[d < pd.Timestamp(p.start)]['product_key'])
    during = set(x[(d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end))]['product_key'])
    keys = sorted(before - during)
    if q.get('as_list'):
        names = x.drop_duplicates('product_key').set_index('product_key')['product']
        return [names[k] for k in keys]
    return len(keys)


def m_days_min_revenue(c, p, f, q):
    o = c.sel_orders(p, f)
    daily = o.groupby('order_date')['revenue'].sum()
    thr = q['min_value']
    return int((daily > thr).sum() if q.get('strict') else (daily >= thr).sum())


def m_gross_profit(c, p, f, q):
    x = c.sel_lines(p, f)
    if 'line_cost' not in x or x['line_cost'].isna().all():
        raise Unanswerable('no cost of goods on sales lines')
    return x['line_total'].sum() - x['line_cost'].sum()


# ---- debts (§4)
def _debt_orders(c):
    o = c.orders
    if 'order_total' not in o or ('paid_amount' not in o and 'payments' not in c.v.frames):
        raise Unanswerable('shop does not record payments / debts')
    o = o[o['order_status'] != 'huỷ']
    if 'payment_method' in o:
        o = o[~o['payment_method'].map(is_cod_or_marketplace)]
    return o


def _paid_until(c, orders, until: date):
    if 'payments' in c.v.frames:
        pay = c.v.frames['payments']
        pay = pay[pd.to_datetime(pay['pay_date']) <= pd.Timestamp(until)]
        paid = pay.groupby('order_id')['amount'].sum()
        return orders['order_id'].map(paid).fillna(0.0)
    return orders['paid_amount'].fillna(0.0)


def _debts_at(c, until: date):
    o = _debt_orders(c)
    o = o[pd.to_datetime(o['order_date']) <= pd.Timestamp(until)].copy()
    o['debt'] = o['order_total'] - _paid_until(c, o, until)
    o = o[o['debt'] > 0.5]
    o['age'] = (pd.Timestamp(until) - pd.to_datetime(o['order_date'])).dt.days
    return o


def _as_of(c, q):
    d = q.get('as_of') or c.today.isoformat()
    return min(date.fromisoformat(str(d)[:10]), c.today)


def m_debt_total(c, p, f, q):
    o = _debts_at(c, _as_of(c, q))
    if q.get('min_age') is not None:
        o = o[o['age'] > q['min_age']]
    return o['debt'].sum()


def m_debtor_count(c, p, f, q):
    o = _debts_at(c, _as_of(c, q)).dropna(subset=['customer_key'])
    return o['customer_key'].nunique()


def m_debt_table(c, p, f, q):
    o = _debts_at(c, _as_of(c, q)).dropna(subset=['customer_key'])
    g = o.groupby('customer_key').agg(v=('debt', 'sum'), name=('customer', 'first')).reset_index()
    g = _rank(g, 'v', 'customer_key').head(int(q.get('k') or 5))
    return {'columns': ['khach_hang', 'so_tien_no'], 'rows': [[n, money(v)] for n, v in zip(g['name'], g['v'])]}


def m_debt_aging(c, p, f, q):
    o = _debts_at(c, _as_of(c, q))
    edges = q.get('buckets') or [7, 15]
    out, lo = [], -1
    for hi in edges:
        out.append(o[(o['age'] > lo) & (o['age'] <= hi)]['debt'].sum())
        lo = hi
    out.append(o[o['age'] > lo]['debt'].sum())
    return [money(v) for v in out]


def _credit_orders(c):
    o = _debt_orders(c)
    if 'payment_method' in o:
        credit = o['payment_method'].map(lambda s: bool(re.search(r'ghi no|\bno\b|cong no|tra sau|credit', plain(s))))
        if credit.any():
            o = o[credit]
    return o


def m_new_debt_and_repaid(c, p, f, q):
    o = _credit_orders(c)
    if f.get('customer'):
        o = o[o['customer_key'].isin(c.customer_keys(f['customer']))]
    pay = c.v.frames.get('payments')
    if pay is None:
        raise Unanswerable('no payment ledger')
    pay = pay[pay['order_id'].isin(o['order_id'])].merge(o[['order_id', 'order_date']], on='order_id')
    same_day = pay[pd.to_datetime(pay['pay_date']) == pd.to_datetime(pay['order_date'])].groupby('order_id')['amount'].sum()
    d = pd.to_datetime(o['order_date'])
    in_p = o[(d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end))]
    new_debt = (in_p['order_total'] - in_p['order_id'].map(same_day).fillna(0)).clip(lower=0).sum()
    later = pay[pd.to_datetime(pay['pay_date']) > pd.to_datetime(pay['order_date'])]
    pd_ = pd.to_datetime(later['pay_date'])
    repaid = later[(pd_ >= pd.Timestamp(p.start)) & (pd_ < pd.Timestamp(p.end))]['amount'].sum()
    if q.get('part') == 'repaid':
        return repaid
    if q.get('part') == 'new':
        return new_debt
    return [money(new_debt), money(repaid)]


# ---- purchases / stock (§5)
def _purchases(c):
    if 'purchases' not in c.v.frames and 'purchase_lines' not in c.v.frames:
        raise Unanswerable('shop has no purchase records')
    return c.v.frames.get('purchases'), c.v.frames.get('purchase_lines')


def _line_value(x):
    """Purchase line value: the line total when recorded, else qty x unit cost."""
    if 'line_total' in x and x['line_total'].notna().any():
        return x['line_total'].fillna(x['qty'] * x['unit_cost'] if {'qty', 'unit_cost'} <= set(x) else 0).sum()
    if {'qty', 'unit_cost'} <= set(x):
        return (x['qty'] * x['unit_cost']).sum()
    raise Unanswerable('purchase lines carry no value')


def m_purchase_total(c, p, f, q):
    if f.get('product'):                               # one product: its purchase lines only
        return _line_value(_plines_for(c, f['product'], p))
    hdr, lines = _purchases(c)
    src = hdr if hdr is not None and 'total' in hdr else lines
    if src is None:
        raise Unanswerable('no purchase totals')
    d = pd.to_datetime(src['purchase_date'])
    x = src[(d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end)) & ~src['cancelled']]
    return x['total'].sum() if 'total' in x else _line_value(x)


def m_top_supplier(c, p, f, q):
    hdr, lines = _purchases(c)
    src = hdr if hdr is not None else lines
    if 'supplier' not in src:
        raise Unanswerable('no supplier column')
    d = pd.to_datetime(src['purchase_date'])
    x = src[(d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end)) & ~src['cancelled']]
    col = 'total' if 'total' in x else 'line_total'
    g = x.groupby('supplier')[col].sum().reset_index().sort_values([col, 'supplier'], ascending=[False, True])
    return str(g['supplier'].iloc[0])


def _plines_for(c, product, p=None):
    _, lines = _purchases(c)
    if lines is None:
        raise Unanswerable('no purchase lines')
    keys = c.product_keys(product)
    x = lines[lines['product_key'].isin(keys) & ~lines['cancelled']]
    if p is not None:
        d = pd.to_datetime(x['purchase_date'])
        x = x[(d >= pd.Timestamp(p.start)) & (d < pd.Timestamp(p.end))]
    return x


def m_avg_purchase_price(c, p, f, q):
    x = _plines_for(c, f.get('product'), p)
    if x.empty:
        raise Unanswerable('no purchase of that product in period')
    per_base = (x['qty'] * x['unit_cost']).sum() / x['qty_base'].sum()
    factor = 1.0
    if q.get('unit'):
        hit = x[x['unit'].map(plain) == plain(q['unit'])]
        factor = float(hit['factor'].iloc[0]) if len(hit) else _unit_factor(c, f.get('product'), q['unit'])
    else:
        factor = float(x['factor'].mode().iloc[0])
    return per_base * factor


def _unit_factor(c, product, unit):
    x = c.lines[c.lines['product_key'].isin(c.product_keys(product))]
    hit = x[x['unit'].map(plain) == plain(unit)]
    return float(hit['factor'].iloc[0]) if len(hit) else 1.0


def _big_unit_factor(c, keys):
    x = c.lines[c.lines['product_key'].isin(keys)]
    big = x[x['factor'] > 1]
    pl = c.v.frames.get('purchase_lines')
    if big.empty and pl is not None:
        big = pl[pl['product_key'].isin(keys) & (pl['factor'] > 1)]
    return float(big['factor'].max()) if len(big) else None


def stock_at(c, keys, day: date):
    st = c.v.frames.get('stock_snapshot')
    if st is None:
        raise Unanswerable('no stock report')
    on_hand = st[st['product_key'].isin(keys)]['qty_on_hand'].sum()
    end = c.v.data_end or day
    if day >= end:
        return float(on_hand)
    after = lambda d: (pd.to_datetime(d) > pd.Timestamp(day)) & (pd.to_datetime(d) <= pd.Timestamp(end))
    pl = c.v.frames.get('purchase_lines')
    bought = pl[pl['product_key'].isin(keys) & ~pl['cancelled'] & after(pl['purchase_date'])]['qty_base'].sum() \
        if pl is not None else 0.0
    sl = c.lines
    sold = sl[sl['product_key'].isin(keys) & (sl['order_status'] != 'huỷ') & after(sl['order_date'])]['qty_base'].sum()
    return float(on_hand - bought + sold)


def m_stock(c, p, f, q):
    keys = c.product_keys(f.get('product'))
    qty = stock_at(c, keys, _as_of(c, q))
    if q.get('split_big_unit'):
        factor = _big_unit_factor(c, keys)
        if not factor:
            return [num(qty), 0]
        return [int(qty // factor), num(qty - factor * (qty // factor))]
    if q.get('unit'):
        qty = qty / _unit_factor(c, f.get('product'), q['unit'])
    return qty


def m_stock_value(c, p, f, q):
    prods = c.v.frames['products']
    if 'unit_cost' not in prods:
        raise Unanswerable('no unit cost in catalogue')
    day = _as_of(c, q)
    total = 0.0
    for key, cost in prods[['product_key', 'unit_cost']].dropna().itertuples(index=False):
        qty = stock_at(c, {key}, day)
        if qty > 0:
            total += qty * cost
    return total


def m_purchase_minus_sales(c, p, f, q):
    keys = c.product_keys(f.get('product'))
    bought = _plines_for(c, f.get('product'), p)['qty_base'].sum()
    sold = c.sel_lines(p, f)['qty_base'].sum()
    return bought - sold


# ---- price change effect (§5)
def m_price_effect(c, p, f, q):
    keys = c.product_keys(f.get('product'))
    day = q.get('date')
    if not day:
        x = c.lines[c.lines['product_key'].isin(keys)].dropna(subset=['unit_price_base'])
        daily = x.groupby('order_date')['unit_price_base'].agg(lambda s: s.mode().iloc[0]).sort_index()
        target = q.get('new_price')
        rises = [d for (d0, p0), (d, p1) in zip(daily.items(), list(daily.items())[1:]) if p1 > p0
                 and (target is None or abs(p1 - target) < 0.5)]
        if not rises:
            raise NeedsReview('price increase date not found')
        day = rises[0]
    day = date.fromisoformat(str(day)[:10])
    n = int(q.get('days') or 7)
    sl = c.lines[c.lines['product_key'].isin(keys) & c.lines['counts_for_revenue']]
    d = pd.to_datetime(sl['order_date'])
    after = sl[(d >= pd.Timestamp(day)) & (d < pd.Timestamp(day + timedelta(days=n)))]['qty_base'].sum()
    before = sl[(d >= pd.Timestamp(day - timedelta(days=n))) & (d < pd.Timestamp(day))]['qty_base'].sum()
    if before == 0:
        raise Unanswerable('no sales before the price change')
    return 100.0 * (after - before) / before


def m_expiring(c, p, f, q):
    """§6 nhà thuốc: lots with expiry in [today, today+N]. Needs lot/expiry columns."""
    has = any('expiry_date' in c.v.frames.get(t, pd.DataFrame()).columns for t in ('purchase_lines', 'stock_snapshot'))
    if not has:
        raise Unanswerable('shop does not record expiry dates / lots')
    raise NeedsReview('lot-level stock not implemented yet')


def m_delivery_batches(c, p, f, q):
    """Rulebook "Giao nhiều đợt": rounds delivered in the period = (order, round) pairs whose delivery date falls in
    it; every round of every order counts once, also for orders returned later."""
    d = c.v.frames.get('deliveries')
    if d is None:
        raise Unanswerable('shop has no delivery book')
    if q.get('min_batches') is not None:
        raise NeedsReview('orders by number of delivery rounds: not in the rulebook as written')
    dd = pd.to_datetime(d['delivery_date'])
    x = d[(dd >= pd.Timestamp(p.start)) & (dd < pd.Timestamp(p.end))]
    return int(x[['order_id', 'batch']].drop_duplicates().shape[0])


def m_net_profit(c, p, f, q):
    if 'expenses' not in c.v.frames:
        raise Unanswerable('shop has no expense book')
    raise NeedsReview('expense book mapping not implemented yet')


# ------------------------------------------------------------------ service books (rulebook "Sửa xe" / service shops)
def _tickets(c, p, f):
    if not getattr(c.v, 'service_book', False):
        raise NeedsReview('shop keeps no service book')
    return c.sel_orders(p, {k: v for k, v in f.items() if k not in LINE_KEYS})


def m_commission(c, p, f, q):
    """Commission of a worker = his/her % (staff list) x total money of the tickets he/she did in the period.
    No worker named -> table of every worker, highest first; params.k=1 -> the worker with the highest."""
    rates = c.v.frames.get('staff_rates')
    if rates is None or rates.empty:
        raise Unanswerable('shop records no commission rate')
    o = _tickets(c, p, f)
    got = o.groupby('staff')['revenue'].sum()
    rows = [(n, float(r) / 100.0 * float(got.get(n, 0.0))) for n, r in zip(rates['staff'], rates['pct'])]
    if f.get('staff'):
        return money(sum(v for n, v in rows if plain(n) == plain(f['staff'])))
    rows.sort(key=lambda t: (-t[1], t[0]))
    if q.get('k') and int(q['k']) == 1 and not q.get('table'):
        return rows[0][0]
    return {'columns': ['nhan_vien', 'hoa_hong'], 'rows': [[n, money(v)] for n, v in rows]}


def m_top_staff(c, p, f, q):
    """Worker with the most tickets (warranty tickets included), the most money, or the most working days."""
    o = _tickets(c, p, {k: v for k, v in f.items() if k != 'staff'}).dropna(subset=['staff'])
    if o.empty:
        raise Unanswerable('no tickets')
    by = q.get('by') or 'orders'
    if by == 'revenue':
        g = o.groupby('staff')['revenue'].sum()
    elif by == 'days':
        g = o.groupby('staff')['order_date'].nunique()
    else:
        g = o.groupby('staff')['order_id'].nunique()
    g = g.reset_index(name='v').sort_values(['v', 'staff'], ascending=[q.get('order') == 'asc', True])
    return g['staff'].iloc[0]


def model_matches(model, query) -> bool:
    """Vehicle model of a ticket vs the model asked: same up to case/spaces, or written short (last word 'alpha' of
    'wave alpha', prefix 'ex' of one-word 'exciter', initials 'ab' of 'air blade') -> same model (rulebook "Dòng xe").
    A first word alone ('wave' for 'wave alpha') is a family, not the model."""
    if not isinstance(model, str) or not model:
        return False
    a, b = re.sub(r'[^a-z0-9]', '', plain(model)), re.sub(r'[^a-z0-9]', '', plain(query))
    words = [w for w in re.split(r'[^a-z0-9]+', plain(query)) if w]
    if not a or not b:
        return False
    if a == b:
        return True
    if len(words) > 1:
        return a == words[-1] or a == ''.join(w[0] for w in words)
    return len(a) >= 2 and b.startswith(a)


def m_vehicle_count(c, p, f, q):
    """Distinct vehicles (plates) brought in the period, warranty visits included; model filter = filters.product.
    params.min_visits: only vehicles with that many PAID tickets (warranty tickets are not a visit)."""
    o = _tickets(c, p, f)
    if 'plate' not in o:
        raise Unanswerable('shop records no plate')
    model = q.get('model') or f.get('product')
    if model:
        o = o[o['vehicle_model'].map(lambda m: model_matches(m, model))]
        if o.empty:
            raise NeedsReview(f'no vehicle model {model!r}')
    if q.get('min_visits'):
        o = o[o['revenue'] > 0]
        n = o.groupby('plate').size()
        return int((n >= int(q['min_visits'])).sum())
    return int(o['plate'].nunique())


def m_warranty_count(c, p, f, q):
    return int(_tickets(c, p, f)['warranty'].sum())


def m_warranty_rate(c, p, f, q):
    """Warranty tickets dated in the period / tickets with money in the same period (rulebook "Bảo hành")."""
    o = _tickets(c, p, f)
    paid = int((o['revenue'] > 0).sum())
    if paid == 0:
        raise Unanswerable('no paid tickets')
    return 100.0 * o['warranty'].sum() / paid


METRICS = {
    'commission': (m_commission, 'name'), 'top_staff': (m_top_staff, 'name'),
    'vehicle_count': (m_vehicle_count, 'count'), 'warranty_count': (m_warranty_count, 'count'),
    'warranty_rate': (m_warranty_rate, 'percent'),
    'expiring': (m_expiring, 'list'), 'net_profit': (m_net_profit, 'money'),
    'delivery_batches': (m_delivery_batches, 'count'),
    'revenue': (m_revenue, 'money'), 'order_count': (m_order_count, 'count'),
    'cancelled_count': (m_cancelled_count, 'count'), 'cancel_rate': (m_cancel_rate, 'percent'),
    'avg_order_value': (m_avg_order_value, 'money'), 'quantity': (m_quantity, 'number'),
    'unit_price': (m_unit_price, 'money'), 'top_products': (m_top_products, 'name'),
    'top_customers': (m_top_customers, 'name'), 'best_day': (m_best_day, 'date'),
    'products_min_orders': (m_products_min_orders, 'count'),
    'customers_min_orders': (m_customers_min_orders, 'count'),
    'gross_profit': (m_gross_profit, 'money'), 'unsold_products': (m_unsold_products, 'count'),
    'days_min_revenue': (m_days_min_revenue, 'count'),
    'debt_total': (m_debt_total, 'money'), 'debtor_count': (m_debtor_count, 'count'),
    'debt_table': (m_debt_table, 'table'), 'debt_aging': (m_debt_aging, 'list'),
    'new_debt_and_repaid': (m_new_debt_and_repaid, 'list'),
    'purchase_total': (m_purchase_total, 'money'), 'top_supplier': (m_top_supplier, 'name'),
    'avg_purchase_price': (m_avg_purchase_price, 'money'), 'stock': (m_stock, 'number'),
    'stock_value': (m_stock_value, 'money'), 'purchase_minus_sales': (m_purchase_minus_sales, 'number'),
    'price_effect': (m_price_effect, 'percent'),
}
SERVICE_METRICS = {'commission', 'top_staff', 'vehicle_count', 'warranty_count', 'warranty_rate'}
STAFF_PREFIX = re.compile(r'^(?:tho|nhan vien|nv|ktv|ky thuat vien)\s+')


def _staff_named_elsewhere(c, f: dict) -> dict:
    """A worker's name put in the customer / group filter ("thợ Đàm Lan An", "Lương Chi Đức bán ...") -> staff filter,
    when it is exactly a staff name of the shop and not a customer / group name."""
    lines = c._lines
    if lines is None or 'staff' not in lines or f.get('staff'):
        return f
    staff = {plain(s): s for s in lines['staff'].dropna().unique()}
    for key in ('customer', 'group', 'customer_group'):
        v = f.get(key)
        if not isinstance(v, str):
            continue
        k = STAFF_PREFIX.sub('', plain(v)).strip()
        known = {plain(x) for x in lines[key].dropna().unique()} if key in lines else set()
        if k in staff and k not in known:
            f = {**{a: b for a, b in f.items() if a != key}, 'staff': staff[k]}
            break
    return f


ORDER_IDENTITY = {'order_count', 'cancelled_count', 'cancel_rate', 'avg_order_value',
                  'products_min_orders', 'customers_min_orders'}
ITEM_LEVEL = {'quantity', 'unit_price', 'top_products', 'products_min_orders', 'gross_profit',
              'unsold_products', 'stock', 'stock_value', 'purchase_minus_sales', 'price_effect'}
NO_PERIOD = {'debt_total', 'debtor_count', 'debt_table', 'debt_aging', 'stock', 'stock_value', 'price_effect'}
SELF_COMPARING = {'price_effect'}


def _format(value, kind, q):
    if kind == 'money':
        return money(value), 'number'
    if kind == 'percent':
        return pct(value), 'percent'
    if kind == 'count':
        return int(value), 'number'
    if kind == 'number':
        if isinstance(value, list):
            return value, 'list'
        return num(value), 'number'
    if kind == 'date':
        return value, 'date'
    if kind == 'name':
        if isinstance(value, dict):                    # commission: table of every worker
            return value, 'table'
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            return money(value), 'number'              # commission of one worker
        return value, ('list' if isinstance(value, list) else 'string')
    if kind == 'table':
        return value, 'table'
    if kind == 'list':
        return value, 'list'
    return value, 'string'


def run(views: Views, intent: dict, today, calendar: Calendar | None = None) -> dict:
    undefined = (intent.get('params') or {}).get('undefined_term')
    if undefined:                                      # set by slots.apply_cues: a judgement no data defines
        raise NeedsReview(f'undefined judgement {undefined!r}')
    c = Ctx(views, today, calendar)
    metric = intent['metric']
    if metric not in METRICS:
        raise NeedsReview(f'metric {metric!r} not in library')
    fn, kind = METRICS[metric]
    if metric in ORDER_IDENTITY and getattr(views, 'no_order_id', False):
        raise Unanswerable('shop records no order number: orders cannot be counted')
    if getattr(views, 'no_line_items', False) and (metric in ITEM_LEVEL or any(
            _set((intent.get('filters') or {}).get(k)) for k in LINE_KEYS)):
        raise Unanswerable('shop has no item lines')
    f = intent.get('filters') or {}
    q = intent.get('params') or {}
    f = _staff_named_elsewhere(c, f)
    if getattr(views, 'service_book', False) and metric not in SERVICE_METRICS and (
            metric in ITEM_LEVEL or metric in ('top_customers', 'customers_min_orders')
            or any(_set(f.get(k)) for k in LINE_KEYS)):
        # customers of a service book are vehicles (plates); jobs are free text
        # jobs are free text with no price per job ("Sửa điện" excludes bulbs...): an item-level answer would guess
        raise NeedsReview('service book: jobs are free text')
    if metric in ('new_debt_and_repaid',) and q.get('part') in ('new', 'repaid'):
        kind = 'money'
    if metric == 'customers_min_orders' and q.get('as_percent'):
        kind = 'percent'
    if metric == 'best_day' and q.get('by') == 'hour':
        kind = 'number'                                # the start hour of the peak one-hour slot
    compare = intent.get('compare')
    periods = intent.get('periods') or ([intent['period']] if intent.get('period') else [])
    split = intent.get('split_by')
    if split and not compare and len(periods) == 1 and metric not in NO_PERIOD:
        key, values = split                            # one number per named value, in the order of the question
        p = c.period(periods[0])
        return {'answer': [_format(fn(c, p, {**f, key: v}, q), kind, q)[0] for v in values], 'type': 'list'}
    if metric in SELF_COMPARING:
        # the metric already compares N days after the event with N days before it (rulebook §5): a 'compare' or a
        # period the model added only restates that; the window length may sit in the period ({"days": 30})
        compare = None
        if not q.get('days'):
            n = next((s.get('days') or s.get('n') for s in periods if isinstance(s, dict) and (s.get('days') or s.get('n'))), None)
            if n:
                q = {**q, 'days': int(n)}

    def value_for(spec):
        p = c.period(spec) if spec else None
        return fn(c, p, f, q)

    if metric in NO_PERIOD and not compare:
        if periods and periods[0].get('type') == 'as_of':
            q = {**q, 'as_of': periods[0].get('date')}
        elif periods and periods[0].get('type') in ('today',):
            q = {**q, 'as_of': c.today.isoformat()}
        return dict(zip(('answer', 'type'), _format(fn(c, None, f, q), kind, q)))
    if not periods:
        raise NeedsReview('no period')
    mode = intent.get('output')
    if compare:
        cur_p = c.period(periods[0])
        if compare == 'explicit' and len(periods) > 1:
            base_p = c.period(periods[1])
        elif compare == 'same_period_last_year' and periods[0].get('type') == 'tet':
            base_p = c.period({**periods[0], 'year': int(periods[0]['year']) - 1})   # Tết of the previous lunar year
        else:
            base_p = c.clip(previous_period(resolve(periods[0], c.today, c.cal), compare))
        cur, base = fn(c, cur_p, f, q), fn(c, base_p, f, q)
        if mode == 'diff':
            return dict(zip(('answer', 'type'), _format(cur - base, kind if kind != 'percent' else 'number', q)))
        if base == 0:
            raise Unanswerable('comparison base is zero')
        return {'answer': pct(100.0 * (cur - base) / base), 'type': 'percent'}
    if len(periods) > 1:
        values = [fn(c, c.period(s), f, q) for s in periods]
        if mode == 'increasing':
            return {'answer': all(b > a for a, b in zip(values, values[1:])), 'type': 'boolean'}
        if mode in ('argmax', 'argmin'):
            idx = int(np.argmax(values) if mode == 'argmax' else np.argmin(values))
            p = resolve(periods[idx], c.today, c.cal)
            return {'answer': p.start.strftime('%Y-%m') if p.kind == 'month' else p.start.isoformat(), 'type': 'date'}
        return {'answer': [_format(v, kind, q)[0] for v in values], 'type': 'list'}
    if intent.get('share_of_total'):                   # part / whole of the same metric
        if not any(v not in (None, '', [], {}) for v in (f or {}).values()):
            # no part is named (its filter was dropped or never read): part = whole = 100%, never the question
            raise NeedsReview('share of the total with no part named')
        p = c.period(periods[0])
        part = fn(c, p, f, q)
        whole = fn(c, p, {}, q)
        if whole == 0:
            raise Unanswerable('total is zero')
        return {'answer': pct(100.0 * part / whole), 'type': 'percent'}
    if intent.get('shift_compare'):
        p = c.period(periods[0])
        aft = fn(c, p, {**f, 'shift': 'chieu'}, q)
        morn = fn(c, p, {**f, 'shift': 'sang'}, q)
        if morn == 0:
            raise Unanswerable('no morning sales')
        return {'answer': pct(100.0 * (aft - morn) / morn), 'type': 'percent'}
    return dict(zip(('answer', 'type'), _format(value_for(periods[0]), kind, q)))
