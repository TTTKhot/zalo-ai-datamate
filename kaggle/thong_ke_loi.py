"""Error / abstain statistics of a public replay against the ChatGPT reference (measuring stick, NOT gold).

python kaggle/thong_ke_loi.py <replay.jsonl (raw, before guards)> <final.jsonl (Docker order)> [--md out.md]

<replay>.reasons.jsonl (written by kaggle/replay_public.py) must sit next to the raw replay. Shops held out from error
reading (dev_001, dev_007, dev_009, dev_010) appear only as one aggregated row, never per question.
Wrong answers are split into layers by an AUTOMATIC heuristic (metric vs reference kind, period vs reference period,
filter keys vs reference filters, size of the numeric gap) -> counts are an estimate, examples show the rule.
Never used by the Docker image; never used to fit anything.
"""
import collections
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.periods import Calendar, resolve      # noqa: E402
from datamate.scoring import is_correct             # noqa: E402

SPLIT = ROOT / 'public_test' / 'public_test'
REF = ROOT / 'runs' / 'tham_chieu_gpt' / 'tham_chieu_day_du_co_tin_cay.jsonl'
KINDS = ROOT / 'runs' / 'tham_chieu_gpt' / 'phan_ra.json'
HELD = {'dev_001', 'dev_007', 'dev_009', 'dev_010'}
HELD_ROW = '4 shop giữ kín'

# reference kind -> metrics of datamate/metrics.py that answer it; None = no computation for it in the library
KIND_METRICS = {
    'revenue': {'revenue'}, 'orders': {'order_count'}, 'quantity': {'quantity'}, 'avg_order': {'avg_order_value'},
    'customers_threshold': {'customers_min_orders'}, 'top_products': {'top_products'},
    'debt': {'debt_total', 'debtor_count', 'debt_table', 'debt_aging'}, 'cancel_count': {'cancelled_count'},
    'price_effect': {'price_effect'}, 'cancel_rate': {'cancel_rate'}, 'days_threshold': {'days_min_revenue'},
    'best_day': {'best_day'}, 'busiest_day': {'best_day'}, 'top_customer_orders': {'top_customers'},
    'top_customers': {'top_customers'}, 'loyal': {'top_customers'}, 'vip': {'top_customers'},
    'products_orders_threshold': {'products_min_orders'}, 'repaid': {'new_debt_and_repaid'},
    'new_and_repaid': {'new_debt_and_repaid'}, 'top_profit': {'top_products', 'gross_profit'},
    'purchase': {'purchase_total'}, 'gross_profit': {'gross_profit'}, 'stock': {'stock', 'stock_value'},
    'expiry': {'expiring'}, 'near_expiry': {'expiring'}, 'purchase_minus_sales': {'purchase_minus_sales'},
    'idle': {'unsold_products'}, 'net_profit': {'net_profit'}, 'supplier_amount': {'top_supplier'},
    'supplier_count': {'top_supplier'}, 'model_top': {'top_products'}, 'top_brand': {'top_products'},
    'popular': {'top_products'},
    # no computation in the library
    'orders_threshold': {'order_count'}, 'service': None, 'installment': None, 'payable': None, 'delivery': None,
    'adjustment': None, 'trade': None, 'trade_share': None, 'deadline': None, 'warranty': None, 'top_staff': None,
    'brand_share': None, 'peak_hour': None, 'avg_machine': None, 'cancel_customer': None, 'new_members': None,
    'purchase_qty': None, 'missing': None,
}


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8-sig').splitlines() if l.strip()]


def abstain_cause(raw_type, reason, blocked):
    if blocked and raw_type not in ('abstain',):
        return 'chặn cả shop (guard >20% unanswerable)'
    if raw_type == 'unanswerable':
        return 'unanswerable → bỏ trống'
    r = str(reason or '')
    if not r:
        return 'không có log'
    if re.match(r'^[A-Z]\w*(Error|Exception)\b', r):
        return 'lỗi code (exception)'
    if 'not implemented' in r or r.startswith(('unknown metric', 'unknown filter')):
        return 'phép tính / bộ lọc chưa có'
    if 'not found' in r or 'not in shop data' in r or r.startswith(('unknown status', 'unknown shift')):
        return 'giá trị lọc không khớp dữ liệu'
    if r in ('no intent', 'no period') or 'intent' in r:
        return 'không hiểu câu (intent rỗng/sai)'
    return 'khác: ' + r[:40]


def ref_period(note):
    m = re.search(r'kỳ (\d{4}-\d{2}-\d{2}) đến (\d{4}-\d{2}-\d{2})', note or '')
    return (m.group(1), m.group(2)) if m else None


def ref_filters(note):
    m = re.search(r'bộ lọc (\{.*?\})', note or '')
    try:
        return set(json.loads(m.group(1))) if m else None
    except Exception:
        return None


def our_period(intent, as_of, cal):
    from datetime import date, timedelta
    ps = (intent or {}).get('periods') or []
    if len(ps) != 1:
        return None
    try:
        p = resolve(ps[0], date.fromisoformat(as_of), cal)
        return (p.start.isoformat(), (p.end - timedelta(days=1)).isoformat())
    except Exception:
        return None


def as_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list) and len(v) == 1:
        return as_num(v[0])
    return None


def wrong_layer(q, ref, kind, rs, cal):
    intent = rs.get('intent') or {}
    ours = intent.get('metric')
    want = KIND_METRICS.get(kind, 'unknown')
    if ref.get('type') == 'unanswerable':
        return 'tham chiếu: không trả lời được (ta trả lời)'
    if want is None:
        return 'phép tính không có trong thư viện (kind)'
    if want != 'unknown' and ours not in want:
        return 'hiểu câu: metric'
    rp, op = ref_period(ref.get('note')), our_period(intent, q['as_of_date'], cal)
    if rp and op and rp != op:
        return 'hiểu câu: kỳ'
    rf = ref_filters(ref.get('note'))
    of = {k for k, v in (intent.get('filters') or {}).items() if v not in (None, '', [], {})}
    if rf is not None and rf != of:
        return 'hiểu câu: bộ lọc'
    a, b = as_num(rs.get('answer')), as_num(ref.get('answer'))
    if a is not None and b:
        return 'tính/định nghĩa (lệch ≤ 15%)' if abs(a - b) / abs(b) <= 0.15 else 'đọc dữ liệu/ánh xạ hoặc định nghĩa (lệch > 15%)'
    return 'kiểu đáp án / danh sách / chữ khác'


def table(rows, head):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows]
    return '\n'.join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    raw_path, final_path = Path(args[0]), Path(args[1])
    md_out = sys.argv[sys.argv.index('--md') + 1] if '--md' in sys.argv else None
    qs = load(SPLIT / 'questions.jsonl')
    cal = Calendar(SPLIT / 'calendar.csv')
    ref = {r['id']: r for r in load(REF)}
    kind = {x['id']: x['kind'] for x in json.loads(KINDS.read_text(encoding='utf-8'))}
    raw = {r['id']: r for r in load(raw_path)}
    final = {r['id']: r for r in load(final_path)}
    reasons = {r['id']: r for r in load(raw_path.with_suffix('.reasons.jsonl'))}
    # shops blocked = shops where the final file abstains on answers the raw replay gave (not unanswerable)
    blocked = {q['business_id'] for q in qs
               if final[q['id']]['type'] == 'abstain' and raw.get(q['id'], {}).get('type') not in (None, 'abstain', 'unanswerable')}

    def row_of(biz):
        return HELD_ROW if biz in HELD else biz

    def ok(r, qid):
        try:
            return bool(is_correct(r, ref[qid]))
        except Exception:
            return False

    tot = collections.Counter()
    per_shop = collections.defaultdict(collections.Counter)
    causes = collections.defaultdict(collections.Counter)            # cause -> shop row -> n
    cause_ref = collections.defaultdict(collections.Counter)         # cause -> 'ref has answer' / 'ref unanswerable'
    abst_kind = collections.defaultdict(collections.Counter)         # kind -> cause -> n (non-held)
    kind_status = collections.defaultdict(collections.Counter)       # kind -> khớp/khác/bỏ trống (all shops)
    would = collections.defaultdict(collections.Counter)             # blocked shop -> khớp/khác if unblocked
    layers = collections.Counter()
    layer_held = 0
    examples = collections.defaultdict(list)
    for q in qs:
        qid, biz = q['id'], q['business_id']
        f, rr, rs = final[qid], raw.get(qid, {'type': 'abstain'}), reasons.get(qid, {})
        k = kind.get(qid, '?')
        if f['type'] == 'abstain':
            c = abstain_cause(rr['type'], rs.get('reason'), biz in blocked)
            st = 'bỏ trống'
            causes[c][row_of(biz)] += 1
            cause_ref[c]['tham chiếu có đáp án' if ref[qid]['type'] != 'unanswerable' else 'tham chiếu: unanswerable'] += 1
            if biz not in HELD:
                abst_kind[k][c] += 1
            if c.startswith('chặn cả shop'):
                would[biz]['khớp' if ok(rr, qid) else 'khác'] += 1
        else:
            st = 'khớp' if ok(f, qid) else 'khác'
            if st == 'khác':
                if biz in HELD:
                    layer_held += 1
                else:
                    lay = wrong_layer(q, ref[qid], k, rs, cal)
                    layers[lay] += 1
                    if len(examples[lay]) < 2:
                        examples[lay].append(f"{biz} [{k}/{(rs.get('intent') or {}).get('metric')}] "
                                             f"«{q['question'][:70]}» ta={str(f.get('answer'))[:30]} "
                                             f"tc={str(ref[qid].get('answer'))[:30]}")
        tot[st] += 1
        per_shop[row_of(biz)][st] += 1
        if biz not in HELD:
            kind_status[k][st] += 1
    n = len(qs)
    md = []
    sc = (tot['khớp'] - tot['khác']) / n
    md.append(f"## Tổng ({final_path.name}, {n} câu)\n")
    md.append(table([[tot['khớp'] + tot['khác'], tot['bỏ trống'], tot['khớp'], tot['khác'], f'{sc:+.3f}', f'{sc + 0.05:+.3f}']],
                    ['trả lời', 'bỏ trống', 'khớp tc', 'khác tc', 'điểm tc', 'ước LB (tc+0,05)']))
    md.append('\n### Theo shop\n')
    rows = []
    for s in sorted(per_shop):
        c = per_shop[s]
        rows.append([s, c['khớp'], c['khác'], c['bỏ trống'], f"{(c['khớp'] - c['khác']) / n:+.3f}",
                     'chặn cả shop' if s in blocked else ''])
    md.append(table(rows, ['shop', 'khớp', 'khác', 'bỏ trống', 'góp điểm', 'ghi chú']))

    md.append('\n## Câu BỎ TRỐNG theo nguyên nhân × shop\n')
    shops = sorted({s for c in causes.values() for s in c})
    rows = []
    for c in sorted(causes, key=lambda c: -sum(causes[c].values())):
        rows.append([c, sum(causes[c].values()), cause_ref[c]['tham chiếu có đáp án'],
                     ', '.join(f'{s}:{causes[c][s]}' for s in shops if causes[c][s])])
    md.append(table(rows, ['nguyên nhân', 'câu', 'tc có đáp án (lấy lại được)', 'theo shop']))
    if would:
        md.append('\n### Shop bị chặn: nếu bỏ chặn (câu đã có đáp án số của pipeline, so tham chiếu)\n')
        md.append(table([[s, would[s]['khớp'], would[s]['khác'], f"{(would[s]['khớp'] - would[s]['khác']) / n:+.3f}"]
                         for s in sorted(would)], ['shop', 'khớp', 'khác', 'đổi điểm nếu bỏ chặn']))
    md.append('\n### Bỏ trống theo loại câu (kind của tham chiếu), 20 shop không giữ kín — top 25\n')
    cause_names = sorted(causes, key=lambda c: -sum(causes[c].values()))
    short = {c: c.split(' (')[0].split(':')[0][:22] for c in cause_names}
    rows = []
    for k in sorted(abst_kind, key=lambda k: -sum(abst_kind[k].values()))[:25]:
        rows.append([k, 'có' if KIND_METRICS.get(k) else ('KHÔNG' if k in KIND_METRICS else '?'),
                     sum(abst_kind[k].values())] + [abst_kind[k][c] or '' for c in cause_names])
    md.append(table(rows, ['kind', 'thư viện', 'bỏ trống'] + [short[c] for c in cause_names]))

    md.append('\n## Câu SAI (khác tham chiếu) theo tầng — phân loại tự động\n')
    rows = [[lay, v, ' ; '.join(examples[lay])] for lay, v in layers.most_common()]
    rows.append([HELD_ROW + ' (không phân loại)', layer_held, ''])
    md.append(table(rows, ['tầng', 'câu', 'ví dụ (shop [kind/metric ta] câu, ta, tc)']))

    md.append('\n## Loại câu tham chiếu có mà thư viện `metrics.py` KHÔNG có (20 shop không giữ kín, chỉ đếm)\n')
    rows = []
    for k in sorted((k for k in kind_status if KIND_METRICS.get(k, 'x') is None), key=lambda k: -sum(kind_status[k].values())):
        c = kind_status[k]
        rows.append([k, sum(c.values()), c['khớp'], c['khác'], c['bỏ trống']])
    md.append(table(rows, ['kind', 'câu', 'khớp', 'khác', 'bỏ trống']))
    md.append('\n## Mọi loại câu (20 shop không giữ kín): khớp / khác / bỏ trống\n')
    rows = [[k, 'có' if KIND_METRICS.get(k) else ('KHÔNG' if k in KIND_METRICS else '?'), sum(c.values()), c['khớp'], c['khác'],
             c['bỏ trống']] for k, c in sorted(kind_status.items(), key=lambda kv: -sum(kv[1].values()))]
    md.append(table(rows, ['kind', 'thư viện', 'câu', 'khớp', 'khác', 'bỏ trống']))
    text = '\n'.join(md) + '\n'
    if md_out:
        Path(md_out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
