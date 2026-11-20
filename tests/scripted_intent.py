"""TEST-ONLY stand-in for the LLM intent step (GPU-free).

It plays the role the old OracleBackend played: it lets us measure the rule and
metric libraries against answers.jsonl without a GPU. It reads only the question
text, the as_of date and the names that exist in the shop; never ids. The production
path asks Qwen for the same JSON (datamate.intent.build_messages).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datamate.values import plain                               # noqa: E402

from datamate.normalize import ABBR, TELEX, TONE_TYPO, norm  # noqa: E402,F401


from datamate.timex import _months, periods_of  # noqa: E402,F401


def _k(text):
    return ' ' + ' '.join(re.findall(r'[a-z0-9]+(?:\.[0-9]+)?[a-z]*', plain(text))) + ' '


def find_name(q, names, min_len=4):
    best = None
    qk = _k(q)
    for n in names:
        p = _k(n).strip()
        if len(p) >= min_len and f' {p} ' in qk:
            if best is None or len(p) > len(plain(best)):
                best = n
    return best


def scripted_intent(question: str, as_of: str, names: dict) -> dict:
    vocab = {t for n in names.get('products', []) + names.get('customers', []) for t in re.findall(r'[a-z0-9]+', plain(n))}
    q = norm(question, vocab)
    periods = periods_of(q, as_of)
    f, params, it = {}, {}, {'periods': periods}
    product = find_name(q, names.get('products', []))
    if product:
        f['product'] = product
    grp = re.search(r'nhom (?:hang )?([a-z ]+?)(?: chiem| ban| la| thang| trong| co|$)', q)
    if grp and names.get('groups'):
        g = find_name(' ' + grp.group(1) + ' ', names['groups'], 2)
        if g:
            f['group'] = g
    for pm, key in (('chuyen khoan', 'chuyển khoản'), ('tien mat', 'tiền mặt'), ('cod', 'cod'),
                    ('vi dien tu', 'ví điện tử'), ('ghi no', 'ghi nợ')):
        if re.search(rf'\b{pm}\b', q) and re.search(r'tra bang|thanh toan|cac don|don tra|qua', q):
            f['payment_method'] = key
    shift_cmp = bool(re.search(r'ca chieu.*ca sang|ca sang.*ca chieu', q))
    if re.search(r'ca chieu', q) and not re.search(r'ca sang', q):
        f['shift'] = 'chieu'
    if re.search(r'ca sang', q) and not re.search(r'ca chieu', q):
        f['shift'] = 'sang'
    size = re.search(r'size ([ml])\b', q)
    if size:
        f['size'] = size.group(1).upper()
    cust = None
    if names.get('customers') and re.search(r'\bkhach\b', q):
        cust = find_name(q, names['customers'], 6)
    pct_word = bool(re.search(r'%|phan tram', q))

    def done(metric, **kw):
        it.update(metric=metric, filters=f, params=params, **kw)
        return it

    # ---- comparisons
    compare = None
    if re.search(r'tang hay giam|thay doi|tang truong|hon hay kem|chenh|so (?:voi|vs)|tang/giam', q) \
            and not re.search(r'ca chieu.*ca sang|ca sang.*ca chieu', q):
        if re.search(r'cung ky nam|nam (?:truoc|ngoai)', q):
            compare = 'same_period_last_year'
        elif len(periods) == 2:
            compare = 'explicit'
        else:
            compare = 'previous'
        if periods and periods[0]['type'] == 'tet':
            compare = 'previous'
    output = 'pct' if pct_word else ('diff' if compare else None)

    if re.search(r'tang gia|len gia|doi gia', q) and product and not re.search(r'het han', q):
        params['days'] = 7
        d = re.search(r'(\d{1,2})/(\d{1,2})/(20\d{2})', q)
        if d:
            params['date'] = f'{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}'
        n = re.search(r'(\d+) ngay (?:ke tu|dau|lien|tu)', q) or re.search(r'(\d+) ngay', q)
        if n:
            params['days'] = int(n.group(1))
        price = re.search(r'len (?:gia )?(\d[\d.,]*)', q)
        if price and not params.get('date'):
            params['new_price'] = float(re.sub(r'[.,]', '', price.group(1)))
        it['periods'] = []
        return done('price_effect')
    if shift_cmp:
        return done('order_count' if re.search(r'don|bill', q) else 'revenue', shift_compare=True)
    # ---- delivery rounds (rulebook "Giao nhiều đợt")
    if re.search(r'\bdot\b', q) and re.search(r'\bgiao\b|\bcho\b|\bxe\b', q):
        return done('delivery_batches')
    # ---- unsold / thresholds per day
    if re.search(r'(?:mat hang|mon|hang) e\b|bi e\b|khong ban (?:duoc|dc)|ko ban|k ban|chua ban', q) and re.search(r'mat hang|mon|san pham', q):
        return done('unsold_products')
    m = re.search(r'(?:so ngay|may ngay|bao nhieu ngay).*?(?:tu|tren) (\d[\d.,]*) (?:dong|d)', q)
    if m:
        params['min_value'] = float(re.sub(r'[.,]', '', m.group(1)))
        return done('days_min_revenue')
    # ---- debts
    if re.search(r'tuoi no|nhom tuoi', q):
        params['buckets'] = [7, 15]
        return done('debt_aging')
    if re.search(r'no them|ghi no them|tra no|tra bot no|thu no', q):
        cust = cust or find_name(q, names.get('customers', []), 6)
        if cust:
            f['customer'] = cust
        if re.search(r'no them', q) and re.search(r'tra (?:no )?(?:duoc|dc)', q):
            return done('new_debt_and_repaid')
        params['part'] = 'repaid' if re.search(r'tra bot no|tra no|thu no', q) else 'new'
        return done('new_debt_and_repaid')
    if re.search(r'\bno\b|cong no|thieu tien|con thieu|chua tra het|chua thu', q):
        if re.search(r'(\d+) khach nao|bang|khach nao .* nhieu nhat|nhieu nhat|lon nhat', q):
            k = re.search(r'(\d+) khach', q)
            params['k'] = int(k.group(1)) if k else 5
            return done('debt_table')
        if re.search(r'so khach|bao nhieu khach|may khach', q):
            return done('debtor_count')
        m = re.search(r'(?:qua|hon|tren) (\d+) ngay|tuoi qua (\d+)', q)
        if m:
            params['min_age'] = int(m.group(1) or m.group(2))
        return done('debt_total')
    # ---- stock / purchases
    if re.search(r'het han', q):
        return done('expiring')
    if re.search(r'khach (?:nu|nam)\b|gioi tinh', q):
        f['customer_group'] = 'nữ'
    m = re.search(r'nhom (?:khach )?(than thiet|vip|si|le|thuong)', q)
    if m and re.search(r'khach', q):
        f['customer_group'] = m.group(1)
    if re.search(r'gia tri (?:hang )?(?:con )?(?:ton|trong kho)|tien hang nam trong kho|nam trong kho|gia tri kho|hang con trong kho', q):
        return done('stock_value')
    if re.search(r'nhap tru|so nhap tru', q):
        return done('purchase_minus_sales')
    if re.search(r'gia nhap binh quan|gia nhap trung binh', q):
        u = re.search(r'mot (\w+)', q)
        if u:
            params['unit'] = u.group(1)
        return done('avg_purchase_price')
    if re.search(r'nha cung cap|ncc', q):
        return done('top_supplier')
    if re.search(r'nhap hang|tien nhap|phieu nhap|nhap vao|hang nhap', q):
        return done('purchase_total')
    if re.search(r'ton kho|trong kho|con lai|con may|con ton|kho con|ton (?:bao|bn)', q) and product:
        if re.search(r'chan.*le|thung.*le|hop.*le|may (?:thung|hop|loc)', q):
            params['split_big_unit'] = True
        if periods and periods[0]['type'] in ('day', 'today'):
            d = periods[0].get('date') or as_of
            it['periods'] = [{'type': 'as_of', 'date': d}]
        return done('stock')
    if re.search(r'tang gia|len gia|doi gia', q) and product:
        it['periods'] = []
        d = re.search(r'(\d{1,2})/(\d{1,2})/(20\d{2})', q)
        if d:
            params['date'] = f'{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}'
        n = re.search(r'(\d+) ngay (?:ke tu|dau|lien)', q) or re.search(r'(\d+) ngay', q)
        params['days'] = int(n.group(1)) if n else 7
        price = re.search(r'len (\d[\d.,]*)', q)
        if params.get('date'):
            price = None
        if price:
            params['new_price'] = float(re.sub(r'[.,]', '', price.group(1)))
        it['periods'] = []
        return done('price_effect')
    # ---- profit
    if re.search(r'loi nhat|lai gop cao nhat|lai nhat', q):
        params.update(by='profit', k=1)
        return done('top_products')
    if re.search(r'lai gop|loi gop|lai rong|loi nhuan', q):
        if re.search(r'lai rong|tru het chi phi', q):
            it['answerable'] = False
        return done('gross_profit')
    # ---- cancellations
    if re.search(r'\bhuy\b', q):
        if pct_word or re.search(r'ti le|ty le', q):
            return done('cancel_rate', compare=compare, output=output if compare else None)
        return done('cancelled_count')
    # ---- averages / argmax
    if re.search(r'trung binh|binh quan', q) and re.search(r'don|bill', q):
        return done('avg_order_value', compare=compare, output=output if compare else None)
    if re.search(r'ngay nao', q):
        return done('best_day')
    if re.search(r'thang nao', q) and len(periods) > 1:
        return done('revenue', output='argmax')
    if re.search(r'tang lien tuc', q):
        return done('revenue', output='increasing')
    # ---- customers
    if re.search(r'\bkhach\b', q) and re.search(r'tu (\d+) don|(\d+) don tro len|it nhat (\d+) don', q):
        m = re.search(r'tu (\d+) don|(\d+) don tro len|it nhat (\d+) don', q)
        params['threshold'] = int(m.group(1) or m.group(2) or m.group(3))
        params['as_percent'] = pct_word
        return done('customers_min_orders')
    if False:
        params['threshold'] = int(m.group(1) or m.group(2))
        params['as_percent'] = pct_word
        return done('customers_min_orders')
    if re.search(r'\bkhach\b|\bai\b', q) and re.search(r'nhieu tien|chi tieu|mua nhieu|tong tien mua|nhieu don|nhieu lan|mua nhieu nhat', q):
        k = re.search(r'(\d+) khach', q)
        params['k'] = int(k.group(1)) if k else 1
        if re.search(r'nhieu don|nhieu lan|so don', q):
            params['by'] = 'orders'
        params['as_list'] = bool(k)
        return done('top_customers')
    if re.search(r'nhan vien', q):
        it['answerable'] = False
        return done('revenue')
    # ---- products
    m = re.search(r'(?:it nhat|≥|>=|tu) (\d+) (?:don|bill)', q)
    if m and re.search(r'mat hang|san pham|mon', q):
        params['threshold'] = int(m.group(1))
        return done('products_min_orders')
    if re.search(r'chay nhat|ban nhieu nhat|hot nhat|ban duoc nhieu nhat|ban chay', q):
        k = re.search(r'top (\d+)|(?<![/\d])(\d{1,2}) (?:mat hang|san pham|mon|hang)', q)
        params['k'] = int(k.group(1) or k.group(2)) if k else 1
        params['as_list'] = bool(k)
        return done('top_products')
    if re.search(r'gia (?:bao nhieu|ban)|don gia|gia mot', q) and product and not re.search(r'thu ve|doanh thu', q):
        return done('unit_price')
    # ---- counts / quantities / revenue
    m = re.search(r'(?:tu|tren|dat) (\d[\d.,]*) (?:dong|d|vnd)', q)
    if m:
        params['min_value'] = float(re.sub(r'[.,]', '', m.group(1)))
        params['strict'] = q[m.start():m.start() + 3] == 'tre'
    counting = re.search(r'so don|bao nhieu don|may don|bill|don hang|bao nhieu hoa don', q)
    if counting and (not re.search(r'doanh thu|tien', q) or 'min_value' in params):
        return done('order_count', compare=compare, output=output if compare else None)
    unit = re.search(r'(?:bao nhieu|nhieu|may|so) (ly|cai|kg|chai|lon|goi|hop|vien|vi|phan(?! tram)|thung|bao|cay)\b', q)
    if unit:
        if not product and not f.get('size'):
            f['unit'] = {'ly': 'ly', 'cai': 'cái', 'kg': 'kg', 'chai': 'chai', 'lon': 'lon', 'goi': 'gói', 'hop': 'hộp',
                         'vien': 'viên', 'vi': 'vỉ', 'phan': 'phần', 'thung': 'thùng', 'bao': 'bao', 'cay': 'cây'}[unit.group(1)]
        return done('quantity', compare=compare, output=output if compare else None)
    share = bool(pct_word and re.search(r'chiem|ti trong', q))
    if len(periods) > 1 and not compare:
        return done('revenue')
    return done('revenue', compare=compare, output=output if compare else None, share_of_total=share)
