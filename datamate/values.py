"""Value parsing for the formats Vietnamese shop exports use.

Every parser takes a pandas Series of raw objects (strings, numbers, datetimes)
and returns a parsed Series plus nothing else; parse rate is measured by the caller.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

EXCEL_EPOCH = pd.Timestamp('1899-12-30')
_CURRENCY = re.compile(r'(?i)\s*(?:vnđ|vnd|đồng|dong|đ|₫|d)\s*$')
_LEADING_CURRENCY = re.compile(r'(?i)^\s*(?:vnđ|vnd|₫)\s*')


def plain(text) -> str:
    """Lower-case, accent-free, single-spaced text (đ -> d)."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ''
    value = unicodedata.normalize('NFKD', str(text).casefold().replace('đ', 'd'))
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', value).strip()


def slug(text) -> str:
    return re.sub(r'[^a-z0-9]+', '_', plain(text)).strip('_')


def is_blank(value) -> bool:
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


# ---------------------------------------------------------------- numbers
def _number_token(text: str, prefer_thousands: bool) -> float | None:
    token = text.replace(' ', '').replace(' ', '')
    negative = token.startswith('(') and token.endswith(')')
    token = token.strip('()')
    if token.startswith('-'):
        negative, token = True, token[1:]
    token = token.lstrip('+')
    if not token or not re.fullmatch(r'[\d.,]+', token) or not re.search(r'\d', token):
        return None
    if '.' in token and ',' in token:
        decimal = '.' if token.rfind('.') > token.rfind(',') else ','
        group = ',' if decimal == '.' else '.'
        token = token.replace(group, '').replace(decimal, '.')
    else:
        sep = '.' if '.' in token else ',' if ',' in token else None
        if sep:
            parts = token.split(sep)
            grouped = all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3
            if grouped and (len(parts) > 2 or prefer_thousands):
                token = token.replace(sep, '')
            elif len(parts) == 2:
                token = parts[0] + '.' + parts[1]
            else:
                return None
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


# Vietnamese shorthand amounts: 25k, 1,39tr, 1tr440 (= 1.440.000), 2 triệu, 1.2 tỷ.
_MULT = {'k': 1e3, 'nghin': 1e3, 'ngan': 1e3, 'tr': 1e6, 'trieu': 1e6, 'cu': 1e6, 'ty': 1e9}
_SCALED = re.compile(r'([-+]?)\s*(\d[\d.,]*)\s*(k|nghin|ngan|tr|trieu|cu|ty)\.?')
_TR_TAIL = re.compile(r'([-+]?)\s*(\d+)\s*(tr|trieu|cu)\s*(\d{1,3})')


def _scaled_amount(text: str) -> float | None:
    """Number written with a magnitude word (k / tr / triệu / tỷ); None if the text is not one."""
    key = plain(text)
    m = _TR_TAIL.fullmatch(key)
    if m:                                        # 1tr440 -> 1.440.000 ; 3tr04 -> 3.040.000
        sign, whole, _, tail = m.groups()
        value = int(whole) * 1e6 + int(tail.ljust(3, '0')) * 1e3
        return -value if sign == '-' else value
    m = _SCALED.fullmatch(key)
    if not m:
        return None
    sign, digits, word = m.groups()
    number = _number_token(digits, prefer_thousands=False)   # '1,39tr' -> 1.39 x 10^6
    if number is None:
        return None
    value = round(number * _MULT[word], 6)
    return -value if sign == '-' else value


def parse_number_value(value, prefer_thousands=True):
    """Return (number, trailing unit text) or (None, None)."""
    if is_blank(value):
        return None, None
    if isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float, np.integer, np.floating)):
        value = float(value)
        return (value, None) if math.isfinite(value) else (None, None)
    text = _LEADING_CURRENCY.sub('', str(value).strip())
    text = _CURRENCY.sub('', text)
    scaled = _scaled_amount(text)
    if scaled is not None:
        return scaled, None
    match = re.fullmatch(r'([-+(]?\s*\d[\d.,]*(?:\s\d{3})*\)?)\s*([^\W\d_].{0,24})?', text)
    if not match:
        return None, None
    number = _number_token(match.group(1), prefer_thousands)
    unit = (match.group(2) or '').strip() or None
    return number, unit


def parse_numbers(series: pd.Series, prefer_thousands=True):
    pairs = [parse_number_value(v, prefer_thousands) for v in series.tolist()]
    numbers = pd.Series([p[0] for p in pairs], index=series.index, dtype='float64')
    units = pd.Series([p[1] for p in pairs], index=series.index, dtype='object')
    return numbers, units


# ---------------------------------------------------------------- dates
_VI_MONTH = re.compile(r'^(\d{1,2})\s*(?:thg|tháng|th)\s*(\d{1,2})[,\s]+(\d{4})', re.I)
_DMY = re.compile(r'^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?')
_YMD = re.compile(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?')
_DM = re.compile(r'^(\d{1,2})[/.\-](\d{1,2})$')


def parse_datetime_value(value, sheet_year=None, allow_serial=True):
    if is_blank(value):
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        if allow_serial and 20000 <= float(value) <= 80000:   # Excel serial date
            return (EXCEL_EPOCH + timedelta(days=float(value))).to_pydatetime()
        return None
    text = str(value).strip()
    if allow_serial and re.fullmatch(r'\d{5}(?:\.\d+)?', text) and 20000 <= float(text) <= 80000:
        return (EXCEL_EPOCH + timedelta(days=float(text))).to_pydatetime()
    try:
        m = _YMD.match(text)
        if m:
            y, mo, d, hh, mm, ss = m.groups()
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
        m = _DMY.match(text)
        if m:
            d, mo, y, hh, mm, ss = m.groups()
            y = int(y) + (2000 if len(y) == 2 else 0)
            return datetime(y, int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
        m = _VI_MONTH.match(text)
        if m:
            d, mo, y = m.groups()
            return datetime(int(y), int(mo), int(d))
        m = _DM.match(text)
        if m and sheet_year:
            d, mo = m.groups()
            return datetime(int(sheet_year), int(mo), int(d))
    except ValueError:
        return None
    return None


def split_camel(text) -> str:
    """'MaHoaDon' -> 'Ma Hoa Don', 'SLQuyDoi' -> 'SL Quy Doi', 'IDCuaHang' -> 'ID Cua Hang' (column names only)."""
    t = str(text or '')
    out = []
    for i, ch in enumerate(t):
        prev = t[i - 1] if i else ''
        nxt = t[i + 1] if i + 1 < len(t) else ''
        if i and ch.isupper() and (prev.islower() or prev.isdigit() or (prev.isupper() and nxt.islower())):
            out.append(' ')
        out.append(ch)
    return ''.join(out)


def date_cue(*texts) -> bool:
    """Header / README text that names a date ('ngày bán', 'ngay_ban', 'Order date')."""
    toks = set(re.findall(r'[a-z0-9]+', ' '.join(plain(split_camel(t)) for t in texts if t)))
    return bool(toks & {'ngay', 'date', 'day'})


def parse_datetimes(series: pd.Series, sheet_years: pd.Series | None = None,
                    allow_serial: bool | None = None) -> pd.Series:
    """Excel serial numbers count as dates only when the column also holds real dates."""
    years = sheet_years.tolist() if sheet_years is not None else [None] * len(series)
    if allow_serial is None:
        sample = series.dropna().head(2000).tolist()
        real = sum(parse_datetime_value(v, None, allow_serial=False) is not None for v in sample)
        allow_serial = bool(sample) and real / len(sample) >= 0.2
    raw = series.tolist()
    values = [parse_datetime_value(v, y, allow_serial) for v, y in zip(raw, years)]
    # 'd/m' without a year in a book whose other rows carry full dates: take the year of the
    # previous dated row (books run in time order), rolling over when the month wraps Dec -> Jan.
    prev = None
    pending = []                     # leading d/m rows before the first full date
    for i, (v, parsed) in enumerate(zip(raw, values)):
        if parsed is not None:
            prev = parsed
            continue
        m = _DM.match(str(v).strip()) if isinstance(v, str) else None
        if not m:
            continue
        d, mo = int(m.group(1)), int(m.group(2))
        if prev is None:
            pending.append((i, d, mo))
            continue
        year = prev.year + (1 if mo < prev.month - 6 else 0)
        try:
            values[i] = prev = datetime(year, mo, d)
        except ValueError:
            pass
    if pending:
        first = next((p for p in values if p is not None), None)
        for i, d, mo in pending if first is not None else []:
            try:
                values[i] = datetime(first.year - (1 if mo > first.month + 6 else 0), mo, d)
            except ValueError:
                pass
    return pd.to_datetime(pd.Series(values, index=series.index, dtype='object'), errors='coerce')


def has_time_component(parsed: pd.Series) -> bool:
    valid = parsed.dropna()
    if valid.empty:
        return False
    return bool(((valid.dt.hour != 0) | (valid.dt.minute != 0)).mean() > 0.5)


def year_from_label(label) -> int | None:
    match = re.search(r'(20\d{2})', str(label or ''))
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------- text
def clean_text(series: pd.Series) -> pd.Series:
    return series.map(lambda v: None if is_blank(v) else re.sub(r'\s+', ' ', str(v)).strip())


def name_key(text) -> str:
    """Key under which spelling variants of one name collide (accents/space/case)."""
    return re.sub(r'[^a-z0-9]', '', plain(text))
