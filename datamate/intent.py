"""Question -> intent JSON. The LLM fills the JSON; fixed checks validate it.

The prompt lists the metric library, the period vocabulary and the names that exist in
this shop (products, groups, customers, payment methods) so the model copies names
instead of inventing them. No question ids or business ids are involved.
"""
from __future__ import annotations

import json
import re

from .metrics import METRICS, NO_PERIOD, match_name
from .values import plain

PERIOD_TYPES = ('day', 'month', 'quarter', 'year', 'range', 'today', 'yesterday', 'this_week', 'last_week',
                'this_month', 'last_month', 'year_to_date', 'last_n_days', 'tet', 'as_of')
FILTER_KEYS = ('product', 'group', 'size', 'unit', 'payment_method', 'shift', 'customer', 'customer_group',
               'staff', 'status')
CUE_ONLY_FILTERS = ('channel', 'prescription', 'active_ingredient')      # set by slots.apply_cues from fixed vocabulary, not shown in the LLM prompt
METRIC_DOC = {
    'revenue': 'doanh thu / bán được bao nhiêu tiền / thu về (filters: product, group, size, payment_method, shift, customer, customer_group, staff)',
    'order_count': 'số đơn / bao nhiêu bill (params.min_value: đơn có tiền hàng từ X trở lên; strict=true khi "trên X")',
    'cancelled_count': 'số đơn bị huỷ', 'cancel_rate': 'tỉ lệ % đơn huỷ',
    'avg_order_value': 'giá trị trung bình một đơn', 'quantity': 'bán được bao nhiêu <đơn vị> (filters.unit) / số ly size M (filters.size) / số cái của một mặt hàng',
    'unit_price': 'giá bán một đơn vị của mặt hàng vào ngày D (period day)',
    'top_products': 'mặt hàng bán chạy nhất / top k. "Bán chạy" = theo SỐ LƯỢNG (params.by=qty, mặc định); by=revenue chỉ khi hỏi "doanh thu/tiền cao nhất"; by=profit khi hỏi lãi; params.k (mặc định 1), params.order=asc cho bán chậm',
    'top_customers': 'khách mua nhiều tiền nhất / top k (params.by=revenue|orders)',
    'best_day': 'NGÀY NÀO trong kỳ bán được nhiều tiền / doanh thu cao nhất (trả về một ngày, không phải số tiền)',
    'products_min_orders': 'số mặt hàng có mặt ở ít nhất N đơn (params.threshold)',
    'customers_min_orders': 'số khách (hoặc % khách: params.as_percent) mua từ N đơn trở lên',
    'gross_profit': 'lãi gộp', 'net_profit': 'lãi ròng (lãi gộp trừ chi phí)',
    'expiring': 'hàng/lô hết hạn trong N ngày tới (params.days)', 'unsold_products': 'số mặt hàng ế (đã từng bán trước kỳ, trong kỳ không bán được)',
    'days_min_revenue': 'số ngày trong kỳ có doanh thu cả ngày từ X trở lên (params.min_value)', 'debt_total': 'tổng tiền khách còn nợ tính đến hết ngày (period as_of; params.min_age: nợ quá N ngày)',
    'debtor_count': 'số khách còn nợ', 'debt_table': 'bảng k khách nợ nhiều nhất (params.k)',
    'debt_aging': 'nợ theo nhóm tuổi 0–7, 8–15, trên 15 ngày (params.buckets)',
    'new_debt_and_repaid': 'nợ thêm và trả nợ trong kỳ (filters.customer; params.part=new|repaid khi chỉ hỏi một số)',
    'purchase_total': 'tổng tiền nhập hàng', 'top_supplier': 'nhà cung cấp nhập nhiều nhất',
    'avg_purchase_price': 'giá nhập bình quân (filters.product, params.unit)',
    'stock': 'tồn kho cuối ngày (period as_of; params.split_big_unit=true khi hỏi mấy thùng mấy lẻ)',
    'stock_value': 'giá trị hàng tồn kho theo giá vốn', 'purchase_minus_sales': 'số nhập trừ số bán',
    'price_effect': 'số lượng N ngày kể từ ngày tăng giá so với N ngày trước (params.date, params.days, params.new_price)',
}
SYSTEM = ('You turn a Vietnamese shop question into ONE JSON intent. Output JSON only:\n'
          '{"metric": str, "periods": [period...], "compare": null|"previous"|"same_period_last_year"|"explicit", '
          '"output": null|"pct"|"diff"|"increasing"|"argmax", "share_of_total": bool, "shift_compare": bool, '
          '"filters": {...}, "params": {...}, "answerable": true}\n'
          'Use "answerable": false when the shop data has no such information.\n'
          'compare/output stay null unless the question asks to compare (so với, tăng/giảm bao nhiêu %, chênh lệch).\n'
          '"hqua"/"hôm qua" = yesterday; "hnay"/"hôm nay" = today; "quý q/yyyy" = quarter, not month.\n'
          'Copy product / customer / group names exactly from the NAMES list.')
FEW_SHOT = [
    ('dthu thang 3/2026 tang hay giam bn % so voi thang truoc',
     {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 3, 'year': 2026}], 'compare': 'previous', 'output': 'pct'}),
    ('Tuần rồi bán được bao nhiêu ly Trà vải ABC (M)?',
     {'metric': 'quantity', 'periods': [{'type': 'last_week'}], 'filters': {'product': 'Trà vải ABC (M)'}}),
    ('tính đến hết ngày 05/04/2026, 3 khách nào nợ nhiều nhất, mỗi người còn nợ bao nhiêu',
     {'metric': 'debt_table', 'periods': [{'type': 'as_of', 'date': '2026-04-05'}], 'params': {'k': 3}}),
    ('Tháng 6/2026 nhóm bánh chiếm bao nhiêu % doanh thu?',
     {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 6, 'year': 2026}], 'filters': {'group': 'bánh'}, 'share_of_total': True}),
    ('doanh thu có tăng liên tục qua 3 tháng 4/2026, 5/2026, 6/2026 không',
     {'metric': 'revenue', 'periods': [{'type': 'month', 'month': m, 'year': 2026} for m in (4, 5, 6)], 'output': 'increasing'}),
    ('thang 2/2026 ngay nao ban dc nhieu tien nhat', {'metric': 'best_day', 'periods': [{'type': 'month', 'month': 2, 'year': 2026}]}),
    ('mặt hàng bán chạy nhất quý 1/2026 là gì', {'metric': 'top_products', 'periods': [{'type': 'quarter', 'quarter': 1, 'year': 2026}], 'params': {'k': 1, 'by': 'qty'}}),
    ('hqua bán được mấy bill', {'metric': 'order_count', 'periods': [{'type': 'yesterday'}]}),
    ('đến hết 10/03/2026 có bao nhiêu khách còn nợ', {'metric': 'debtor_count', 'periods': [{'type': 'as_of', 'date': '2026-03-10'}]}),
    ('so với cùng kỳ tháng trước, doanh thu từ đầu tháng tới nay tăng bao nhiêu %',
     {'metric': 'revenue', 'periods': [{'type': 'this_month'}], 'compare': 'previous', 'output': 'pct'}),
    ('liệt kê 4 khách mua nhiều tiền nhất tháng 1/2026', {'metric': 'top_customers', 'periods': [{'type': 'month', 'month': 1, 'year': 2026}], 'params': {'k': 4}}),
]


def build_messages(question, as_of, names: dict, normalized: str | None = None, tagged=None):
    names_txt = '\n'.join(f'{k}: {"; ".join(v[:80])}' for k, v in names.items() if v)
    metrics = '\n'.join(f'- {k}: {v}' for k, v in METRIC_DOC.items())
    shots = '\n'.join(f'Q: {q}\nJSON: {json.dumps(a, ensure_ascii=False)}' for q, a in FEW_SHOT)
    user = (f'METRICS:\n{metrics}\nPERIOD types: {", ".join(PERIOD_TYPES)}\nFILTER keys: {", ".join(FILTER_KEYS)}\n'
            f'NAMES:\n{names_txt}\nEXAMPLES (other shops):\n{shots}\n\n'
            f'today (as_of_date): {as_of}\nQ: {question}\n' + (f'(normalized: {normalized})\n' if normalized else '') + (f'(time expressions found by the date tagger: {json.dumps(tagged, ensure_ascii=False)})\n' if tagged else '') + 'JSON:')
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]


COMPACT_SYSTEM = ('Turn the Vietnamese shop question into ONE intent JSON (keys: metric, periods, compare, output, '
                  'share_of_total, shift_compare, filters, params, answerable). Omit keys that are null/false/empty. '
                  'Copy names exactly from NAMES. JSON only.')


def _trigrams(text):
    t = f'  {plain(text)}  '
    return {t[i:i + 3] for i in range(len(t) - 2)}


def relevant_names(question: str, names: dict, normalized: str | None = None, per_kind: int = 12,
                   always: int = 20) -> dict:
    """Names most likely mentioned by the question (char-trigram containment), so the prompt stays short.

    Short lists (groups, payment methods) are kept whole. Pure string similarity; no shop logic."""
    q = _trigrams(question) | (_trigrams(normalized) if normalized else set())
    out = {}
    for kind, pool in names.items():
        pool = [n for n in pool if n]
        if len(pool) <= always:
            out[kind] = pool
            continue
        scored = []
        for n in pool:
            g = _trigrams(n)
            scored.append((len(g & q) / max(len(g), 1), n))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out[kind] = [n for s, n in scored[:per_kind] if s > 0.2]
    return out


def build_compact_messages(question, as_of, names: dict, normalized: str | None = None, tagged=None):
    """Prompt for the LoRA-finetuned intent model: metric list + relevant names, no few-shot."""
    rel = relevant_names(question, names, normalized)
    names_txt = '\n'.join(f'{k}: {"; ".join(v)}' for k, v in rel.items() if v)
    metrics = '\n'.join(f'- {k}: {v}' for k, v in METRIC_DOC.items())
    user = (f'METRICS:\n{metrics}\nPERIOD types: {", ".join(PERIOD_TYPES)}\nFILTER keys: {", ".join(FILTER_KEYS)}\n'
            f'NAMES:\n{names_txt}\n\ntoday: {as_of}\nQ: {question}\n'
            + (f'(normalized: {normalized})\n' if normalized else '')
            + (f'(dates: {json.dumps(tagged, ensure_ascii=False)})\n' if tagged else '') + 'JSON:')
    return [{'role': 'system', 'content': COMPACT_SYSTEM}, {'role': 'user', 'content': user}]


INTENT_KEYS = ('metric', 'periods', 'compare', 'output', 'share_of_total', 'shift_compare', 'filters', 'params',
               'answerable')


def canonical_intent(intent: dict) -> dict:
    """Stable, minimal form of an intent (training target and equality checks)."""
    out = {}
    for k in INTENT_KEYS:
        v = intent.get(k)
        if k == 'answerable':
            if v is False:
                out[k] = False
            continue
        if v in (None, False, '', [], {}):
            continue
        if k in ('filters', 'params'):
            v = {kk: vv for kk, vv in sorted(v.items()) if vv not in (None, '', [], {}) and
                 not (k == 'params' and vv is False)}
            if not v:
                continue
        if k == 'periods':
            v = [{kk: vv for kk, vv in p.items() if vv is not None} for p in v if isinstance(p, dict)]
        out[k] = v
    return out


def parse_intent(text: str) -> dict | None:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S)
    decoder = json.JSONDecoder()
    for m in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and 'metric' in value:
            return value
    return None


def validate_intent(intent: dict, names: dict) -> list[str]:
    """Fixed checks; returns problems (empty = ok). Names are snapped to the shop's spelling."""
    problems = []
    if intent.get('answerable') is False:
        return []
    if intent.get('metric') not in METRICS:
        problems.append(f'unknown metric {intent.get("metric")!r}')
    periods = intent.get('periods') or []
    if not periods and intent.get('metric') not in NO_PERIOD:
        problems.append('missing period')
    for p in periods:
        if not isinstance(p, dict) or p.get('type') not in PERIOD_TYPES:
            problems.append(f'bad period {p!r}')
    filters = intent.setdefault('filters', {}) or {}
    for key in list(filters):
        if key not in FILTER_KEYS + CUE_ONLY_FILTERS:
            problems.append(f'unknown filter {key}')
            continue
        pool = names.get({'product': 'products', 'group': 'groups', 'customer': 'customers'}.get(key, ''), None)
        if pool and filters[key]:
            found = match_name(str(filters[key]), pool, 0.6)
            if found is None:
                problems.append(f'{key} {filters[key]!r} not in shop data')
            else:
                filters[key] = found
    if intent.get('compare') not in (None, 'previous', 'same_period_last_year', 'explicit'):
        problems.append('bad compare')
    return problems


def sanitize_intent(intent: dict) -> list[str]:
    """Fixed structural clean-up of LLM output (in place). Returns notes of what changed.

    Only fields that contradict the rest of the JSON are touched: comparison outputs without a
    comparison, an argmax over a single period (= best_day for revenue), null filters."""
    notes = []
    if not isinstance(intent, dict):
        return notes
    filters = intent.get('filters') or {}
    intent['filters'] = {k: v for k, v in filters.items() if v not in (None, '', [], {})}
    periods = intent.get('periods') or []
    out = intent.get('output')
    if out in ('diff', 'pct') and not intent.get('compare') and len(periods) < 2 and not intent.get('shift_compare'):
        intent['output'] = None
        notes.append(f'dropped output {out} without compare')
    if out in ('argmax', 'increasing') and len(periods) < 2:
        intent['output'] = None
        if out == 'argmax' and intent.get('metric') == 'revenue':
            intent['metric'] = 'best_day'
            notes.append('argmax of revenue inside one period -> best_day')
        else:
            notes.append(f'dropped output {out} with one period')
    return notes
