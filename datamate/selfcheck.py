"""Shop-level self-check after the views are built: was the shop READ right? (no question, no LLM).

A shop whose files were read wrong (sales split over tables nobody joined, lines counted as orders against the README,
months missing from the sales view) answers most questions wrong: -1 each. The old guard only saw this through the
share of "unanswerable" answers (> 20%), which a wrongly read shop can stay under. These checks look at the data:

  lost_sales  - tables with exactly the columns of the sales table (or the order table) that got no role, or another
                role inside a series of >= 3 such tables: their rows are sales the views do not see (one file per
                month nobody joined: 11 of 12 months lost);
  orders_vs_readme - every line counted as its own order (no order key found) while the README says the order's info
                is repeated on each of its lines / the lines of one order share a number;
  names       - the sold product names are mostly not in the catalogue's name column (a book writing abbreviations
                listed in another column: product questions ask about names the views never see);
  months      - the sales view stops long before the README's "Dữ liệu có đến hết dd/mm/yyyy", or has empty months
                between its first and last month.

Thresholds are set on the 24 train shops and every perturb family (all pass) with the control split_month_t without
the month join (must be caught); never on public. Nothing here names a shop, a file or a question.
"""
from __future__ import annotations

import re

import pandas as pd

from .values import name_key, plain

SALES_ENTITIES = ('sales_line', 'order')
LOST_SALES_MAX = 0.25          # share of sales-shaped rows outside the sales view
END_LAG_MAX_DAYS = 62          # README end date vs last sale
GAP_MONTHS_MAX = 0             # empty months between the first and the last month of sales
NAME_MATCH_MIN = 0.8           # sold product names found in the catalogue's name column (train: 1.0 on every shop)
NAME_MIN_SOLD = 20             # ... checked when both lists have at least this many names
MULTI_LINE_README = re.compile(r'lap lai (?:o|tren) (?:moi|tung|cac) dong|cac dong cung (?:ma|so|stt)|'
                               r'nhieu dong (?:cung|chung) (?:mot )?(?:don|hoa don|ma|so)')
README_END = re.compile(r'đến hết (?:ngày )?(\d{1,2})/(\d{1,2})/(\d{4})')


def shop_check(tables: dict, mapping: dict, views, readme_text: str = '') -> dict:
    """Returns {'signals': {...}, 'block': [reason, ...]} (empty block list = the shop looks read right)."""
    signals, block = {}, []
    ent = {n: (mapping[n].entity if n in mapping else None) for n in tables}
    rows = {n: len(t.frame) for n, t in tables.items()}
    cols = {n: frozenset(plain(str(h)) for h in t.headers) for n, t in tables.items()}

    sales = [n for n in tables if ent[n] in SALES_ENTITIES]
    # a table with the sales columns is lost when it has no role, or when it is one of a series (>= 3 tables with
    # these columns: one per period). A PAIR with two roles (sales book + purchase book written alike) is left alone.
    series = {s: sum(cols[n] == cols[s] for n in tables) for s in sales}
    lost = {n: rows[n] for s in sales for n in tables
            if n != s and cols[n] == cols[s] and ent[n] not in SALES_ENTITIES
            and (ent[n] is None or series[s] >= 3)}
    seen = sum(rows[n] for n in sales)
    share = sum(lost.values()) / max(sum(lost.values()) + seen, 1)
    signals['lost_sales'] = round(share, 3)
    if share > LOST_SALES_MAX:
        block.append(f'{len(lost)} table(s) with the columns of the sales table got no sales role '
                     f'({sum(lost.values())} rows, {share:.0%} of the sales-shaped rows)')

    text = plain(readme_text or '')
    multi = bool(MULTI_LINE_README.search(text))
    signals['no_order_id'] = bool(getattr(views, 'no_order_id', False))
    signals['readme_multi_line_orders'] = multi
    if signals['no_order_id'] and multi:
        block.append('each line counted as its own order, but the README says an order spans several lines')

    sl = views.frames.get('sales_lines') if views is not None else None
    # sold product names vs the catalogue's name column: on train every shop with a catalogue finds 100% of its sold
    # names there. A book writing names its own way (abbreviations listed in another column of the catalogue,
    # "Ghi tắt") answers every product / product-group question on names nobody asks about.
    cat = next((m for m in mapping.values() if m.entity == 'product' and 'product_name' in m.columns
                and m.table in tables), None)
    if cat is not None and sl is not None and 'product' in sl:
        listed = {name_key(v) for v in tables[cat.table].frame[cat.columns['product_name']].dropna().unique()}
        sold = {name_key(v) for v in sl['product'].dropna().unique()}
        if len(sold) >= NAME_MIN_SOLD and len(listed) >= NAME_MIN_SOLD:
            share = len(sold & listed) / len(sold)
            signals['sold_names_in_catalogue'] = round(share, 3)
            if share < NAME_MATCH_MIN:
                block.append(f'only {share:.0%} of the sold product names are in the catalogue '
                             f'({cat.table}.{cat.columns["product_name"]}): product names read wrong')
    if sl is not None and 'order_date' in sl and len(sl):
        d = pd.to_datetime(sl['order_date'], errors='coerce').dropna()
        if len(d):
            per = d.dt.to_period('M')
            counts = per.value_counts()
            gaps = [str(m) for m in pd.period_range(per.min(), per.max(), freq='M') if counts.get(m, 0) == 0]
            signals['gap_months'] = gaps
            if len(gaps) > GAP_MONTHS_MAX:
                block.append(f'sales view has empty months between its first and last month: {gaps}')
            m = README_END.search(readme_text or '')
            if m:
                end = pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                lag = int((end - d.max()).days)
                signals['end_lag_days'] = lag
                if lag > END_LAG_MAX_DAYS:
                    block.append(f'last sale {d.max().date()} is {lag} days before the README end date {end.date()}')
    return {'signals': signals, 'block': block}
