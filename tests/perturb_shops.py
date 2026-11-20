"""Robustness check without new data: rename headers / tables of a real shop and check the answers do not change.

python tests/perturb_shops.py --train-root data/train biz_101 biz_105 ... [--families accents case synonym order]

Families (each one is a way a NEW shop could write the same data):
  accents  - headers without Vietnamese accents ("Thành tiền" -> "Thanh tien")
  case     - CamelCase / snake_case headers ("ThanhTien", "thanh_tien")
  synonym  - other common Vietnamese header words (independent list below, NOT the mapper's synonym list)
  shuffle  - shuffled column order
  tablename- generic table names (sheet1, data_2, ...) instead of the file / sheet names (README follows)
  noreadme - README without column descriptions (a shop with a poor README)
  fill_down, fill_down_id, non_item_total, non_item_fee - (not in the default list) see ROW_FAMILIES
  short_names - (not in the default list) catalogue "Ghi tắt" column, sales book writes short names (ALIAS_FAMILIES)
  sheet_roles, sheet_roles_vi, sheet_roles_flat, sheet_roles_en, sheet_roles_plain - (not in the default list) side
             tables gathered into one workbook, one sheet per table named by its role (SHEET_FAMILIES)
  stt_order, stt_order_flat, stt_order_blank - (not in the default list) order codes replaced by a per-month order
             number "STT" (see STT_FAMILIES)
  rewrite, split_month, split_month_t, split_month_dot, split_month_en - (not in the default list) sales lines + order table written as one file per
             month and read back through ingest (see SPLIT_FAMILIES); `rewrite` is the no-split control.
  status, status2 - (not in the default list) order-status VALUES rewritten with other labels of the same meaning
             ("Đang vận chuyển", "Khách trả", "Cancelled"...), consistently in the shop and its README; the status
             column is the one mapped on the original shop, the meaning of an original value is rules.canonical_status
             (score-checked on train). Questions whose gold answer is a status label are excluded and counted.
The README is rewritten with the same renames, so column descriptions still point at the right columns.
A question counts as broken when it was correct on the original shop and is not correct on the variant.
Only use this on shops you may look at (not the held-out shops in kaggle/config.json `val_shops`).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from datamate.ingest import RawTable, read_business, read_readme   # noqa: E402
from datamate.mapper import mapping_to_json, resolve_mapping        # noqa: E402
from datamate.periods import Calendar                               # noqa: E402
from datamate.pipeline import Shop, answer, shop_names              # noqa: E402
from datamate.profile import profile_business                       # noqa: E402
from datamate.rules import build_views                              # noqa: E402
from datamate.scoring import is_correct, to_submission              # noqa: E402
from datamate.selfcheck import shop_check                           # noqa: E402
from datamate.values import plain, split_camel                      # noqa: E402
from scripted_intent import scripted_intent                         # noqa: E402

# Alternative header words a shop owner / another POS might use. Keys are accent-free, lower-case headers.
# Deliberately written from general knowledge of Vietnamese sales exports, not from datamate/concepts.py.
SYNONYMS = {
    'thanh tien': 'Tổng giá trị dòng', 'tri gia': 'Giá trị', 'so luong': 'SL bán', 'sl': 'Số lượng bán',
    'don gia': 'Giá 1 đơn vị', 'gia ban': 'Giá bán ra', 'ngay': 'Ngày chứng từ', 'ngay ban': 'Ngày xuất bán',
    'ngay dat hang': 'Ngày tạo đơn', 'thoi gian': 'Thời điểm', 'khach hang': 'Người mua',
    'ten khach hang': 'Họ tên khách', 'ma khach hang': 'Mã người mua', 'ma hang': 'Mã SP', 'ma hang hoa': 'Mã SP',
    'ten hang': 'Mặt hàng', 'ten hang hoa': 'Mặt hàng', 'ten san pham': 'Sản phẩm bán', 'trang thai': 'Tình trạng',
    'ma don hang': 'Số chứng từ', 'ma hoa don': 'Số hoá đơn', 'nhom hang': 'Ngành hàng', 'nhom hang hoa': 'Ngành hàng',
    'don vi tinh': 'ĐV bán', 'dvt': 'ĐV', 'giam gia': 'Chiết khấu', 'tong tien': 'Tổng cộng',
    'phuong thuc thanh toan': 'Hình thức TT', 'kenh ban': 'Nguồn bán', 'gia von': 'Giá gốc', 'ton kho': 'Tồn hiện tại',
    'nha cung cap': 'NCC', 'so luong quy doi': 'SL theo ĐV cơ bản', 'khach da tra': 'Đã thanh toán',
}


def _strip_accents(h: str) -> str:
    """Drop diacritics, keep the letter case ("Thành tiền" -> "Thanh tien", "MaKhachHang" unchanged)."""
    import unicodedata
    h = h.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(ch for ch in unicodedata.normalize('NFD', h) if not unicodedata.combining(ch))


def _camel(h: str) -> str:
    return ''.join(w.capitalize() for w in re.findall(r'[a-z0-9]+', plain(split_camel(h))))


def _snake(h: str) -> str:
    return '_'.join(re.findall(r'[a-z0-9]+', plain(split_camel(h))))


def rename_map(headers, family: str, rng: random.Random) -> dict:
    if family == 'accents':
        return {h: _strip_accents(h) for h in headers}
    if family == 'case':
        style = _camel if rng.random() < 0.5 else _snake
        return {h: style(h) for h in headers}
    if family == 'synonym':
        return {h: SYNONYMS.get(plain(h), h) for h in headers}
    return {h: h for h in headers}


def perturb(tables: dict, readme_text: str, family: str, seed: int):
    rng = random.Random(seed)
    out, text = {}, readme_text
    for i, (name, t) in enumerate(tables.items()):
        ren = rename_map(t.headers, family, rng)
        used, final = set(), {}
        for h in t.headers:                       # keep headers unique after renaming
            new = ren[h]
            while new in used:
                new += '_'
            used.add(new)
            final[h] = new
        frame = t.frame.rename(columns=final)
        headers = [final[h] for h in t.headers]
        new_name = name
        if family in ('shuffle', 'order'):
            data_cols = [c for c in frame.columns if c in headers]
            rng.shuffle(data_cols)
            frame = frame[data_cols + [c for c in frame.columns if c not in headers]]
            headers = data_cols
        if family in ('tablename', 'order'):
            new_name = f'sheet{i + 1}' if i % 2 == 0 else f'data_{i + 1}'
            # a real shop's README names its own files: rename the file references with the table
            for src in t.sources:
                fname = src.split(':')[0]
                stem, dot, ext = fname.rpartition('.')
                text = text.replace(f'`{fname}`', f'`{new_name}.{ext}`') if dot else text
            text = text.replace(f'`{name}.', f'`{new_name}.')          # database notes `table.Column`
        out[new_name] = RawTable(new_name, frame, headers, list(t.sources))
        for old, new in sorted(final.items(), key=lambda kv: -len(kv[0])):
            if old != new:
                text = text.replace(f'**{old}**', f'**{new}**').replace(f'.{old}`', f'.{new}`')
    if family == 'noreadme':                       # README without column descriptions (only the free text)
        text = '\n'.join(l for l in text.splitlines() if not re.match(r'^\s*[-*]\s*\*\*', l) and '`' not in l)
    return out, text


# Other ways a shop / POS writes the four order statuses (general Vietnamese e-commerce wording, NOT datamate/rules.py).
# Several labels per meaning: distinct original values of one meaning get distinct labels (nothing is merged).
# Some labels contain look-alike substrings on purpose ("vận CHUYển" holds "huy" once accents are dropped).
STATUS_WORDS = {
    'status': {'hoàn thành': ['Đã giao xong', 'Thành công', 'Giao thành công'],
               'huỷ': ['Khách huỷ', 'Đã hủy đơn', 'Hủy bỏ'],
               'trả hàng': ['Khách trả', 'Hoàn hàng', 'Trả lại hàng'],
               'đang giao': ['Đang vận chuyển', 'Chờ xác nhận', 'Đang giao hàng']},
    'status2': {'hoàn thành': ['Hoàn tất', 'Đã nhận hàng', 'Done'],
                'huỷ': ['Bị hủy', 'Cancelled', 'Huỷ đơn'],
                'trả hàng': ['Hoàn trả', 'Returned', 'Khách trả lại'],
                'đang giao': ['Đang chuyển phát', 'Đang xử lý', 'Chờ lấy hàng']},
}
STATUS_ENTITIES = ('sales_line', 'order')


def status_columns(mapping) -> list[tuple[str, str]]:
    """(table, header) of the order-status columns, as mapped on the ORIGINAL shop (the mapping is score-checked)."""
    return [(n, m.columns['status']) for n, m in mapping.items()
            if m.entity in STATUS_ENTITIES and 'status' in (m.columns or {})]


def status_relabel(tables, mapping, family: str) -> dict:
    """original status value -> new label of the same meaning (meaning of the original from rules.canonical_status)."""
    from datamate.rules import canonical_status
    values = set()
    for tname, col in status_columns(mapping):
        if tname in tables and col in tables[tname].frame:
            values |= {str(v) for v in tables[tname].frame[col].dropna().unique() if str(v).strip()}
    used, out = Counter(), {}
    for v in sorted(values):
        meaning = canonical_status(v)
        labels = STATUS_WORDS[family].get(meaning)
        if not labels:
            continue                                  # unclassified: kept (counted by the caller)
        out[v] = labels[used[meaning] % len(labels)]
        if used[meaning] >= len(labels):              # more distinct values than labels: keep them distinct
            out[v] += f' ({used[meaning] // len(labels) + 1})'
        used[meaning] += 1
    return out


def perturb_status(tables: dict, readme_text: str, mapping, family: str):
    relabel = status_relabel(tables, mapping, family)
    cols = status_columns(mapping)
    out = {}
    for name, t in tables.items():
        frame = t.frame
        for tname, col in cols:
            if tname == name and col in frame:
                frame = frame.copy()
                frame[col] = frame[col].map(lambda v: relabel.get(str(v), v) if v is not None and str(v) in relabel else v)
        out[name] = RawTable(name, frame, list(t.headers), list(t.sources))
    text = readme_text
    if relabel:                                    # README names the same values -> rename them too (one pass)
        alt = '|'.join(re.escape(o) for o in sorted(relabel, key=len, reverse=True))
        text = re.sub(rf'(?<!\w)(?:{alt})(?!\w)', lambda mt: relabel[mt.group(0)], text)
    return out, text, relabel


def answer_is_status(g, values) -> bool:
    """Gold answer that IS a status label (it would change with the relabelling): excluded from the count."""
    if not g or g.get('type') == 'unanswerable':
        return False
    ans = g.get('answer')
    items = ans if isinstance(ans, list) else [ans]
    keys = {plain(v) for v in values}
    return any(plain(str(a)) in keys for a in items if a is not None)


# ---------------------------------------------------------------- split_month: sales split into one file per month
# Unlike the families above, these rewrite FILES and read them back with ingest.read_business, so file grouping
# (ingest._base_name), sheet names and the README file references are exercised the way a real shop would.
#   rewrite       - control: each sales/order table rewritten as one file of the same name (no split). Losses here
#                   come from the writer (title rows dropped, cell types), not from the split.
#   split_month   - sales lines (and the order table) split by month: `SoBanHang_2025_03.xlsx`, ... same columns;
#                   an order's lines go to the month of the order. Other tables untouched. README file names follow.
#   split_month_t - same split, other common naming: `SoBanHang_T03-2025.xlsx`.
#   split_month_dot - `SoBanHang T3.2025.xlsx` (space, month.year);  split_month_en - `SoBanHang_Mar_2025.xlsx`.
SPLIT_FAMILIES = ('rewrite', 'split_month', 'split_month_t', 'split_month_dot', 'split_month_en')
EN_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
SPLIT_ENTITIES = ('sales_line', 'order')


def _stem_base(stem: str) -> str:
    """'So_chi_tiet_ban_hang_2026' -> 'So_chi_tiet_ban_hang' (the same suffixes ingest groups on)."""
    return re.sub(r'(?:[_\-\s](?:\d{1,2}|20\d{2}))+$', '', stem) or stem


def _month_name(base: str, ym, family: str) -> str:
    if family == 'rewrite':
        return base
    if family == 'split_month_t':
        return f'{base}_T{ym.month:02d}-{ym.year}'
    if family == 'split_month_dot':
        return f'{base} T{ym.month}.{ym.year}'
    if family == 'split_month_en':
        return f'{base}_{EN_MONTHS[ym.month - 1]}_{ym.year}'
    return f'{base}_{ym.year}_{ym.month:02d}'


def row_months(tables, mapping) -> dict:
    """table -> monthly Period per row (aligned to the raw frame), for the sales line / order tables.
    Date from the table's own date column; lines without one take the month of their order. Rows still without a
    month (continuation rows of an order, blank dates) take the previous row's month in the same file/sheet."""
    import pandas as pd
    from datamate.mapper import TypedTables
    typed, out, by_id = TypedTables(tables), {}, {}
    order_first = sorted((n for n, m in mapping.items() if m.entity in SPLIT_ENTITIES and n in tables),
                         key=lambda n: mapping[n].entity != 'order')
    for name in order_first:
        m, t = mapping[name], tables[name]
        hdr = m.columns.get('order_date') or m.columns.get('order_time')
        months = pd.Series([None] * len(t.frame), index=t.frame.index, dtype=object)
        if hdr:
            d = pd.to_datetime(typed.get(name, hdr, 'date'), errors='coerce')
            months = d.dt.to_period('M').astype(object).where(d.notna(), None)
        oid = m.columns.get('order_id')
        if oid and m.entity == 'order':
            ids = t.frame[oid].astype(str).str.strip()
            by_id.update({i: mo for i, mo in zip(ids, months) if mo is not None})
        elif oid and by_id:
            ids = t.frame[oid].astype(str).str.strip()
            from_order = ids.map(by_id)
            months = months.where(months.notna(), from_order)
        months = months.groupby([t.frame['_file'], t.frame['_sheet']], sort=False).transform(lambda s: s.ffill().bfill())
        if months.notna().mean() >= 0.5:
            out[name] = months
    return out


def split_month(folder: Path, tables, mapping, readme_text: str, family: str, work: Path):
    """Write the shop with its sales tables split by month into `work`, read it back. Returns tables, README, info."""
    import shutil
    import pandas as pd
    months = row_months(tables, mapping)
    split = {n for n in months if not any(s.split(':')[0].lower().endswith(('.sqlite', '.sqlite3', '.db'))
                                           for s in tables[n].sources)}
    info = {'split': sorted(split), 'skipped': sorted(n for n, m in mapping.items()
                                                      if m.entity in SPLIT_ENTITIES and n in tables and n not in split)}
    gone = {}                                          # file name -> sheets moved into month files
    for n in split:
        for s in tables[n].sources:
            f, _, sheet = s.partition(':')
            gone.setdefault(f, set()).add(sheet)
    work.mkdir(parents=True, exist_ok=True)
    for p in folder.rglob('*'):
        if not p.is_file() or p.name.lower().startswith('readme'):
            continue
        if p.name not in gone:
            shutil.copy2(p, work / p.name)
        elif p.suffix.lower() in ('.xlsx', '.xlsm'):  # keep the other sheets of a mixed workbook
            import openpyxl
            wb = openpyxl.load_workbook(p)
            if any(ws.title not in gone[p.name] for ws in wb.worksheets):
                for ws in [w for w in wb.worksheets if w.title in gone[p.name]]:
                    wb.remove(ws)
                wb.save(work / p.name)
    # (file base, ext, month) -> sheet -> [frames]
    buckets, owner, renamed = {}, {}, {}
    for n in sorted(split):
        t, mo = tables[n], months[n]
        for (f, sheet), part in t.frame.groupby(['_file', '_sheet'], sort=False):
            stem, ext = Path(f).stem, Path(f).suffix.lower()
            ext = '.xlsx' if ext in ('.xls', '.xlsm') else ext
            base = _stem_base(stem)
            for ym, rows in part.groupby(mo.loc[part.index].astype(str), sort=True):
                ym = pd.Period(ym, 'M') if ym not in ('None', 'nan', 'NaT') else None
                fname = (_month_name(base, ym, family) if ym is not None else f'{base}_khac') + ext
                key = (fname, sheet)
                if owner.setdefault(key, n) != n:      # two tables with one sheet name in one month file
                    key = (fname, f'{sheet}_{n}'[:31])
                buckets.setdefault(fname, {}).setdefault(key[1], []).append(rows[t.headers])
                renamed.setdefault(f, set()).add(fname)
    for fname, sheets in buckets.items():
        path = work / fname
        if path.suffix in ('.csv', '.tsv', '.txt'):
            frame = pd.concat(next(iter(sheets.values())), ignore_index=True)
            frame.to_csv(path, index=False, sep='\t' if path.suffix == '.tsv' else ',', encoding='utf-8')
        else:
            kept = {'mode': 'a', 'if_sheet_exists': 'new'} if path.exists() else {}   # workbook kept its other sheets
            with pd.ExcelWriter(path, engine='openpyxl', **kept) as xw:
                for sheet, frames in sheets.items():
                    pd.concat(frames, ignore_index=True).to_excel(xw, sheet_name=(sheet or 'Sheet1')[:31], index=False)
    text = readme_text
    for f, new in renamed.items():                    # README names the new files (first ... last of the months)
        new = sorted(new)
        phrase = f'`{new[0]}`' if len(new) == 1 else f'`{new[0]}` … `{new[-1]}` (mỗi tháng một file, cùng cột)'
        if f not in new and (work / f).exists():      # the original workbook still holds the other sheets
            phrase = f'`{f}` (các sheet khác); bán hàng: {phrase}'
        text = text.replace(f'`{f}`', phrase)
    info['files'] = sum(len(v) for v in renamed.values())
    (work / 'README.md').write_text(text, encoding='utf-8')   # read_business skips it; kept for inspection
    return read_business(work), text, info


#   stt_order       - a hand-kept book numbers its orders instead of coding them: the sales line table's order id
#                     column becomes "STT" = 1, 2, 3 ... restarting every month, one sheet per month ("T03-2025"),
#                     lines of an order kept together. Only shops whose sales lines are the only order-keyed table
#                     (no order header table, no payment / return / delivery table joined by order id).
#   stt_order_flat  - same, numbers continue over the whole book, one sheet.
#   stt_order_blank - as stt_order, the number written on the FIRST line of each order only (later lines blank).
# Questions naming an original order id (in the question or the gold answer) are excluded and counted.
STT_FAMILIES = ('stt_order', 'stt_order_flat', 'stt_order_blank')


def stt_order(tables, mapping, readme_text: str, family: str):
    """Returns (tables, README, info) or (None, None, reason) when the shop does not fit the family."""
    import pandas as pd
    lines_t = [n for n, m in mapping.items() if m.entity == 'sales_line' and 'order_id' in m.columns and n in tables]
    if len(lines_t) != 1:
        return None, None, 'không có đúng một bảng dòng hàng có mã đơn'
    if any(m.entity == 'order' for m in mapping.values()):
        return None, None, 'có bảng đơn riêng'
    joined = sorted(n for n, m in mapping.items() if n != lines_t[0] and m.entity and 'order_id' in m.columns)
    if joined:
        return None, None, f'bảng khác nối theo mã đơn {joined}'
    name = lines_t[0]
    t, h = tables[name], mapping[name].columns['order_id']
    months = row_months(tables, mapping).get(name)
    if months is None:
        return None, None, 'không có tháng cho dòng hàng'
    frame = t.frame.copy()
    where = [frame['_file'], frame['_sheet']]
    blank_cell = frame[h].isna() | (frame[h].astype(str).str.strip() == '')
    ids = frame[h].where(~blank_cell).groupby(where).ffill()
    ids = ids.astype(str).str.strip()
    # every line of an order goes to the order's month (a return line dated later stays with its order, as in
    # split_month): the month of the order's earliest dated line
    month = months.astype(str).where(months.notna(), None)
    month = month.groupby(ids).transform(lambda s: s.dropna().min() if s.notna().any() else 'None')
    first = pd.Series(range(len(frame)), index=frame.index).groupby(ids).transform('min')
    frame = frame.assign(_m=month.values, _first=first.values, _pos=range(len(frame)))
    frame = frame.sort_values(['_m', '_first', '_pos'], kind='stable')
    oid = ids.loc[frame.index]
    if family == 'stt_order_flat':
        number = pd.Series(pd.factorize(oid)[0] + 1, index=frame.index)
    else:
        number = oid.groupby(frame['_m']).transform(lambda s: pd.Series(pd.factorize(s)[0] + 1, index=s.index))
        frame['_sheet'] = frame['_m'].map(lambda p: f'T{int(p[5:7])}-{p[:4]}' if p[:4].isdigit() else 'Khac')
        frame['_file'] = frame['_file'].iloc[0]          # one workbook, one sheet per month (a sheet is in one file)
    new = 'STT' if 'STT' not in t.headers else 'Số TT'
    frame[h] = number.astype(float)
    frame.loc[blank_cell.loc[frame.index], h] = None     # a blank order cell (subtotal row ...) stays blank
    if family == 'stt_order_blank':
        frame.loc[frame[h].eq(frame[h].shift()) & frame['_sheet'].eq(frame['_sheet'].shift()), h] = None
    frame = frame.drop(columns=['_m', '_first', '_pos']).rename(columns={h: new}).reset_index(drop=True)
    headers = [new if x == h else x for x in t.headers]
    out = dict(tables)
    out[name] = RawTable(name, frame, headers, list(t.sources))
    text = readme_text.replace(f'**{h}**', f'**{new}**')
    text += (f'\n- **{new}**: số thứ tự đơn trong sổ; các dòng cùng {new} là một đơn'
             + ('' if family == 'stt_order_flat' else '; sổ mỗi tháng một sheet, mỗi tháng đánh lại từ 1') + '\n')
    return out, text, {'table': name, 'column': h, 'ids': set(ids[ids != 'nan'])}


def mentions_order_id(rec: dict, gold, ids: set) -> bool:
    toks = set(re.findall(r'[\w\-/.]+', rec.get('question', '') + ' ' + json.dumps(gold or {}, ensure_ascii=False)))
    return bool(toks & ids)


#   Row families (16/11, diagnostic): the sales line table is changed, then written back through split_month's writer
#   with no split (same files / sheets as the `rewrite` control) and read again through ingest.
#   fill_down      - hand-kept book "blank = same as the line above": on lines following a line of the SAME order,
#                    the order-level cells (date, customer, status, channel, staff, payment, time and every other
#                    column constant inside each order, except the line fields and the order id) are left blank.
#   fill_down_id   - same, the order id blank too.
#   non_item_total - a "Tổng" row after the last line of each month (first column "Tổng", line money = the month's
#                    sum, other cells blank). Every answer must stay.
#   non_item_fee   - after ~20% of the orders, one extra row: same order id, product "Phí ship" (+15 000) or "Voucher"
#                    (-10 000) as line money, quantity / price / date blank. The train rulebook says revenue has no
#                    shipping fee and no order discount; the report also gives the share kept on questions that do
#                    not depend on these rows (order counts, quantities, top products by quantity).
ROW_FAMILIES = ('fill_down', 'fill_down_id', 'non_item_total', 'non_item_fee')
WRITE_FAMILIES = SPLIT_FAMILIES + ROW_FAMILIES
LINE_FIELDS = ('product_name', 'product_code', 'unit', 'qty', 'qty_base', 'unit_price', 'line_discount', 'line_total',
               'unit_cost', 'delivery_date')
FEE_SAFE_METRICS = ('order_count', 'quantity', 'avg_items', 'cancelled_count', 'returned_count')


def row_transform(tables, mapping, family: str, seed: int = 0):
    """Returns (tables with the sales line table changed, info) or (None, reason)."""
    import pandas as pd
    from datamate.mapper import TypedTables
    names = [n for n, m in mapping.items() if m.entity == 'sales_line' and n in tables]
    if len(names) != 1:
        return None, 'không có đúng một bảng dòng hàng'
    name = names[0]
    m, t = mapping[name], tables[name]
    f = t.frame.copy()
    oid_h = m.columns.get('order_id')
    out = dict(tables)
    if family in ('fill_down', 'fill_down_id'):
        if not oid_h:
            return None, 'không có mã đơn'
        oid = f[oid_h].astype(str).str.strip().where(f[oid_h].notna())
        same_place = f['_file'].eq(f['_file'].shift()) & f['_sheet'].eq(f['_sheet'].shift())
        cont = oid.notna() & oid.eq(oid.shift()) & same_place
        if cont.sum() == 0:
            return None, 'không có đơn nhiều dòng liền nhau'
        line_h = {m.columns[x] for x in LINE_FIELDS if x in m.columns} | {oid_h}
        multi = oid[oid.map(oid.value_counts()) > 1]
        cols = []
        for h in t.headers:
            if h in line_h:
                continue
            per = f.loc[multi.index, h].astype(str).groupby(multi).nunique()
            if len(per) and (per <= 1).mean() >= 0.99:
                cols.append(h)                          # constant inside every order: an order-level cell
        if family == 'fill_down_id':
            cols.append(oid_h)
        f.loc[cont, cols] = None
        out[name] = RawTable(name, f, list(t.headers), list(t.sources))
        return out, {'table': name, 'blanked_rows': int(cont.sum()), 'columns': cols}
    money_h = m.columns.get('line_total')
    prod_h = m.columns.get('product_name') or m.columns.get('product_code')
    if not money_h or not prod_h:
        return None, 'không có cột thành tiền / tên hàng'
    f = f.reset_index(drop=True)
    pos = pd.Series(range(len(f)), dtype=float)
    keep = ['_file', '_sheet', '_row']
    if family == 'non_item_total':
        months = row_months(tables, mapping).get(name)
        if months is None:
            return None, 'không có tháng'
        money = TypedTables(tables).get(name, money_h, 'money').reset_index(drop=True)
        key = f['_file'].astype(str) + '|' + f['_sheet'].astype(str) + '|' + months.astype(str).reset_index(drop=True)
        block = key.ne(key.shift()).cumsum()
        last = key.ne(key.shift(-1))
        add = f.loc[last, keep].copy()
        for h in t.headers:
            add[h] = None
        add[t.headers[0]] = 'Tổng'
        add[money_h] = money.groupby(block).sum().loc[block[last]].values
    else:
        if not oid_h:
            return None, 'không có mã đơn'
        rng = random.Random(seed)
        oid = f[oid_h].astype(str)
        last = oid.ne(oid.shift(-1)) & f[oid_h].notna()
        last &= pd.Series([rng.random() < 0.2 for _ in range(len(f))])
        add = f.loc[last, keep].copy()
        for h in t.headers:
            add[h] = None
        ship = pd.Series([rng.random() < 0.5 for _ in range(len(add))], index=add.index)
        add[oid_h] = f.loc[last, oid_h]
        add[prod_h] = ship.map({True: 'Phí ship', False: 'Voucher'})
        add[money_h] = ship.map({True: 15000, False: -10000})
    add_pos = pos[last] + 0.5
    f2 = pd.concat([f.assign(_p=pos), add[list(f.columns)].assign(_p=add_pos.values)], ignore_index=True)
    f2 = f2.sort_values('_p', kind='stable').drop(columns='_p').reset_index(drop=True)
    out[name] = RawTable(name, f2, list(t.headers), list(t.sources))
    return out, {'table': name, 'inserted_rows': int(last.sum())}


#   short_names - (bản 2) the catalogue gets a "Ghi tắt" column (initials + the number words: "Sữa đặc Ông Thọ 380g" ->
#                 "SĐÔT 380g"); the sales book writes every other catalogue item by that short name. Answers must stay.
ALIAS_FAMILIES = ('short_names',)


def short_names(tables, mapping, readme_text: str):
    """Returns (tables, README, info) or (None, None, reason)."""
    import pandas as pd
    from datamate.values import name_key
    cats = [n for n, m in mapping.items() if m.entity == 'product' and 'product_name' in m.columns and n in tables]
    sales = [n for n, m in mapping.items() if m.entity == 'sales_line' and 'product_name' in m.columns and n in tables]
    if len(cats) != 1 or len(sales) != 1:
        return None, None, 'không có đúng một danh mục có tên hàng và một sổ bán có tên hàng'
    cn, sn = cats[0], sales[0]
    ct, st = tables[cn], tables[sn]
    ch, sh = mapping[cn].columns['product_name'], mapping[sn].columns['product_name']
    full = ct.frame[ch]
    short, used = [], set()
    for v in full:
        if not isinstance(v, str) or not v.strip():
            short.append(None)
            continue
        words = v.split()
        s = ''.join(w[0].upper() for w in words if not any(c.isdigit() for c in w))
        s = ' '.join([s] + [w for w in words if any(c.isdigit() for c in w)]).strip()
        base, i = s, 2
        while name_key(s) in used:
            s, i = f'{base} {i}', i + 1
        used.add(name_key(s))
        short.append(s)
    head = 'Ghi tắt' if 'Ghi tắt' not in ct.headers else 'Tên tắt'
    cf = ct.frame.copy()
    cf.insert(0, head, short)
    out = dict(tables)
    out[cn] = RawTable(cn, cf, [head] + list(ct.headers), list(ct.sources))
    keyed = sorted({name_key(v) for v in full if isinstance(v, str) and v.strip()})
    to_short = {name_key(f): s for f, s in zip(full, short) if s}
    pick = {k for i, k in enumerate(keyed) if i % 2 == 0}
    sf = st.frame.copy()
    keys = sf[sh].map(lambda v: name_key(v) if isinstance(v, str) else None)
    hit = keys.isin(pick)
    sf.loc[hit, sh] = keys[hit].map(to_short)
    out[sn] = RawTable(sn, sf, list(st.headers), list(st.sources))
    text = readme_text + f'\n- **{head}**: tên viết tắt của mặt hàng; sổ bán có khi ghi tên tắt thay cho tên hàng.\n'
    return out, text, {'catalogue': cn, 'renamed_lines': int(hit.sum()), 'items': len(pick)}


#   sheet_roles      - (bản 2) the shop's tables kept in their own one-table files (catalogue, customers, purchases,
#                      stock, and the sales lines / orders when in one file) are gathered into ONE workbook with a generic
#                      name ("QuanLy.xlsx"), one sheet per table named by its role: "DanhMuc", "KhachHang" ...
#   sheet_roles_vi   - sheet names with accents and spaces ("Danh mục", "Khách hàng")
#   sheet_roles_flat - accent-free, run together, lower case ("danhmuc", "khachhang")
#   sheet_roles_en   - English ("Products", "Customers")
#   sheet_roles_plain- control: default sheet names "Sheet1", "Sheet2" ... (what the sheet name is worth)
# The README follows: a "`danhmuc.csv`" section becomes "`QuanLy.xlsx`, sheet `DanhMuc`". Answers must stay.
SHEET_FAMILIES = ('sheet_roles', 'sheet_roles_vi', 'sheet_roles_flat', 'sheet_roles_en', 'sheet_roles_plain')
ROLE_SHEETS = {           # role -> (CamelCase, Vietnamese, run together, English)
    'product': ('DanhMuc', 'Danh mục hàng', 'danhmuc', 'Products'),
    'customer': ('KhachHang', 'Khách hàng', 'khachhang', 'Customers'),
    'purchase': ('NhapHang', 'Nhập hàng', 'nhaphang', 'Purchases'),
    'purchase_line': ('ChiTietNhap', 'Chi tiết nhập', 'chitietnhap', 'PurchaseLines'),
    'supplier': ('NhaCungCap', 'Nhà cung cấp', 'nhacungcap', 'Suppliers'),
    'unit_conversion': ('QuyDoi', 'Quy đổi đơn vị', 'quydoi', 'UnitConversion'),
    'stock_snapshot': ('TonKho', 'Tồn kho', 'tonkho', 'Inventory'),
    'staff': ('NhanVien', 'Nhân viên', 'nhanvien', 'Staff'),
    'price_history': ('BangGia', 'Bảng giá', 'banggia', 'PriceList'),
    'expense': ('ChiPhi', 'Chi phí', 'chiphi', 'Expenses'),
    'payment': ('SoQuy', 'Sổ quỹ', 'soquy', 'Payments'),
    'delivery': ('GiaoHang', 'Giao hàng', 'giaohang', 'Deliveries'),
    'sales_line': ('BanHang', 'Bán hàng', 'banhang', 'Sales'),        # only when kept in a one-table file
    'order': ('HoaDon', 'Hoá đơn', 'hoadon', 'Orders'),
}


def sheet_roles(folder: Path, tables, mapping, readme_text: str, family: str, work: Path):
    """Write the shop with its side tables as sheets of one workbook into `work`, read it back.
    Returns (tables, README, info) or (None, None, reason)."""
    import pandas as pd
    per_file = Counter(s.split(':', 1)[0] for t in tables.values() for s in {x.split(':', 1)[0] for x in t.sources})
    gather = {}
    for n, m in mapping.items():
        if m.entity not in ROLE_SHEETS or n not in tables:
            continue
        files = {s.split(':', 1)[0] for s in tables[n].sources}
        if len(files) != 1:
            continue
        f = next(iter(files))
        if Path(f).suffix.lower() in ('.sqlite', '.sqlite3', '.db', '.parquet') or per_file[f] != 1:
            continue
        gather[n] = f
    if len(gather) < 2:
        return None, None, f'chỉ {len(gather)} bảng phụ một-bảng-một-file'
    style = {'sheet_roles': 0, 'sheet_roles_vi': 1, 'sheet_roles_flat': 2, 'sheet_roles_en': 3}.get(family)
    book = 'QuanLy.xlsx' if not (folder / 'QuanLy.xlsx').exists() else 'DuLieu_QuanLy.xlsx'
    work.mkdir(parents=True, exist_ok=True)
    gone = set(gather.values())
    for p in folder.rglob('*'):
        if p.is_file() and not p.name.lower().startswith('readme') and p.name not in gone:
            shutil.copy2(p, work / p.name)
    sheets, text = {}, readme_text
    for i, (n, f) in enumerate(sorted(gather.items(), key=lambda kv: kv[0])):
        sheet = ROLE_SHEETS[mapping[n].entity][style] if style is not None else f'Sheet{i + 1}'
        sheets[sheet] = tables[n].frame[tables[n].headers]
        # README: the file's section heading names the workbook + sheet; other mentions name the sheet
        text = re.sub(rf'^(#+[^\n]*?)`{re.escape(f)}`', lambda m: f'{m.group(1)}`{book}`, sheet `{sheet}`', text,
                      flags=re.M)
        text = text.replace(f'`{f}`', f'sheet `{sheet}` của `{book}`').replace(f, f'{book} (sheet {sheet})')
    with pd.ExcelWriter(work / book, engine='openpyxl') as xw:
        for sheet, frame in sheets.items():
            frame.to_excel(xw, sheet_name=sheet[:31], index=False)
    (work / 'README.md').write_text(text, encoding='utf-8')
    return read_business(work), text, {'book': book, 'sheets': {s: n for s, n in zip(sheets, sorted(gather))}}


DATE_TOKEN = re.compile(r'(?:thang|th|t|m)?\d+')


def merge_month_tables(tables: dict) -> dict:
    """PROTOTYPE, moved into ingest.read_business (_join_month_groups) on 16/11 -> --merge-months is now a no-op kept for
    old commands. Tables with the same columns whose names differ only by
    date tokens ('sobanhang_t03', 'sobanhang_t04', '2025_03_banhang' -> 'sobanhang' / 'banhang') are one table.
    Only names made of '_'-separated tokens; a token is dropped when it is wholly a month/year mark."""
    import pandas as pd
    groups = {}
    for name, t in tables.items():
        core = '_'.join(tok for tok in name.split('_') if not DATE_TOKEN.fullmatch(tok)) or name
        groups.setdefault((core, tuple(plain(h) for h in t.headers)), []).append(name)
    out = {}
    for (core, _), names in groups.items():
        if len(names) == 1:
            out[names[0]] = tables[names[0]]
            continue
        ts = [tables[n] for n in names]
        name = core if (core in names or core not in tables) and core not in out else names[0]
        frames = [t.frame.rename(columns=dict(zip(t.headers, ts[0].headers))) for t in ts]
        out[name] = RawTable(name, pd.concat(frames, ignore_index=True), list(ts[0].headers),
                             [s for t in ts for s in t.sources])
    return out


def table_diff(before: dict, after: dict, mb, ma) -> list[str]:
    """Data-layer differences between the original shop and the variant: tables, rows, mapped entities."""
    ent_b = {n: m.entity for n, m in mb.items()}
    ent_a = {n: m.entity for n, m in ma.items()}
    out = []
    for n in sorted(set(before) | set(after)):
        b, a = before.get(n), after.get(n)
        if b is None or a is None or len(b.frame) != len(a.frame) or ent_b.get(n) != ent_a.get(n) \
                or [plain(h) for h in b.headers] != [plain(h) for h in a.headers]:
            out.append(f'{n}: {len(b.frame) if b is not None else "-"}→{len(a.frame) if a is not None else "-"} dòng, '
                       f'{ent_b.get(n)}→{ent_a.get(n)}')
    return out


def load_from(tables, readme_text, biz) -> Shop:
    started = time.time()
    readme = read_readme(None, text=readme_text)
    profiles = profile_business(tables, readme)
    log = []
    mapping, extra = resolve_mapping(tables, profiles, readme, None, log)
    views = build_views(tables, mapping, extra['typed'], readme, extra.get('product_attrs'))
    report = {'mapping': mapping_to_json(mapping), 'checks': extra['report'], 'notes': views.notes + log,
              'selfcheck': shop_check(tables, mapping, views, readme.get('text', ''))}   # as pipeline.load_shop
    return Shop(biz, views, mapping, shop_names(views), report, round(time.time() - started, 1))


def score(shop, qs, gold, cal, subs=None, metrics=None):
    res = {}
    for rec in qs:
        out = answer(shop, rec, scripted_intent, cal)
        if metrics is not None:
            metrics[rec['id']] = (out.get('intent') or {}).get('metric')
        sub = to_submission(out)
        if subs is not None:
            subs[rec['id']] = json.dumps(sub, sort_keys=True, ensure_ascii=False, default=str)
        g = gold.get(rec['id'])
        res[rec['id']] = 'abstain' if sub['type'] == 'abstain' else ('correct' if g and is_correct(sub, g) else 'wrong')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-root', required=True)
    ap.add_argument('--families', nargs='*', default=['accents', 'case', 'synonym', 'shuffle', 'tablename', 'noreadme'])
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default='')
    ap.add_argument('--merge-months', action='store_true',
                    help='prototype fix: merge same-column tables whose names differ only by month/year tokens')
    ap.add_argument('--work-dir', default='', help='keep the rewritten split_month shops here (default: temp, deleted)')
    ap.add_argument('--no-month-join', action='store_true',
                    help='control: read the variants WITHOUT ingest joining one-file-per-month tables (the shop '
                         'self-check, datamate.selfcheck, must then block the split shops)')
    ap.add_argument('biz', nargs='+')
    args = ap.parse_args()
    if args.no_month_join:
        import datamate.ingest as _ingest
        _ingest._join_month_groups = lambda groups: groups
    root = Path(args.train_root)
    hold = set(json.loads((ROOT / 'kaggle' / 'config.json').read_text(encoding='utf-8')).get('val_shops') or [])
    bad = [b for b in args.biz if b in hold]
    if bad:
        sys.exit(f'refusing held-out shops {bad} (kaggle/config.json val_shops)')
    questions = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    gold = {r['id']: r for r in map(json.loads, (root / 'answers.jsonl').read_text(encoding='utf-8').splitlines()) if r}
    cal = Calendar(root / 'calendar.csv')
    summary, broken = Counter(), []
    for biz in args.biz:
        folder = root / 'data' / biz
        tables = read_business(folder)
        if args.merge_months:
            tables = merge_month_tables(tables)
        rd = sorted(folder.glob('README*'))
        text = rd[0].read_text(encoding='utf-8-sig') if rd else ''
        qs = [q for q in questions if q['business_id'] == biz]
        base_shop = load_from(tables, text, biz)
        if base_shop.report['selfcheck']['block']:
            print(f'    [gốc] TỰ KIỂM CHẶN SHOP: {base_shop.report["selfcheck"]["block"]}', flush=True)
        base_subs = {}
        base_metric = {}
        base = score(base_shop, qs, gold, cal, base_subs, base_metric)
        ok = {i for i, v in base.items() if v == 'correct'}
        line = [f'{biz}: gốc đúng {len(ok)}/{len(qs)}']
        for fam in args.families:
            excluded = set()
            if fam in STATUS_WORDS:
                t2, text2, relabel = perturb_status(tables, text, base_shop.mapping, fam)
                cols = status_columns(base_shop.mapping)
                excluded = {q['id'] for q in qs if answer_is_status(gold.get(q['id']), relabel)}
                summary[(fam, 'excluded')] += len(excluded)
                summary[(fam, 'no_status_col')] += not cols
                print(f'    [{fam}] cột {cols}  đổi {relabel}' + (f'  loại {len(excluded)} câu' if excluded else ''),
                      flush=True)
                if not relabel:
                    line.append(f'{fam} (không có cột trạng thái)')
                    continue
            elif fam in STT_FAMILIES:
                t2, text2, info = stt_order(tables, base_shop.mapping, text, fam)
                if t2 is None:
                    line.append(f'{fam} (không áp dụng: {info})')
                    summary[(fam, 'not_split')] += 1
                    continue
                excluded = {q['id'] for q in qs if mentions_order_id(q, gold.get(q['id']), info['ids'])}
                summary[(fam, 'excluded')] += len(excluded)
                print(f'    [{fam}] {info["table"]}.{info["column"]} → STT' +
                      (f'  loại {len(excluded)} câu nêu mã đơn' if excluded else ''), flush=True)
            elif fam in ALIAS_FAMILIES:
                t2, text2, info = short_names(tables, base_shop.mapping, text)
                if t2 is None:
                    line.append(f'{fam} (không áp dụng: {info})')
                    summary[(fam, 'not_split')] += 1
                    continue
                print(f'    [{fam}] {info}', flush=True)
            elif fam in SHEET_FAMILIES:
                work = Path(tempfile.mkdtemp(prefix=f'{biz}_{fam}_', dir=args.work_dir or None))
                t2, text2, info = sheet_roles(folder, tables, base_shop.mapping, text, fam, work)
                if not args.work_dir:
                    shutil.rmtree(work, ignore_errors=True)
                if t2 is None:
                    line.append(f'{fam} (không áp dụng: {info})')
                    summary[(fam, 'not_split')] += 1
                    continue
                print(f'    [{fam}] {info["book"]}: {info["sheets"]}', flush=True)
            elif fam in WRITE_FAMILIES:
                src, writer = tables, fam
                if fam in ROW_FAMILIES:
                    src, rinfo = row_transform(tables, base_shop.mapping, fam, args.seed)
                    if src is None:
                        line.append(f'{fam} (không áp dụng: {rinfo})')
                        summary[(fam, 'not_split')] += 1
                        continue
                    print(f'    [{fam}] {rinfo}', flush=True)
                    writer = 'rewrite'
                work = Path(tempfile.mkdtemp(prefix=f'{biz}_{fam}_', dir=args.work_dir or None))
                try:
                    t2, text2, info = split_month(folder, src, base_shop.mapping, text, writer, work)
                except Exception as exc:              # a tool failure, not a system failure: report, do not count
                    print(f'    [{fam}] LỖI CÔNG CỤ {type(exc).__name__}: {exc}', flush=True)
                    line.append(f'{fam} (lỗi công cụ)')
                    summary[(fam, 'not_split')] += 1
                    continue
                if args.merge_months:
                    t2 = merge_month_tables(t2)
                if not info['split']:
                    line.append(f'{fam} (không tách được: {info["skipped"] or "không có bảng bán"})')
                    summary[(fam, 'not_split')] += 1
                    if not args.work_dir:
                        shutil.rmtree(work, ignore_errors=True)
                    continue
            else:
                t2, text2 = perturb(tables, text, fam, args.seed)
            subs = {}
            try:
                var_shop = load_from(t2, text2, biz)
                if var_shop.report['selfcheck']['block']:
                    summary[(fam, 'self_check')] += 1
                    print(f'    [{fam}] TỰ KIỂM CHẶN SHOP: {var_shop.report["selfcheck"]["block"]}', flush=True)
                res = score(var_shop, qs, gold, cal, subs)
                if fam in SHEET_FAMILIES:            # roles of the gathered tables (now sheets) in the variant
                    roles = {n: m.entity for n, m in var_shop.mapping.items()
                             if any(s.startswith(info['book'] + ':') for s in t2[n].sources)}
                    want = {base_shop.mapping[n].entity for n in info['sheets'].values()}
                    print(f'    [{fam}] vai các sheet: {roles}'
                          + ('' if want == set(roles.values()) else f'  ≠ gốc {sorted(want, key=str)}'), flush=True)
                if fam in WRITE_FAMILIES:
                    dif = table_diff(tables, t2, base_shop.mapping, var_shop.mapping)
                    print(f'    [{fam}] tách {info["split"]} → {info["files"]} file'
                          + (f'  bỏ qua {info["skipped"]}' if info['skipped'] else '')
                          + (f'\n      bảng khác gốc: {"; ".join(dif)}' if dif else '  (bảng/ánh xạ như gốc)'), flush=True)
            except Exception as exc:                  # a crash on a variant counts as all broken
                res = {i: f'crash {type(exc).__name__}' for i in base}
                print(f'    [{fam}] crash {type(exc).__name__}: {exc}', flush=True)
            finally:
                if fam in WRITE_FAMILIES and not args.work_dir:
                    shutil.rmtree(work, ignore_errors=True)
            ok_f = ok - excluded
            lost = [i for i in ok_f if res.get(i) != 'correct']
            gained = [i for i, v in res.items() if v == 'correct' and i not in ok and i not in excluded]
            diff = [i for i in base_subs if i not in excluded and subs.get(i) != base_subs[i]]
            summary[(fam, 'kept')] += len(ok_f) - len(lost)
            summary[(fam, 'lost')] += len(lost)
            summary[(fam, 'gained')] += len(gained)
            summary[(fam, 'diff')] += len(diff)
            qtext = {q['id']: q['question'] for q in qs}
            broken += [{'biz': biz, 'family': fam, 'id': i, 'kind': 'lost' if i in lost else 'gained' if i in gained
                        else 'diff', 'question': qtext.get(i), 'was': base.get(i), 'now': res.get(i),
                        'base_answer': base_subs.get(i), 'new_answer': subs.get(i)}
                       for i in sorted(set(lost) | set(gained) | set(diff))]
            if fam == 'non_item_fee':          # questions that do not depend on the fee / voucher rows
                safe = {i for i in ok_f if base_metric.get(i) in FEE_SAFE_METRICS}
                summary[(fam, 'safe')] += len(safe)
                summary[(fam, 'safe_lost')] += len(safe & set(lost))
            line.append(f'{fam} −{len(lost)}/+{len(gained)}/≠{len(diff)}')
        print('  '.join(line), flush=True)
    print('\n=== giữ được câu đúng theo họ biến đổi')
    for fam in args.families:
        k, l = summary[(fam, 'kept')], summary[(fam, 'lost')]
        extra = f'  loại {summary[(fam, "excluded")]} câu (đáp án là nhãn trạng thái), ' \
                f'{summary[(fam, "no_status_col")]} shop không có cột trạng thái' if fam in STATUS_WORDS else             (f'  {summary[(fam, "not_split")]} shop không tách được' if summary[(fam, 'not_split')] else '')
        if fam in STT_FAMILIES:
            extra = f'  {summary[(fam, "not_split")]} shop không áp dụng, loại {summary[(fam, "excluded")]} câu nêu mã đơn'
        if fam == 'non_item_fee':
            extra += f'  câu không phụ thuộc dòng phụ: giữ {summary[(fam, "safe")] - summary[(fam, "safe_lost")]}/'                      f'{summary[(fam, "safe")]}'
        if summary[(fam, 'self_check')]:
            extra += f'  tự kiểm chặn {summary[(fam, "self_check")]} shop'
        print(f'{fam:9s} giữ {k}/{k + l} ({100.0 * k / max(k + l, 1):.1f}%)  mất {l}  thêm {summary[(fam, "gained")]}'
              f'  đáp án khác {summary[(fam, "diff")]}{extra}')
    if args.out:
        Path(args.out).write_text(json.dumps(broken, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
