"""Rulebook §2 period resolution from a structured spec (LLM output), never from raw text.

spec examples
  {"type": "day", "date": "2025-06-14"}             {"type": "month", "month": 3, "year": 2025}
  {"type": "month", "month": 3}                      (no year: this year unless after today)
  {"type": "quarter", "quarter": 4, "year": 2025}    {"type": "year", "year": 2025}
  {"type": "range", "start": "...", "end": "..."}    (both inclusive)
  {"type": "today"} {"type": "yesterday"} {"type": "this_week"} {"type": "last_week"}
  {"type": "this_month"} {"type": "last_month"} {"type": "year_to_date"}
  {"type": "last_n_days", "n": 7}                    {"type": "tet", "year": 2026}
  {"type": "as_of", "date": "..."}                   (state at end of that day: stock, debt)
A resolved period is (start, end_exclusive, label).
"""
from __future__ import annotations

import csv
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Period:
    start: date
    end: date            # exclusive
    label: str
    kind: str = ''

    @property
    def days(self):
        return (self.end - self.start).days

    def to_json(self):
        return {'start': self.start.isoformat(), 'end_exclusive': self.end.isoformat(), 'label': self.label}


def _d(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def month_period(year, month, label=None):
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return Period(date(year, month, 1), end, label or f'{month:02d}/{year}', 'month')


class Calendar:
    def __init__(self, path=None):
        self.lunar = {}
        if path and Path(path).is_file():
            with open(path, encoding='utf-8-sig', newline='') as fh:
                for row in csv.DictReader(fh):
                    key = (int(row['lunar_year']), int(row['lunar_month']), int(row['lunar_day']),
                           str(row.get('lunar_leap', '')).strip().lower() == 'true')
                    self.lunar.setdefault(key, date.fromisoformat(row['date']))

    def solar(self, year, month, day, leap=False):
        return self.lunar.get((year, month, day, leap))


def resolve(spec: dict, today: date, calendar: Calendar | None = None) -> Period:
    t = spec.get('type')
    today = _d(today)
    if t == 'day':
        d = _d(spec['date'])
        return Period(d, d + timedelta(days=1), d.isoformat(), 'day')
    if t == 'today':
        return Period(today, today + timedelta(days=1), 'today', 'day')
    if t == 'yesterday':
        y = today - timedelta(days=1)
        return Period(y, today, 'yesterday', 'day')
    if t == 'month':
        year = spec.get('year')
        month = int(spec['month'])
        if not year:
            year = today.year if date(today.year, month, 1) <= today else today.year - 1
        return month_period(int(year), month)
    if t == 'quarter':
        q = int(spec['quarter'])
        year = spec.get('year') or (today.year if date(today.year, 3 * q - 2, 1) <= today else today.year - 1)
        start = date(int(year), 3 * q - 2, 1)
        end = date(int(year) + 1, 1, 1) if q == 4 else date(int(year), 3 * q + 1, 1)
        return Period(start, end, f'Q{q}/{year}', 'quarter')
    if t == 'year':
        y = int(spec['year'])
        return Period(date(y, 1, 1), date(y + 1, 1, 1), str(y), 'year')
    if t == 'range' and not (spec.get('start') and spec.get('end')) and (spec.get('days') or spec.get('n')):
        t, spec = 'last_n_days', {'n': spec.get('days') or spec.get('n')}       # {"type": "range", "days": 30}
    if t == 'range':
        s, e = _d(spec['start']), _d(spec['end'])
        return Period(s, e + timedelta(days=1), f'{s}..{e}', 'range')
    if t == 'this_week':
        monday = today - timedelta(days=today.weekday())
        return Period(monday, today + timedelta(days=1), 'this week', 'week_to_date')
    if t == 'last_week':
        monday = today - timedelta(days=today.weekday())
        return Period(monday - timedelta(days=7), monday, 'last week', 'week')
    if t == 'this_month':
        return Period(today.replace(day=1), today + timedelta(days=1), 'this month', 'month_to_date')
    if t == 'last_month':
        first = today.replace(day=1)
        prev = (first - timedelta(days=1)).replace(day=1)
        return Period(prev, first, 'last month', 'month')
    if t == 'year_to_date':
        return Period(date(today.year, 1, 1), today + timedelta(days=1), 'year to date', 'ytd')
    if t == 'last_n_days':
        n = int(spec['n'])
        return Period(today - timedelta(days=n - 1), today + timedelta(days=1), f'last {n} days', 'n_days')
    if t == 'tet':
        if calendar is None:
            raise ValueError('calendar.csv is required for Tết')
        y = int(spec['year'])
        start = calendar.solar(y - 1, 12, 23)
        end = calendar.solar(y, 1, 10)
        if not start or not end:
            raise ValueError(f'Tết {y} outside calendar')
        return Period(start, end + timedelta(days=1), f'Tết {y}', 'tet')
    if t == 'as_of':
        d = _d(spec.get('date') or today)
        return Period(date(1900, 1, 1), d + timedelta(days=1), f'as of {d}', 'as_of')
    raise ValueError(f'Unknown period type {t!r}')


def previous_period(p: Period, how: str = 'previous') -> Period:
    """Comparison base (rulebook §1, §2)."""
    if how == 'same_period_last_year':
        def shift(d):
            try:
                return d.replace(year=d.year - 1)
            except ValueError:
                return d.replace(year=d.year - 1, day=28)
        return Period(shift(p.start), shift(p.end), f'{p.label} last year', p.kind)
    if p.kind == 'month':
        prev = (p.start - timedelta(days=1)).replace(day=1)
        return month_period(prev.year, prev.month)
    if p.kind == 'month_to_date':
        prev_first = (p.start - timedelta(days=1)).replace(day=1)
        last_day = monthrange(prev_first.year, prev_first.month)[1]
        day = min((p.end - timedelta(days=1)).day, last_day)
        return Period(prev_first, prev_first.replace(day=day) + timedelta(days=1), 'same days last month', 'range')
    if p.kind == 'quarter':
        end = p.start
        start = date(end.year - 1, 10, 1) if end.month == 1 else date(end.year, end.month - 3, 1)
        return Period(start, end, 'previous quarter', 'quarter')
    if p.kind in ('week', 'week_to_date'):
        return Period(p.start - timedelta(days=7), p.end - timedelta(days=7), 'previous week', p.kind)
    if p.kind == 'year':
        return Period(date(p.start.year - 1, 1, 1), p.start, str(p.start.year - 1), 'year')
    n = p.days                                     # tet, n_days, day, range: same length right before
    return Period(p.start - timedelta(days=n), p.start, f'{n} days before', 'range')
