"""Vietnamese time-expression tagger (a fixed tool, like a date parser).

Finds periods written in the question (accent-free, normalised text): tháng m/yyyy,
quý q/yyyy, dd/mm/yyyy, từ..đến.., tính đến hết.., N ngày gần nhất, Tết yyyy, tuần này/trước,
tháng này/trước, hôm nay/hôm qua, từ đầu năm. Output uses the intent period vocabulary.
The LLM still decides the metric, filters and comparison; when the tagger finds an
explicit period and the LLM wrote a different one, the tagger wins (see reconcile_periods).
"""
from __future__ import annotations

import re


_NUMWORD = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
# a count written as a word, only right before a time span ("ba thang lien nhau", "bay ngay gan nhat")
_NUMWORD_RX = re.compile(r'(?<![a-z0-9])(mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi) '
                         r'(?=thang lien|ngay (?:gan nhat|qua|vua qua|gan day))')
# "thang 5 nam nay", "quy 2 nam ngoai/truoc": the year said relative to today
_REL_YEAR_RX = re.compile(r'(?<![a-z0-9])(thang|quy) (\d{1,2}) nam (nay|ngoai|truoc|trc|roi)(?![a-z0-9])')
_RANGE_RX = re.compile(r'tu thang (\d{1,2})(?:\s*(?:/|nam)\s*(20\d{2}))? (?:den|toi|cho den|cho toi) (?:het )?'
                       r'thang (\d{1,2})(?:\s*(?:/|nam)\s*(20\d{2}))?(?![\d/])')


def _ym(as_of):
    """(year, month) of as_of ('YYYY-MM-DD...'), or None when it is missing or not a date."""
    m = re.match(r'\s*(\d{4})-(\d{1,2})', str(as_of or ''))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _canon(q, as_of):
    """Rewrite relative years and counts in words into the explicit forms below (general Vietnamese)."""
    q = _NUMWORD_RX.sub(lambda m: f'{_NUMWORD[m.group(1)]} ', q)
    ym = _ym(as_of)
    if ym:
        q = _REL_YEAR_RX.sub(lambda m: f'{m.group(1)} {m.group(2)}/{ym[0] - (m.group(3) != "nay")}', q)
    return q


def _year_of_month(month, as_of):
    """Rulebook: a month without a year is this year's unless it starts after today, then last year's."""
    ym = _ym(as_of)
    if not ym:
        return None
    return ym[0] if month <= ym[1] else ym[0] - 1


def _month_range(q, as_of):
    m = _RANGE_RX.search(q)
    if not m:
        return []
    a, ya, b, yb = m.groups()
    a, b = int(a), int(b)
    if not (1 <= a <= 12 and 1 <= b <= 12):
        return []
    if yb:
        yb = int(yb)
    elif ya and b >= a:
        yb = int(ya)
    else:
        yb = _year_of_month(b, as_of)
        if yb is None:
            return []
    ya = int(ya) if ya else (yb if a <= b else yb - 1)
    n = (yb - ya) * 12 + b - a + 1
    if not 2 <= n <= 24:
        return []
    out, mm, yy = [], a, ya
    for _ in range(n):
        out.append({'type': 'month', 'month': mm, 'year': yy})
        mm, yy = (1, yy + 1) if mm == 12 else (mm + 1, yy)
    return out


def _months(q, as_of=None):
    m = re.search(r'(\d) thang lien (?:nhau|tiep) ket thuc (?:o|vao|tai) thang (\d{1,2})(?:\s*(?:/|nam)\s*(20\d{2}))?'
                  r'(?![\d/])', q)
    if m and (m.group(3) or _ym(as_of)):
        n, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else _year_of_month(mo, as_of)
        out = []
        for i in range(n - 1, -1, -1):
            mm, yy = mo - i, y
            while mm <= 0:
                mm, yy = mm + 12, yy - 1
            out.append({'type': 'month', 'month': mm, 'year': yy})
        return out
    rng = _month_range(q, as_of)
    if rng:
        return rng
    if re.search(r'thang', q) and not re.search(r'\d{1,2}/\d{1,2}/20\d{2}', q):
        toks = re.findall(r'(?<![\d/])(\d{1,2})\s*/\s*(20\d{2})', q)
        if len(toks) >= 2:
            return [{'type': 'month', 'month': int(a), 'year': int(b)} for a, b in toks]
    out = []
    for m in re.finditer(r'thang (\d{1,2})\s*(?:/|nam|-)\s*(20\d{2})', q):
        out.append({'type': 'month', 'month': int(m.group(1)), 'year': int(m.group(2))})
    return out


def periods_of(q, as_of):
    q = _canon(q, as_of)
    tet =re.search(r'tet (?:am lich )?(?:nam )?(20\d{2})', q)
    if tet:
        return [{'type': 'tet', 'year': int(tet.group(1))}]
    rel = re.search(r'tet (?:nam )?(nay|truoc|trc|ngoai|roi)\b', q)
    if rel and as_of:
        y = int(str(as_of)[:4]) - (0 if rel.group(1) == 'nay' else 1)
        return [{'type': 'tet', 'year': y}]
    m = re.search(r'(\d+) ngay (?:gan nhat|qua|vua qua|gan day)', q)
    if m:
        return [{'type': 'last_n_days', 'n': int(m.group(1))}]
    m = re.search(r'tu (?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2}) den (?:het )?(?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2})', q)
    if m:
        g = list(map(int, m.groups()))
        return [{'type': 'range', 'start': f'{g[2]}-{g[1]:02d}-{g[0]:02d}', 'end': f'{g[5]}-{g[4]:02d}-{g[3]:02d}'}]
    m = re.search(r'(?:den het|toi het|tinh den|tinh toi|theo ton kho) (?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2})', q)
    if m:
        return [{'type': 'as_of', 'date': f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'}]
    m = re.search(r'tu (?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2}) den (?:het )?(?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2})', q)
    if m:
        g = list(map(int, m.groups()))
        return [{'type': 'range', 'start': f'{g[2]}-{g[1]:02d}-{g[0]:02d}', 'end': f'{g[5]}-{g[4]:02d}-{g[3]:02d}'}]
    months = _months(q, as_of)
    m = re.search(r'quy (\d)\s*(?:/|nam|-)?\s*(20\d{2})', q)
    if m:
        return [{'type': 'quarter', 'quarter': int(m.group(1)), 'year': int(m.group(2))}]
    if months:
        return months
    m = re.search(r'(?:ngay )?(\d{1,2})/(\d{1,2})/(20\d{2})', q)
    if m:
        return [{'type': 'day', 'date': f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'}]
    if re.search(r'tu dau nam|\bdau nam (?:den|toi|cho den)|tu (?:ngay )?1/1(?: nam nay)? den|nam nay', q) and not _months(q):
        return [{'type': 'year_to_date'}]
    # months named without a year ("thang 8, thang 9 va thang 10", "thang 3 hon hay kem thang truoc"): every named
    # month counts (the year of each follows the rulebook in periods.py), and a named month beats "thang truoc/nay"
    bare = list(dict.fromkeys(int(x) for x in re.findall(r'(?<![\d/])thang (\d{1,2})(?![\d/])', q)))
    bare = [mo for mo in bare if 1 <= mo <= 12]
    if bare and re.search(r'thang (?:nay|truoc|roi|vua roi)|tu dau thang', q):
        return [{'type': 'month', 'month': mo} for mo in bare]
    if re.search(r'tuan nay', q):
        return [{'type': 'this_week'}]
    if re.search(r'tuan (?:truoc|roi|vua roi)', q):
        return [{'type': 'last_week'}]
    if re.search(r'thang nay|tu dau thang|tu (?:ngay )?mung (?:1|mot) (?:den|toi)', q):
        return [{'type': 'this_month'}]
    if re.search(r'thang (?:truoc|roi|vua roi)', q) and \
            not re.search(r'so (?:voi|vs) (?:cung ky )?thang (?:truoc|roi|vua roi)', q):
        return [{'type': 'last_month'}]
    if re.search(r'hom nay|bua nay|het nay|cuoi ngay', q):
        return [{'type': 'today'}]
    if re.search(r'hom qua|bua qua', q):
        return [{'type': 'yesterday'}]
    if bare:
        return [{'type': 'month', 'month': mo} for mo in bare]
    return []


def _key(p: dict):
    return tuple((k, p.get(k)) for k in ('type', 'month', 'quarter', 'date', 'start', 'end', 'n')) + \
        (('year', p.get('year')) if p.get('type') != 'month' or p.get('year') else ())


def same_period(a: dict, b: dict) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if a.get('type') == b.get('type') == 'month' and a.get('month') == b.get('month'):
        return not a.get('year') or not b.get('year') or int(a['year']) == int(b['year'])
    return _key(a) == _key(b)


def reconcile_periods(llm_periods, tagged):
    """Return (periods, overridden). Keep the LLM's list when it already contains every tagged period."""
    llm_periods = [p for p in (llm_periods or []) if isinstance(p, dict)]
    if not tagged:
        return llm_periods, False
    if all(any(same_period(t, p) for p in llm_periods) for t in tagged):
        return llm_periods, False
    return tagged, True
