"""Step 2 of v6: a second, independent route to the answer - Qwen writes SQL over the canonical views.

The metric route (intent JSON -> metric library) and the SQL route share only the canonical
tables built by rules.py. When both produce the same answer the answer is more likely right;
calibration learns how much more (feature `agree`).

Safety and determinism:
  * sqlglot parses the text (duckdb dialect); exactly one read-only query; every table must be
    a canonical view (or a CTE); every column must exist in some view (or be an alias);
    file / network table functions are refused;
  * duckdb runs in memory with external access disabled and a wall-clock interrupt.

The prompt gives the resolved periods (start / end-exclusive) from the date tagger, the
rulebook defaults that the views already encode (counts_for_revenue, qty_base ...) and the
shop names relevant to the question. Nothing refers to a question id or a shop.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import re
import threading

import numpy as np
import pandas as pd

from .intent import relevant_names
from .metrics import money, pct
from .periods import resolve

TABLES = ('sales_lines', 'orders', 'products', 'payments', 'purchase_lines', 'purchases', 'stock_snapshot')
COLUMN_DOC = {
    'order_id': 'mã đơn', 'order_date': 'ngày bán (DATE)', 'order_status': "trạng thái đơn: 'hoàn thành' | 'đang giao' | 'huỷ' | 'trả hàng'",
    'counts_for_revenue': 'TRUE nếu đơn tính vào doanh thu (không huỷ, không trả hàng) - luôn lọc cột này khi tính doanh thu / bán chạy',
    'product': 'tên hàng chuẩn', 'product_key': 'khoá mặt hàng', 'qty': 'số lượng theo đơn vị của dòng',
    'qty_base': 'số lượng quy ra đơn vị cơ bản (dùng cho "bán được bao nhiêu")', 'base_unit': 'đơn vị cơ bản',
    'unit': 'đơn vị của dòng', 'factor': 'hệ số quy đổi ra đơn vị cơ bản',
    'unit_price': 'đơn giá của dòng', 'unit_price_base': 'đơn giá một đơn vị cơ bản',
    'line_total': 'thành tiền dòng sau giảm giá dòng (doanh thu dòng)', 'line_cost': 'giá vốn của dòng',
    'revenue': 'doanh thu của đơn = tổng line_total', 'is_item': 'FALSE cho phí phục vụ',
    'customer_key': 'khoá khách (NULL = khách lẻ)', 'customer': 'tên khách', 'customer_group': 'nhóm khách',
    'payment_method': 'hình thức thanh toán', 'staff': 'nhân viên', 'hour': 'giờ tạo đơn (0-23)',
    'order_total': 'tổng phải trả của đơn', 'paid_amount': 'đã trả', 'pay_date': 'ngày trả (DATE)',
    'amount': 'số tiền trả', 'purchase_date': 'ngày nhập (DATE)', 'supplier': 'nhà cung cấp',
    'cancelled': 'TRUE nếu phiếu nhập bị huỷ', 'total': 'tổng tiền phiếu nhập', 'qty_on_hand': 'tồn hiện tại',
    'unit_cost': 'giá vốn một đơn vị', 'group': 'nhóm hàng', 'n_lines': 'số dòng của đơn',
}
RULES = ('Quy tắc mặc định (đã có sẵn trong bảng): doanh thu = SUM(orders.revenue) hoặc SUM(sales_lines.line_total) '
         'với counts_for_revenue = TRUE; số đơn = COUNT(DISTINCT order_id) với counts_for_revenue = TRUE; '
         '"bán chạy" = theo SUM(qty_base); kỳ là [start, end_exclusive) trên order_date; '
         'huỷ = order_status = \'huỷ\'; tỉ lệ % làm tròn 2 chữ số; tiền làm tròn đơn vị đồng.')
SYSTEM = ('You write ONE DuckDB SQL SELECT that answers a Vietnamese shop question from the given tables. '
          'Use only the listed tables and columns. Return one row with one column for a single value, '
          'one column for a list (ordered), two columns (name, value) for a table. Output SQL only.')
BANNED_FUNCS = re.compile(r'^(read_|glob|sniff_|parquet_|query_table|scan|http|s3|attach|load|install)', re.I)


def frames_for_sql(views):
    """Canonical frames as duckdb-friendly pandas frames (python dates -> datetime64, objects -> str)."""
    out = {}
    for name in TABLES:
        df = views.frames.get(name)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            continue
        df = df.copy()
        for c in df.columns:
            s = df[c]
            if s.dtype == object:
                sample = s.dropna().head(50)
                if len(sample) and all(isinstance(v, _dt.date) and not isinstance(v, _dt.datetime) for v in sample):
                    df[c] = pd.to_datetime(s)
                elif len(sample) and all(isinstance(v, (bool, np.bool_)) for v in sample):
                    df[c] = s.astype('boolean')
                else:
                    df[c] = s.map(lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) else str(v))
        out[name] = df.reset_index(drop=True)
    return out


def schema_text(frames: dict, max_samples=3) -> str:
    lines = []
    for name, df in frames.items():
        cols = []
        for c in df.columns:
            if df[c].isna().all():
                continue
            kind = ('DATE' if str(df[c].dtype).startswith('datetime') else 'BOOL' if str(df[c].dtype) in ('bool', 'boolean')
                    else 'NUM' if pd.api.types.is_numeric_dtype(df[c]) else 'TEXT')
            sample = ''
            if kind == 'TEXT':
                vals = df[c].dropna().astype(str).value_counts().head(max_samples).index.tolist()
                sample = ' e.g. ' + ' | '.join(v[:30] for v in vals)
            doc = COLUMN_DOC.get(c, '')
            cols.append(f'  {c} {kind}' + (f' -- {doc}' if doc else '') + sample)
        lines.append(f'TABLE {name} ({len(df)} rows)\n' + '\n'.join(cols))
    return '\n'.join(lines)


def resolved_periods(tagged, as_of, calendar):
    out = []
    for p in tagged or []:
        try:
            r = resolve(p, _dt.date.fromisoformat(str(as_of)[:10]), calendar)
            out.append(r.to_json())
        except Exception:
            continue
    return out


def build_sql_messages(question, as_of, schema, names, periods, normalized=None):
    rel = relevant_names(question, names, normalized, per_kind=8)
    names_txt = '\n'.join(f'{k}: {"; ".join(v)}' for k, v in rel.items() if v)
    user = (f'{schema}\n\n{RULES}\nNAMES:\n{names_txt}\n\ntoday (as_of_date): {as_of}\n'
            f'PERIODS found in the question: {json.dumps(periods, ensure_ascii=False)}\n'
            f'Q: {question}\n' + (f'(normalized: {normalized})\n' if normalized else '') + 'SQL:')
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]


def extract_sql(text: str) -> str:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S)
    m = re.search(r'```(?:sql)?\s*(.*?)```', text, flags=re.S | re.I)
    if m:
        text = m.group(1)
    m = re.search(r'\b(with|select)\b', text, flags=re.I)
    text = text[m.start():] if m else text
    return text.strip().rstrip(';').strip()


def validate_sql(sql: str, frames: dict) -> list[str]:
    """sqlglot checks; returns problems (empty = ok)."""
    import sqlglot
    from sqlglot import exp
    problems = []
    try:
        trees = [t for t in sqlglot.parse(sql, read='duckdb') if t is not None]
    except Exception as exc:
        return [f'parse error: {str(exc)[:200]}']
    if len(trees) != 1:
        return [f'expected one statement, got {len(trees)}']
    tree = trees[0]
    if not isinstance(tree, exp.Query):
        return [f'not a SELECT query ({type(tree).__name__})']
    bad = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Command, exp.Alter, exp.Copy) \
        if hasattr(exp, 'Copy') else (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Command, exp.Alter)
    for node in tree.walk():
        node = node[0] if isinstance(node, tuple) else node
        if isinstance(node, bad):
            problems.append(f'forbidden statement {type(node).__name__}')
        if isinstance(node, (exp.Anonymous, exp.Func)):
            fname = node.name if isinstance(node, exp.Anonymous) else (node.sql_name() if hasattr(node, 'sql_name') else '')
            if fname and BANNED_FUNCS.search(str(fname)):
                problems.append(f'forbidden function {fname}')
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if t.name and t.name not in frames and t.name not in ctes:
            problems.append(f'unknown table {t.name}')
        if isinstance(t.this, exp.Func) or t.args.get('db') or t.args.get('catalog'):
            problems.append(f'table expression not allowed: {t.sql()[:60]}')
    known = {c for df in frames.values() for c in df.columns}
    aliases = {a.alias for a in tree.find_all(exp.Alias) if a.alias}
    aliases |= {c.alias_or_name for c in tree.find_all(exp.CTE)}
    for cte in tree.find_all(exp.CTE):
        aliases |= set(getattr(cte, 'alias_column_names', None) or [])
    for col in tree.find_all(exp.Column):
        if col.name and col.name not in known and col.name not in aliases and not col.name.startswith('_'):
            problems.append(f'unknown column {col.name}')
    return sorted(set(problems))


def run_sql(sql: str, frames: dict, timeout_s: float = 10.0):
    import duckdb
    con = duckdb.connect(':memory:')
    try:
        for name, df in frames.items():
            con.register(name, df)
        con.execute("SET enable_external_access = false")
        try:
            con.execute("SET lock_configuration = true")
        except Exception:
            pass
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
        try:
            return con.execute(sql).fetchdf()
        finally:
            timer.cancel()
    finally:
        con.close()


def _scalar(v):
    if isinstance(v, (np.generic,)):
        v = v.item()
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat() if v == v.normalize() else v.isoformat()
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()[:10]
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def result_value(df: pd.DataFrame):
    """DataFrame -> answer-shaped value (scalar, list or table dict)."""
    if df is None or df.empty:
        return None
    if df.shape == (1, 1):
        return _scalar(df.iat[0, 0])
    if df.shape[1] == 1:
        return [_scalar(v) for v in df.iloc[:, 0]]
    if df.shape[0] == 1:
        return [_scalar(v) for v in df.iloc[0]]
    return {'columns': [str(c) for c in df.columns[:2]],
            'rows': [[_scalar(a), _scalar(b)] for a, b in zip(df.iloc[:, 0], df.iloc[:, 1])]}


def _num_eq(a, b, kind):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if kind == 'percent':
        return pct(a) == pct(b) or abs(a - b) < 0.006
    if abs(b) >= 1:
        return money(a) == money(b) or abs(a - b) <= 1e-6 * abs(b)
    return abs(a - b) < 1e-6


def _txt(v):
    from .scoring import _norm_text
    return _norm_text(v)


def answers_agree(sql_value, answer, kind) -> bool:
    """Is the SQL result the same answer as the metric route (after §9 rounding)?"""
    if sql_value is None or answer is None:
        return False
    if kind in ('number', 'percent'):
        if isinstance(sql_value, list) and len(sql_value) == 1:
            sql_value = sql_value[0]
        return not isinstance(sql_value, (list, dict, str, bool)) and _num_eq(sql_value, answer, kind)
    if kind == 'boolean':
        return bool(sql_value) is answer if isinstance(sql_value, (bool, np.bool_, int)) else False
    if kind == 'date':
        return isinstance(sql_value, str) and sql_value[:len(answer)] == answer
    if kind == 'string':
        if isinstance(sql_value, list) and sql_value:
            sql_value = sql_value[0]
        return isinstance(sql_value, str) and _txt(sql_value) == _txt(answer)
    if kind == 'list':
        if not isinstance(sql_value, list):
            sql_value = [sql_value]
        if len(sql_value) != len(answer):
            return False
        return all(_num_eq(a, b, 'number') if isinstance(b, (int, float)) and not isinstance(b, bool)
                   else _txt(a) == _txt(b) for a, b in zip(sql_value, answer))
    if kind == 'table':
        if not isinstance(sql_value, dict):
            return False
        a = sorted((_txt(r[0]), money(r[1]) if r[1] is not None else None) for r in sql_value['rows'])
        b = sorted((_txt(r[0]), money(r[1]) if r[1] is not None else None) for r in answer['rows'])
        return a == b
    return False


def format_like(sql_value, kind):
    """Shape a SQL value as an answer of the given type (used when SQL is the only route)."""
    if kind == 'percent':
        return pct(sql_value)
    if kind == 'number':
        v = float(sql_value)
        return int(round(v)) if abs(v - round(v)) < 1e-9 or abs(v) >= 100 else round(v, 2)
    return sql_value


def guess_kind(sql_value):
    if isinstance(sql_value, bool):
        return 'boolean'
    if isinstance(sql_value, (int, float)):
        return 'number'
    if isinstance(sql_value, dict):
        return 'table'
    if isinstance(sql_value, list):
        return 'list'
    if isinstance(sql_value, str) and re.fullmatch(r'\d{4}-\d{2}(-\d{2})?', sql_value):
        return 'date'
    return 'string'


class SqlRoute:
    """Per-shop SQL route: build frames + schema once, then answer questions."""

    def __init__(self, shop, backend, calendar, max_repairs=1, timeout_s=10.0):
        self.shop, self.backend, self.cal = shop, backend, calendar
        self.frames = frames_for_sql(shop.views)
        self.schema = schema_text(self.frames)
        self.max_repairs = max_repairs
        self.timeout_s = timeout_s

    def ask(self, question, as_of, norm=None, tagged=None) -> dict:
        periods = resolved_periods(tagged, as_of, self.cal)
        messages = build_sql_messages(question, as_of, self.schema, self.shop.names, periods, norm)
        rec = {'sql': None, 'sql_status': 'none', 'sql_raw': [], 'sql_value': None}
        for attempt in range(self.max_repairs + 1):
            raw = self.backend.generate(messages, max_new_tokens=400)
            rec['sql_raw'].append(raw)
            sql = extract_sql(raw)
            rec['sql'] = sql
            problems = validate_sql(sql, self.frames) if sql else ['empty SQL']
            if not problems:
                try:
                    df = run_sql(sql, self.frames, self.timeout_s)
                    value = result_value(df)
                    rec.update(sql_status='ok' if value is not None else 'empty', sql_value=value)
                    return rec
                except Exception as exc:
                    problems = [f'execution error: {str(exc)[:300]}']
            rec['sql_status'] = 'invalid' if not problems[0].startswith('execution') else 'error'
            rec['sql_problems'] = problems
            if attempt < self.max_repairs:
                messages = messages + [{'role': 'assistant', 'content': raw},
                                       {'role': 'user', 'content': 'Lỗi: ' + '; '.join(problems) + '. Viết lại đúng một câu SQL.'}]
        return rec


def attach_sql(out: dict, sql_rec: dict) -> dict:
    """Merge the SQL route into a pipeline output: agreement feature, SQL-only fallback route."""
    out = dict(out)
    out.update({k: v for k, v in sql_rec.items() if k != 'sql_raw'})
    out['sql_raw'] = sql_rec.get('sql_raw')
    status = out.get('status')
    if status == 'answered':
        out['agree'] = 'agree' if answers_agree(sql_rec.get('sql_value'), out.get('answer'), out.get('type')) \
            else ('disagree' if sql_rec.get('sql_status') == 'ok' else 'nosql')
    elif status == 'unanswerable':
        out['agree'] = 'nosql' if sql_rec.get('sql_status') != 'ok' else 'disagree'
    elif status == 'abstain' and sql_rec.get('sql_status') == 'ok':
        kind = guess_kind(sql_rec['sql_value'])
        try:
            value = format_like(sql_rec['sql_value'], kind)
            out.update(status='answered', answer=value, type=kind, route='sql', agree='sql_only',
                       metric_reason=out.get('reason'))
        except Exception:
            out['agree'] = 'nosql'
    else:
        out['agree'] = 'nosql'
    return out
