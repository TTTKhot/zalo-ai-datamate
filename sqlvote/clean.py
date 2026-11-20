"""Read one shop folder into typed, cleaned tables and store them in a DuckDB file.

Structure and value formats only - no business meaning is decided here:
  * header row detection (title rows, two-row headers), repeated headers and empty rows dropped;
  * sheets / files with the same header become one table (monthly sheets, _1/_2 splits);
  * values: '55.000đ', '25k', '2,825tr', '1,500.0000', '1 hộp' -> numbers (+ a unit column);
    '01/02/2025', Excel serials, ISO datetimes, year-less '1/4' (year from the sheet name) -> dates;
  * rulebook §8 structure rules: blank cells on the later rows of an order are filled from the first
    row (text / date columns only); identical rows of the same order are kept once.
Column names become ASCII slugs; the original header and the README description stay in the meta.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .text import nfc, plain, slug

CLEAN_VERSION = 3
TABLE_SUFFIXES = {'.csv', '.tsv', '.xlsx', '.xlsm', '.xls', '.sqlite', '.sqlite3', '.db'}
EXCEL_EPOCH = dt.datetime(1899, 12, 30)
SERIAL_MIN, SERIAL_MAX = 36526, 58000            # 2000-01-01 .. 2058
RESERVED = set('order group table select from where limit desc asc end case all column check default in is as '
               'on to user when then else and or not null true false having union join using primary unique '
               'references into values'.split())
MULT = {'k': 1e3, 'n': 1e3, 'ng': 1e3, 'nghin': 1e3, 'ngan': 1e3, 'tr': 1e6, 'trieu': 1e6, 'ty': 1e9, 'ti': 1e9}
CURRENCY = ('vnd', 'dong', 'd', '₫')
STATES = ('hoàn thành', 'huỷ', 'trả hàng', 'đang giao')

_NUM_RE = re.compile(r'^\(?\s*([+-]?)\s*(\d[\d.,]*)\s*(.*?)\s*\)?$')
_ISO = re.compile(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?(?:Z|[+-]\d{2}:?\d{2})?$')
_DMY = re.compile(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$')
_YMD = re.compile(r'^(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$')
_DM = re.compile(r'^(\d{1,2})/(\d{1,2})$')
_DTHG = re.compile(r'^(?:ngày\s*)?(\d{1,2})\s*(?:thg|tháng|thang|th)\.?\s*(\d{1,2})(?:\s*(?:năm|nam|,|/)?\s*(\d{4}))?$', re.I)
_DATE_HINT = re.compile(r'\b(ngay|date|han|thoi gian|thoi diem|luc|gio|time)\b')
_KEY_HINT = re.compile(r'\b(ma (don|hoa don|hd|bill|phieu|ct|gd|giao dich)|so (phieu|ct|hoa don|chung tu|hd)|'
                       r'order ?id|bill|invoice)\b|^ma ?(hoa ?don|don ?hang|don)$')
_FOOTER = re.compile(r'^(tong cong|tong so|tong|cong|total|ghi chu|note|nguoi lap|ke toan|thu quy)\b')
_STATUS_HINT = re.compile(r'\b(trang thai|tinh trang|status|state)\b')


def is_blank(v) -> bool:
    if v is None or v is pd.NaT or v is pd.NA:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, str) and not v.strip()


# ---------------------------------------------------------------- value parsers
def _body(body: str, decimal_only: bool):
    body = body.rstrip('.,')
    if not body:
        return None
    if '.' in body and ',' in body:
        dec = '.' if body.rfind('.') > body.rfind(',') else ','
        thou = ',' if dec == '.' else '.'
        body = body.replace(thou, '')
        if body.count(dec) != 1:
            return None
        return float(body.replace(dec, '.'))
    for sep in '.,':
        if sep in body:
            parts = body.split(sep)
            grouped = 1 <= len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:])
            if grouped and not decimal_only and not (len(parts) == 2 and parts[0] == '0'):
                return float(''.join(parts))
            if len(parts) == 2 and parts[1]:
                return float(parts[0] + '.' + parts[1])
            return None
    return float(body)


def parse_number(v, dot_decimal: bool = False):
    """-> (value, unit text or None) or None. Money marks and k/tr/tỷ are applied, a trailing unit is returned."""
    if isinstance(v, (bool, np.bool_)):
        return None
    if isinstance(v, (int, float, np.integer, np.floating)):
        f = float(v)
        return None if math.isnan(f) else (f, None)
    if not isinstance(v, str):
        return None
    s = nfc(v).strip().lower().replace(' ', ' ')
    m = _NUM_RE.match(s)
    if not m:
        return None
    sign, body, rest = m.groups()
    negative = sign == '-' or (s.startswith('(') and s.endswith(')'))
    rest_plain = plain(rest).replace(' ', '')
    for cur in CURRENCY:                              # '25kđ', '2tr vnd'
        if rest_plain.endswith(cur) and (rest_plain[:-len(cur)] in MULT or rest_plain == cur):
            rest_plain = rest_plain[:-len(cur)]
            break
    mult, unit, decimal_only = 1.0, None, False
    tail = re.fullmatch(r'(k|tr|trieu|ty)(\d+)', rest_plain)
    if rest_plain in ('', '%'):
        pass
    elif rest_plain in MULT:
        mult, decimal_only = MULT[rest_plain], True
    elif tail and body.isdigit():                     # '1tr2' = 1.2 triệu
        mult, body, decimal_only = MULT[tail.group(1)], body + '.' + tail.group(2), True
    elif re.fullmatch(r'[^\W\d].{0,11}', rest):       # '1 hộp', '2 m3', '1 xe 4m3'
        unit = rest.strip()
    else:
        return None
    value = _body(body, decimal_only or (dot_decimal and ',' not in body))
    if value is None:
        return None
    value = round(value * mult, 6)
    return (-value if negative else value, unit)


def parse_date(v, year: int | None = None):
    if v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    if not isinstance(v, str):
        return None
    s = v.strip()
    try:
        m = _ISO.match(s) or _YMD.match(s)
        if m:
            y, mo, d, h, mi, se = m.groups()
            return dt.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(se or 0))
        m = _DMY.match(s)
        if m:
            d, mo, y, h, mi, se = m.groups()
            y = int(y) + 2000 if len(y) == 2 else int(y)
            return dt.datetime(y, int(mo), int(d), int(h or 0), int(mi or 0), int(se or 0))
        m = _DTHG.match(s)                              # '10 thg 6 2025', 'ngày 10 tháng 6 năm 2025'
        if m and (m.group(3) or year):
            return dt.datetime(int(m.group(3) or year), int(m.group(2)), int(m.group(1)))
        m = _DM.match(s)
        if m and year:
            return dt.datetime(int(year), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return None


def from_serial(x: float) -> dt.datetime:
    return EXCEL_EPOCH + dt.timedelta(seconds=round(float(x) * 86400))


def year_from_label(label) -> int | None:
    m = re.search(r'(?<!\d)(20\d{2})(?!\d)', str(label or ''))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- column typing
def type_column(col: pd.Series, name: str, desc: str = '', years=None):
    """-> (values list, kind TEXT/BIGINT/DOUBLE/DATE/TIMESTAMP, unit list or None)."""
    vals = col.tolist()
    n_rows = len(vals)
    strings = {v for v in vals if isinstance(v, str)}
    dot_decimal = any(re.fullmatch(r'\s*[+-]?\d+\.(\d{1,2}|\d{4,})\s*\D*', s) for s in strings) and \
        not any(re.fullmatch(r'\s*[+-]?\d{1,3}(\.\d{3}){2,}\s*\D*', s) for s in strings)
    cache: dict = {}

    def classify(v):
        if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
            return 'dt', parse_date(v)
        if isinstance(v, (bool, np.bool_)):
            return 'text', str(v)
        if isinstance(v, (int, float, np.integer, np.floating)):
            return 'num', float(v)
        s = re.sub(r'\s+', ' ', nfc(v)).strip()
        d = parse_date(s)
        if d is not None:
            return 'dt', d
        if _DM.match(s) or _DTHG.match(s):
            return 'dm', s
        num = parse_number(s, dot_decimal)
        if num is not None:
            return 'nstr', (num[0], num[1], s)
        return 'text', s

    kinds, parsed = [None] * n_rows, [None] * n_rows
    count = {'dt': 0, 'dm': 0, 'num': 0, 'nstr': 0, 'text': 0}
    serial = code_like = with_unit = 0
    for i, v in enumerate(vals):
        if is_blank(v):
            continue
        key = (type(v).__name__, v)
        hit = cache.get(key)
        if hit is None:
            hit = cache[key] = classify(v)
        kinds[i], parsed[i] = hit
        count[hit[0]] += 1
        if hit[0] == 'num':
            serial += SERIAL_MIN <= hit[1] <= SERIAL_MAX
        elif hit[0] == 'nstr':
            value, unit, raw = hit[1]
            with_unit += unit is not None
            if unit is None and raw.isdigit():
                serial += SERIAL_MIN <= value <= SERIAL_MAX
                code_like += (raw[0] == '0' and len(raw) > 1) or len(raw) >= 10
    n = sum(count.values())
    if n == 0:
        return [None] * n_rows, 'TEXT', None
    hint = bool(_DATE_HINT.search(plain(f'{name} {desc}')))
    dated = count['dt'] + count['dm']
    if dated + serial >= 0.97 * n and (dated >= 0.5 * n or (hint and serial > 0)):
        out, has_time = [], False
        for i in range(n_rows):
            k, p = kinds[i], parsed[i]
            d = None
            if k == 'dt':
                d = p
            elif k == 'dm':
                d = parse_date(p, None if years is None else years[i])
            elif k == 'num' and SERIAL_MIN <= p <= SERIAL_MAX:
                d = from_serial(p)
            elif k == 'nstr' and p[1] is None and SERIAL_MIN <= p[0] <= SERIAL_MAX:
                d = from_serial(p[0])
            if d is not None and (d.hour or d.minute or d.second):
                has_time = True
            out.append(d)
        return out, 'TIMESTAMP' if has_time else 'DATE', None
    numeric = count['num'] + count['nstr']
    if numeric >= 0.97 * n and code_like < 0.5 * max(count['nstr'], 1):
        out, units = [], []
        for i in range(n_rows):
            k, p = kinds[i], parsed[i]
            if k == 'num':
                out.append(p); units.append(None)
            elif k == 'nstr':
                out.append(p[0]); units.append(p[1])
            else:
                out.append(None); units.append(None)
        integral = all(v is None or float(v).is_integer() for v in out)
        return out, 'BIGINT' if integral else 'DOUBLE', units if with_unit else None
    out = []
    for i in range(n_rows):
        k, p = kinds[i], parsed[i]
        if k is None:
            out.append(None)
        elif k == 'num':
            out.append(str(int(p)) if float(p).is_integer() else repr(p))
        elif k == 'dt':
            out.append(p.isoformat(sep=' ') if p else None)
        elif k == 'nstr':
            out.append(p[2])
        else:
            out.append(p)
    return out, 'TEXT', None


# ---------------------------------------------------------------- file readers
def detect_header_row(raw: pd.DataFrame, scan_rows: int = 30) -> int:
    """First well-filled, text-like, mostly-unique row (title / filter / group-label rows are skipped)."""
    head = raw.head(scan_rows)
    widths = [sum(not is_blank(v) for v in row) for row in head.itertuples(index=False)]
    max_width = max(widths + [1])
    best, best_score = 0, -1.0
    for index, row in enumerate(head.itertuples(index=False)):
        cells = [v for v in row if not is_blank(v)]
        if len(cells) < max(2, 0.6 * max_width):
            continue
        text = [c for c in cells if isinstance(c, str) and not re.fullmatch(r'[\d\s.,:/\-]+', c.strip())]
        unique = len({str(c).strip() for c in cells}) / len(cells)
        score = len(cells) / max_width + len(text) / len(cells) + unique
        if score > best_score + 1e-9:
            best, best_score = index, score
            if len(text) == len(cells) and unique == 1.0 and len(cells) == max_width:
                break
    return best


def _frame_from_raw(raw: pd.DataFrame, header_row: int | None = None):
    raw = raw.dropna(axis=1, how='all').reset_index(drop=True)
    if raw.empty:
        return [], raw
    row = detect_header_row(raw) if header_row is None else header_row
    headers, used = [], {}
    for i, value in enumerate(raw.iloc[row].tolist()):
        name = f'cot_{i + 1}' if is_blank(value) else re.sub(r'\s+', ' ', nfc(value)).strip()
        used[name] = used.get(name, 0) + 1
        headers.append(name if used[name] == 1 else f'{name}_{used[name]}')
    body = raw.iloc[row + 1:].copy()
    body.columns = headers
    blank = body.map(is_blank) if hasattr(body, 'map') else body.applymap(is_blank)
    filled = (~blank).sum(axis=1)
    keep = filled > 0
    if len(headers) >= 5 and len(body):
        # footer rows of report exports: 'Cộng', 'Tổng cộng', 'Ghi chú: ...' with one or two cells filled
        for idx in body.index[(filled > 0) & (filled <= 3)]:
            first = next((plain(v) for v in body.loc[idx] if isinstance(v, str) and v.strip()), '')
            if _FOOTER.match(first):
                keep[idx] = False
        for idx in reversed(body.index):              # trailing near-empty rows under the data
            if not keep[idx] or filled[idx] <= 2:
                keep[idx] = False
            else:
                break
    body = body[keep]
    plain_headers = [plain(h) for h in headers]
    repeated = body.apply(lambda r: all(is_blank(v) or plain(v) == h for v, h in zip(r, plain_headers))
                          and sum(not is_blank(v) for v in r) >= 2, axis=1) if len(body) else pd.Series([], dtype=bool)
    return headers, body[~repeated.astype(bool)].reset_index(drop=True)


def _read_csv(path: Path):
    data = path.read_bytes()
    for encoding in ('utf-8-sig', 'utf-8', 'cp1258', 'utf-16'):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f'cannot decode {path.name}')
    try:
        delimiter = csv.Sniffer().sniff(text[:20000], delimiters=',;\t|').delimiter
    except csv.Error:
        delimiter = '\t' if path.suffix.lower() == '.tsv' else ','
    raw = pd.read_csv(io.StringIO(text), sep=delimiter, header=None, dtype=object, keep_default_na=False,
                      na_values=[''], engine='python' if len(text) < 2_000_000 else 'c')
    return [('', raw, None)]


def _read_excel(path: Path):
    try:
        import python_calamine  # noqa: F401
        engine = 'calamine'
    except ImportError:
        engine = None
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, engine=engine)
    return [(str(name), raw, None) for name, raw in sheets.items()]


def _read_sqlite(path: Path):
    out = []
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")]
        for name in names:
            frame = pd.read_sql_query(f'SELECT * FROM "{name}"', con)
            raw = pd.concat([pd.DataFrame([frame.columns.tolist()]),
                             frame.astype(object).set_axis(range(frame.shape[1]), axis=1)], ignore_index=True)
            out.append((name, raw, 0))
    finally:
        con.close()
    return out


def fix_name(name: str) -> str:
    """Undo zip mojibake (UTF-8 names decoded as cp437) so file names match the README again."""
    try:
        fixed = name.encode('cp437').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return nfc(name)
    return nfc(fixed)


def _base_name(path: Path) -> str:
    stem = Path(fix_name(path.name)).stem
    stem = re.sub(r'(?:[_\-\s](?:\d{1,2}|20\d{2}))+$', '', stem) or stem     # _1, _2, _2026
    return slug(stem) or slug(path.stem)


def read_readme(folder: Path) -> dict:
    """README text + '- **Col**: desc' lines grouped by the file named in the heading above them."""
    paths = sorted(folder.glob('README*')) + sorted(folder.glob('readme*'))
    if not paths:
        return {'text': '', 'columns': {}}
    text = paths[0].read_text(encoding='utf-8-sig', errors='replace')
    columns, current = {}, ''
    for line in text.splitlines():
        heading = re.match(r'^#+\s*(.*)$', line)
        if heading:
            named = re.search(r'`([^`]+)`', heading.group(1))
            current = plain(named.group(1)) if named else ''
            continue
        bullet = re.match(r'^\s*[-*]\s*\*\*(.+?)\*\*\s*[:：]\s*(.+)$', line)
        if bullet and current:
            columns.setdefault(current, {}).setdefault(plain(bullet.group(1)), bullet.group(2).strip())
    return {'text': text, 'columns': columns}


def _describe(readme: dict, sources: list[str], header: str) -> str:
    key = plain(header)
    files = {plain(s.split(':')[0]) for s in sources}
    sheets = {plain(s.split(':', 1)[1]) for s in sources if ':' in s}
    hits = [m[key] for name, m in readme['columns'].items() if key in m and (name in files or name in sheets)]
    if not hits:
        hits = list({m[key] for m in readme['columns'].values() if key in m})
        if len(hits) != 1:
            return ''
    return hits[0]


# ---------------------------------------------------------------- shop -> tables
def _status_state(value: str) -> str:
    p = plain(value)
    if re.search(r'huy|cancel', p):
        return 'huỷ'
    if re.search(r'tra hang|hang tra|doi tra|hoan tra|tra lai|tra ve|hoan hang|khach tra|return|refund', p) \
            or p in ('tra', 'hoan'):
        return 'trả hàng'
    if re.search(r'dang giao|cho giao|chua giao|van chuyen|ship|deliver|dang di', p):
        return 'đang giao'
    return 'hoàn thành'


def _fill_and_dedup(frame: pd.DataFrame, cols: list[dict]):
    """Rulebook §8 structure rules on a line table that has an order-key column. Returns (frame, notes)."""
    notes = []
    key = next((c for c in cols if c['type'] == 'TEXT' and
                (_KEY_HINT.search(plain(c['orig'])) or re.search(r'\bma (don|phieu|hoa don)\b', plain(c['desc'])))), None)
    if key is None or len(frame) < 2:
        return frame, notes
    k = frame[key['name']]
    if k.isna().any() and not pd.isna(k.iloc[0]) and k.isna().mean() < 0.95:
        frame[key['name']] = k = k.ffill()
        notes.append(f'{key["name"]}: ô trống đã điền theo dòng đầu của đơn')
    data_cols = [c['name'] for c in cols]
    dup = frame.duplicated(subset=data_cols, keep='first')
    if dup.any() and frame[key['name']].nunique() < len(frame):
        n = int(dup.sum())
        frame = frame[~dup].reset_index(drop=True)
        k = frame[key['name']]
        notes.append(f'đã bỏ {n} dòng trùng hoàn toàn trong cùng một đơn (rulebook: lỗi xuất file)')
    first = ~k.eq(k.shift())
    rest_n = int((~first).sum())
    if rest_n == 0:
        return frame, notes
    run = first.cumsum()
    for c in cols:
        if c['name'] == key['name'] or c['type'] not in ('TEXT', 'DATE', 'TIMESTAMP'):
            continue
        s = frame[c['name']]
        na = s.isna()
        if not na.any():
            continue
        filled_rest = int((~na & ~first).sum())
        if filled_rest <= 0.02 * rest_n and int((na & first).sum()) <= 0.5 * int(first.sum()):
            frame[c['name']] = s.where(~na, s.groupby(run).transform('first'))
            notes.append(f'{c["name"]}: ô trống ở các dòng sau của đơn đã điền theo dòng đầu')
    return frame, notes


def read_shop(folder: str | Path, max_rows: int = 600_000) -> dict:
    """-> {'tables': [{name, frame, columns, sources, notes}], 'readme': str}."""
    folder = Path(folder)
    readme = read_readme(folder)
    groups: dict = {}
    for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in TABLE_SUFFIXES):
        suffix = path.suffix.lower()
        reader = _read_csv if suffix in ('.csv', '.tsv') else _read_excel if suffix.startswith('.xl') else _read_sqlite
        is_db = reader is _read_sqlite
        for part, raw, header_row in reader(path):
            headers, body = _frame_from_raw(raw, header_row)
            if not headers or body.empty:
                continue
            body['_sheet'] = part
            base = slug(part) if is_db else _base_name(path)
            key = (base, tuple(plain(h) for h in headers))
            shown = fix_name(path.name)
            source = f'{shown}:{part}' if part and not is_db else shown
            if key in groups:
                groups[key]['parts'].append(body)
                groups[key]['sources'].append(source)
            else:
                groups[key] = {'base': base, 'headers': headers, 'parts': [body], 'sources': [source],
                               'sheet': part, 'is_db': is_db}
    per_base: dict = {}
    for g in groups.values():
        per_base.setdefault(g['base'], []).append(g)
    tables, used = [], set()
    for base, items in per_base.items():
        for i, g in enumerate(items):
            name = base
            if len(items) > 1:
                sheet = slug(g['sheet'])
                name = sheet if sheet and not re.fullmatch(r'sheet_?\d*', sheet) else f'{base}_{i + 1}'
            while name in used or not name:
                name = (name or 'bang') + '_2'
            used.add(name)
            raw = pd.concat(g['parts'], ignore_index=True) if len(g['parts']) > 1 else g['parts'][0]
            raw = raw.head(max_rows)
            years = [year_from_label(s) for s in raw['_sheet']]
            data, cols, seen = {}, [], set()
            for header in g['headers']:
                desc = _describe(readme, g['sources'], header)
                values, kind, units = type_column(raw[header], header, desc, years)
                col = slug(header) or 'cot'
                if col in RESERVED:
                    col += '_col'
                while col in seen:
                    col += '_2'
                seen.add(col)
                data[col] = values
                cols.append({'name': col, 'orig': header, 'type': kind, 'desc': desc})
                if units is not None:
                    data[col + '_dv'] = units
                    seen.add(col + '_dv')
                    cols.append({'name': col + '_dv', 'orig': header, 'type': 'TEXT',
                                 'desc': f'đơn vị ghi kèm trong ô "{header}" (trống nếu ô chỉ có số)'})
            frame = pd.DataFrame(data)
            if len(g['parts']) > 1 and not g['is_db']:
                frame['nguon_sheet'] = raw['_sheet'].tolist()
                cols.append({'name': 'nguon_sheet', 'orig': '', 'type': 'TEXT', 'desc': 'tên sheet / phần nguồn của dòng'})
            frame, notes = _fill_and_dedup(frame, cols)
            for c in list(cols):                       # 4-state helper next to an order status column
                if c['type'] != 'TEXT' or not _STATUS_HINT.search(plain(f"{c['orig']} {c['desc']}")):
                    continue
                distinct = frame[c['name']].dropna().unique().tolist()
                mapping = {v: _status_state(v) for v in distinct}
                if 0 < len(distinct) <= 60 and (len(set(mapping.values())) > 1 or 'don' in plain(c['desc'])):
                    frame[c['name'] + '_4tt'] = frame[c['name']].map(mapping)
                    cols.append({'name': c['name'] + '_4tt', 'orig': c['orig'], 'type': 'TEXT', 'status_map': mapping,
                                 'desc': f'trạng thái quy về 4 loại của rulebook, suy từ "{c["orig"]}" bằng từ điển chung '
                                         f'(kiểm tra lại với README)'})
            tables.append({'name': name, 'frame': frame, 'columns': cols, 'sources': g['sources'], 'notes': notes})
    return {'tables': tables, 'readme': readme['text']}


# ---------------------------------------------------------------- profile + duckdb
def _profile(frame: pd.DataFrame, col: dict, max_listed: int = 30, max_values: int = 5000) -> dict:
    s = frame[col['name']]
    nn = s.dropna()
    info = {'nulls': int(s.isna().sum())}
    if nn.empty:
        return info
    if col['type'] == 'TEXT':
        counts = nn.value_counts()
        info['distinct'] = int(len(counts))
        if len(counts) <= max_listed:
            info['listed'] = [[str(v), int(c)] for v, c in counts.items()]
        else:
            info['examples'] = [str(v) for v in counts.index[:4]]
        if len(counts) <= max_values:
            info['values'] = [str(v) for v in counts.index]
    elif col['type'] in ('DATE', 'TIMESTAMP'):
        width = 10 if col['type'] == 'DATE' else 19
        info['min'], info['max'] = str(min(nn))[:width], str(max(nn))[:width]
    else:
        info['min'], info['max'] = float(nn.min()), float(nn.max())
    return info


def _data_range(tables: list[dict], readme: str):
    end = None
    m = re.search(r'du lieu co den het (?:ngay )?(\d{1,2})/(\d{1,2})/(\d{4})', plain(readme))
    if m:
        end = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    best = None
    for t in tables:
        for c in t['columns']:
            if c['type'] not in ('DATE', 'TIMESTAMP') or re.search(r'\b(han|sinh|dang ky|khai truong|nhan viec)\b',
                                                                   plain(f"{c['orig']} {c['desc']}")):
                continue
            nn = t['frame'][c['name']].dropna()
            if len(nn) and (best is None or len(nn) > best[0]):
                best = (len(nn), min(nn).date(), max(nn).date(), f"{t['name']}.{c['name']}")
    if best is None:
        return None, end, None
    return best[1], end or best[2], best[3]


def build_shop_db(folder: str | Path, db_path: str | Path, extra_tables: list[dict] | None = None) -> dict:
    """Clean one shop, write <db_path> (DuckDB) and <db_path>.json (meta). Returns the meta.

    extra_tables: [{'name', 'frame', 'columns': [{'name','type','desc'}], 'notes': [...]}] - e.g. canonical views of
    another pipeline, loaded next to the cleaned raw tables."""
    import duckdb
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shop = read_shop(folder)
    start, end, main_col = _data_range(shop['tables'], shop['readme'])
    for extra in extra_tables or []:
        extra = dict(extra)
        extra.setdefault('sources', ['(bảng chuẩn hoá)'])
        extra.setdefault('notes', [])
        extra['columns'] = [dict({'orig': '', 'desc': ''}, **c) for c in extra['columns']]
        shop['tables'].append(extra)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    meta_tables = []
    try:
        for t in shop['tables']:
            frame = t['frame']
            selects = []
            for c in t['columns']:
                kind = c['type']
                if kind in ('DATE', 'TIMESTAMP'):
                    frame[c['name']] = pd.to_datetime(pd.Series(frame[c['name']].tolist(), dtype='object'), errors='coerce')
                elif kind == 'BIGINT':
                    frame[c['name']] = pd.array(frame[c['name']].tolist(), dtype='Int64')
                elif kind == 'DOUBLE':
                    frame[c['name']] = pd.array(frame[c['name']].tolist(), dtype='Float64')
                else:
                    frame[c['name']] = pd.Series(frame[c['name']].tolist(), dtype='object').where(
                        lambda s: s.notna(), None)
                selects.append(f'CAST("{c["name"]}" AS {kind if kind != "TEXT" else "VARCHAR"}) AS "{c["name"]}"')
                c['profile'] = _profile(frame, c)
            con.register('_src', frame)
            con.execute(f'CREATE TABLE "{t["name"]}" AS SELECT {", ".join(selects)} FROM _src')
            con.unregister('_src')
            meta_tables.append({'name': t['name'], 'rows': int(len(frame)), 'sources': t['sources'],
                                'notes': t['notes'], 'columns': t['columns']})
    finally:
        con.close()
    meta = {'version': CLEAN_VERSION, 'folder': str(folder), 'readme': shop['readme'], 'tables': meta_tables,
            'has_extra': bool(extra_tables),
            'data_start': str(start) if start else None, 'data_end': str(end) if end else None,
            'date_column': main_col}
    Path(str(db_path) + '.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    return meta


def load_or_build(folder: str | Path, db_path: str | Path, extra_tables=None, rebuild: bool = False) -> dict:
    meta_path = Path(str(db_path) + '.json')
    if not rebuild and meta_path.exists() and Path(db_path).exists():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            if meta.get('version') == CLEAN_VERSION and bool(meta.get('has_extra')) == bool(extra_tables):
                return meta
        except Exception:
            pass
    return build_shop_db(folder, db_path, extra_tables)
