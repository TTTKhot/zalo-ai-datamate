"""Model reply -> SQL -> read-only DuckDB -> typed answer -> vote."""
from __future__ import annotations

import datetime as dt
import decimal
import math
import re
import threading

from .text import norm_key

TYPES = ('number', 'percent', 'date', 'boolean', 'string', 'list', 'table', 'unanswerable')
_BANNED = re.compile(r'\b(read_\w+|glob|attach|detach|copy|install|load|export|import|pragma)\b', re.I)


# ---------------------------------------------------------------- reply parsing
def parse_reply(text: str) -> dict:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).split('</think>')[-1]
    out = {'type': None, 'period': None, 'sql': None, 'reason': None, 'note': None}
    m = re.search(r'^\s*TYPE\s*[:：]\s*\**\s*([a-zA-Z_]+)', text, flags=re.M)
    if m and m.group(1).lower() in TYPES:
        out['type'] = m.group(1).lower()
    m = re.search(r'^\s*PERIOD\s*[:：]\s*(\d{4}-\d{2}-\d{2})\s*(?:\.\.|→|->|to|đến)\s*(\d{4}-\d{2}-\d{2})', text, flags=re.M)
    if m:
        try:
            out['period'] = (dt.date.fromisoformat(m.group(1)), dt.date.fromisoformat(m.group(2)))
        except ValueError:
            pass
    m = re.search(r'^\s*NOTE\s*[:：]\s*(.+?)(?=^\s*(?:PERIOD|TYPE|SQL)\s*[:：])', text, flags=re.M | re.S)
    if m:
        out['note'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:500]
    m = re.search(r'^\s*REASON\s*[:：]\s*(.+)$', text, flags=re.M)
    if m:
        out['reason'] = m.group(1).strip()[:300]
    m = re.search(r'```(?:sql)?\s*(.*?)```', text, flags=re.S | re.I)
    sql = m.group(1) if m else None
    if sql is None:
        tail = re.split(r'^\s*SQL\s*[:：]', text, flags=re.M)[-1]
        m = re.search(r'\b(with|select)\b', tail, flags=re.I)
        sql = tail[m.start():] if m else None
    if sql:
        out['sql'] = sql.strip().rstrip(';').strip()
    return out


def check_sql(sql: str) -> str | None:
    """Returns a problem text, or None when the query may run."""
    if not sql:
        return 'không có câu SQL'
    if not re.match(r'^\s*(with|select)\b', sql, flags=re.I):
        return 'chỉ được viết một câu SELECT (hoặc WITH ... SELECT)'
    if _BANNED.search(sql):
        return 'không được dùng hàm đọc file / lệnh hệ thống'
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return None if ';' not in sql else 'chỉ được viết đúng một câu lệnh'
    try:
        trees = [t for t in sqlglot.parse(sql, read='duckdb') if t is not None]
    except Exception:
        return None                                   # let DuckDB give the precise error
    if len(trees) != 1:
        return 'chỉ được viết đúng một câu lệnh'
    if not isinstance(trees[0], exp.Query):
        return 'chỉ được viết câu SELECT'
    return None


# ---------------------------------------------------------------- execution
class ShopDB:
    """Read-only DuckDB file of one shop; one cursor per query, wall-clock timeout by interrupt."""

    def __init__(self, db_path: str):
        import duckdb
        try:
            self.con = duckdb.connect(str(db_path), read_only=True, config={'enable_external_access': 'false'})
        except Exception:
            self.con = duckdb.connect(str(db_path), read_only=True)
            try:
                self.con.execute('SET enable_external_access = false')
            except Exception:
                pass

    def run(self, sql: str, timeout_s: float = 20.0, max_rows: int = 500):
        cur = self.con.cursor()
        timer = threading.Timer(timeout_s, cur.interrupt)
        timer.start()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(max_rows + 1)
        finally:
            timer.cancel()
            cur.close()
        if len(rows) > max_rows:
            raise ValueError(f'kết quả quá {max_rows} dòng - câu hỏi cần một giá trị, một danh sách ngắn hoặc một bảng nhỏ')
        return cols, [list(r) for r in rows]

    def close(self):
        self.con.close()


# ---------------------------------------------------------------- typed answers
def _cell(v):
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if hasattr(v, 'item') and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except Exception:
            pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dt.datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat(sep=' ')
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip() or None
    return v


def _num(v, digits: int = 2):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError:
            return None
    if not isinstance(v, (int, float)):
        return None
    v = round(float(v), digits)
    return int(v) if v.is_integer() else v


def _elem(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return _num(v)
    return v


def to_answer(cols: list, rows: list, typ: str):
    """-> (status, answer). status: ok | empty (no usable value) | shape (wrong result shape for the type)."""
    rows = [[_cell(v) for v in r] for r in rows]
    if not rows or not cols:
        return 'empty', None
    single = rows[0][0] if len(rows) == 1 and len(cols) == 1 else None
    if typ in ('number', 'percent', 'date', 'boolean', 'string'):
        if len(rows) != 1 or len(cols) != 1:
            return 'shape', None
        if single is None:
            return 'empty', None
    if typ in ('number', 'percent'):
        v = _num(single)
        if v is None:
            return 'shape', None
        if typ == 'number' and isinstance(v, float) and abs(v) >= 1000:
            v = int(math.floor(v + 0.5))              # a large non-integer number is money: round to đồng, half up
        return 'ok', v
    if typ == 'date':
        s = str(single)
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}([ T].*)?', s):
            return 'ok', s[:10]
        return ('ok', s) if re.fullmatch(r'\d{4}-\d{2}', s) else ('shape', None)
    if typ == 'boolean':
        if isinstance(single, bool):
            return 'ok', single
        if isinstance(single, (int, float)) and single in (0, 1):
            return 'ok', bool(single)
        if isinstance(single, str) and single.lower() in ('true', 'false'):
            return 'ok', single.lower() == 'true'
        return 'shape', None
    if typ == 'string':
        return 'ok', str(single)
    if typ == 'list':
        if len(cols) == 1:
            values = [r[0] for r in rows]
        elif len(rows) == 1:
            values = rows[0]
        else:
            values = [r[0] for r in rows]             # (name, measure) rows: keep the names
        if any(v is None for v in values):
            return 'empty', None
        return 'ok', [_elem(v) for v in values]
    if typ == 'table':
        if any(r[0] is None for r in rows):
            return 'empty', None
        return 'ok', {'columns': [str(c) for c in cols], 'rows': [[_elem(v) for v in r] for r in rows]}
    return 'shape', None


def _key_elem(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return norm_key(v)


def answer_key(typ: str, answer):
    """Two answers with the same key are the same answer for the scorer (rulebook §9)."""
    if typ == 'unanswerable':
        return ('u',)
    if typ in ('number', 'percent'):
        return ('n', round(float(answer), 2))
    if typ == 'date':
        return ('d', answer)
    if typ == 'boolean':
        return ('b', answer)
    if typ == 'string':
        return ('s', norm_key(answer))
    if typ == 'list':
        return ('l', tuple(_key_elem(v) for v in answer))
    if typ == 'table':
        return ('t', tuple(sorted(tuple(repr(_key_elem(v)) for v in r) for r in answer['rows'])))
    return ('?', repr(answer))


def is_zero(typ: str, answer) -> bool:
    if typ in ('number', 'percent'):
        return float(answer) == 0.0
    if typ == 'list':
        return len(answer) == 0
    if typ == 'table':
        return len(answer['rows']) == 0
    return typ == 'string' and not str(answer).strip()


# ---------------------------------------------------------------- vote
def vote(samples: list[dict], threshold: float = 0.5, unans_threshold: float = 0.5,
         zero_threshold: float = 1.01) -> dict:
    """samples: [{'status': 'ok'|'unanswerable'|..., 'type', 'answer'}]. Every sample counts in the
    denominator, so failed drafts lower the confidence. Ties go to the earliest sample (sample 0 is greedy)."""
    total = len(samples)
    groups: dict = {}
    for i, s in enumerate(samples):
        if s.get('status') == 'ok':
            key = answer_key(s['type'], s['answer'])
        elif s.get('status') == 'unanswerable':
            key = ('u',)
        else:
            continue
        g = groups.setdefault(key, {'count': 0, 'first': i, 'types': {}})
        g['count'] += 1
        t = 'unanswerable' if key == ('u',) else s['type']
        g['types'][t] = g['types'].get(t, 0) + 1
    out = {'decision': 'abstain', 'confidence': 0.0, 'n_samples': total, 'n_valid': sum(g['count'] for g in groups.values()),
           'n_groups': len(groups), 'type': None, 'answer': None, 'reason': None}
    if not groups or not total:
        return out
    key, best = min(groups.items(), key=lambda kv: (-kv[1]['count'], kv[1]['first']))
    first = samples[best['first']]
    conf = best['count'] / total
    out['confidence'] = round(conf, 4)
    if key == ('u',):
        out.update(type='unanswerable', reason=first.get('reason') or 'Dữ liệu không đủ để trả lời')
        if conf >= unans_threshold:
            out['decision'] = 'unanswerable'
        return out
    typ = max(best['types'].items(), key=lambda kv: kv[1])[0]
    answer = next(s['answer'] for s in samples if s.get('status') == 'ok' and s['type'] == typ
                  and answer_key(s['type'], s['answer']) == key)
    out.update(type=typ, answer=answer)
    need = max(threshold, zero_threshold) if is_zero(typ, answer) else threshold
    if conf >= need:
        out['decision'] = 'answer'
    return out
