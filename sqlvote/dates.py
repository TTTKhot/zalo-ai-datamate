"""Calendar anchors computed in code, so the model never does date arithmetic itself.

The anchors are plain calendar facts (Monday of this week, first day of the month, lunar dates from
calendar.csv). Which window a phrase means is still decided by the rulebook of the split in the prompt.
"""
from __future__ import annotations

import calendar as _cal
import csv
import datetime as dt
from pathlib import Path

WEEKDAYS = ['thứ Hai', 'thứ Ba', 'thứ Tư', 'thứ Năm', 'thứ Sáu', 'thứ Bảy', 'Chủ nhật']


def load_calendar(path: str | Path) -> dict:
    """calendar.csv -> {'lunar': {(lunar_year, lunar_month, lunar_day): date}} (leap months skipped)."""
    lunar = {}
    path = Path(path)
    if not path.exists():
        return {'lunar': lunar}
    with path.open(encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            try:
                if str(row.get('lunar_leap', '')).strip().lower() in ('true', '1'):
                    continue
                key = (int(row['lunar_year']), int(row['lunar_month']), int(row['lunar_day']))
                lunar.setdefault(key, dt.date.fromisoformat(row['date'][:10]))
            except (KeyError, ValueError):
                continue
    return {'lunar': lunar}


def tet_window(cal: dict, year: int):
    """23 tháng Chạp (lunar year - 1) .. mùng 10 tháng Giêng (lunar year), as solar dates, or None."""
    start, new_year, end = (cal['lunar'].get((year - 1, 12, 23)), cal['lunar'].get((year, 1, 1)),
                            cal['lunar'].get((year, 1, 10)))
    return (start, new_year, end) if start and end else None


def _rng(a: dt.date, b: dt.date) -> str:
    return f'{a.isoformat()} → {b.isoformat()}'


def date_facts(as_of: str | dt.date, cal: dict) -> str:
    d = as_of if isinstance(as_of, dt.date) else dt.date.fromisoformat(str(as_of)[:10])
    one = dt.timedelta(days=1)
    monday = d - dt.timedelta(days=d.weekday())
    month_start = d.replace(day=1)
    prev_month_end = month_start - one
    prev_month_start = prev_month_end.replace(day=1)
    same_day = min(d.day, _cal.monthrange(prev_month_start.year, prev_month_start.month)[1])
    q = (d.month - 1) // 3
    q_start = dt.date(d.year, 3 * q + 1, 1)
    pq_end = q_start - one
    pq_start = dt.date(pq_end.year, 3 * ((pq_end.month - 1) // 3) + 1, 1)
    lines = [
        f'hôm nay = {d.isoformat()} ({WEEKDAYS[d.weekday()]}); hôm qua = {(d - one).isoformat()}',
        f'tuần chứa hôm nay bắt đầu thứ Hai {monday.isoformat()}; tuần liền trước: {_rng(monday - 7 * one, monday - one)}',
        f'tháng chứa hôm nay: {_rng(month_start, d)} (cả tháng đến {dt.date(d.year, d.month, _cal.monthrange(d.year, d.month)[1]).isoformat()}); '
        f'tháng trước: {_rng(prev_month_start, prev_month_end)}; cùng số ngày của tháng trước: '
        f'{_rng(prev_month_start, prev_month_start.replace(day=same_day))}',
        f'quý chứa hôm nay: Q{q + 1}/{d.year} từ {q_start.isoformat()}; quý liền trước: {_rng(pq_start, pq_end)}',
        f'đầu năm nay: {dt.date(d.year, 1, 1).isoformat()}; 7 ngày gần nhất kể cả hôm nay: {_rng(d - 6 * one, d)}; '
        f'30 ngày gần nhất kể cả hôm nay: {_rng(d - 29 * one, d)}',
    ]
    for year in (d.year - 1, d.year, d.year + 1):
        win = tet_window(cal, year)
        if not win:
            continue
        start, new_year, end = win
        n = (end - start).days + 1
        lines.append(f'Tết {year}: 23 tháng Chạp = {start.isoformat()}, mùng 1 = {new_year.isoformat() if new_year else "?"}, '
                     f'mùng 10 = {end.isoformat()} ({n} ngày); {n} ngày ngay trước 23 tháng Chạp: '
                     f'{_rng(start - n * one, start - one)}')
    return '\n'.join('- ' + line for line in lines)
