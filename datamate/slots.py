"""Fixed post-processing of the LLM intent (structural + generic Vietnamese cue words).

Two kinds of repair, both independent of question ids and shops:

1. normalize_params - the LLM put a value under another key or in another format
   (filters.params, min_value vs threshold, buckets as strings, date of a price change
   written in periods). Purely structural; the meaning is unchanged.

2. apply_cues - a small cue tagger over the accent-free question for slots the 4B model
   gets wrong systematically on train: whether the question compares at all, which
   comparison ("cùng kỳ tháng trước" = previous period, "cùng kỳ năm trước" = last year),
   top-k size, ranking key ("bán chạy" = quantity), morning/afternoon shift.
   These are reading rules of the rulebook vocabulary, the same for every shop. They are
   the slots a LoRA-finetuned intent model should learn; until then they guard the LLM.

Every change is reported so calibration can learn how much to trust repaired intents.
"""
from __future__ import annotations

import re

COMPARE_CUE = re.compile(r'so (?:voi|vs)|tang hay giam|tang giam|chenh|hon hay kem|nhieu hay it|thay doi|'
                         r'cung ky|ky truoc|tang bao nhieu|giam bao nhieu|tang them|giam di|'
                         r'tang truong|so sanh|bien dong|tang len|giam xuong|sut giam|giam sut|'
                         r'gap (?:may|bao nhieu|\d+(?:[.,]\d+)?) lan|len hay xuong|cao hay thap|'
                         r'\bso (?:doi |sv )?(?:cung ky )?(?:thang|tuan|nam|quy|ky) (?:truoc|roi|ngoai|trc)\b')
LAST_YEAR_CUE = re.compile(r'cung ky nam (?:truoc|ngoai|roi)|nam (?:truoc|ngoai) cung ky|cung thoi gian nam')
PREVIOUS_CUE = re.compile(r'cung ky thang (?:truoc|roi)|thang (?:truoc|roi)|tuan (?:truoc|roi)|truoc tet|ngay (?:truoc|lien truoc)|'
                          r'quy (?:truoc|roi)|ky truoc')
TOPK = re.compile(r'(?:top|liet ke|cho biet)?\s*(\d{1,2}) (?:khach|mat hang|hang|san pham|mon|mau|nguoi)')
TOPK2 = re.compile(r'top (\d{1,2})')
# a number right after a time / count word is a period or an amount ("tháng 5 khách nào...", "quý 2 mặt hàng..."), not k
NOT_K_BEFORE = re.compile(r'\b(?:thang|quy|tuan|nam|ngay|hom|t|q|ca|lan|tet|tu|den|so|ma|don|lo)\s*$')
# ranking key of top_products: only overwrite the LLM when the question says which one (rulebook: bán chạy = số lượng)
TOP_BY_PROFIT = re.compile(r'\blai\b|loi nhuan|\bloi\b')
TOP_BY_REVENUE = re.compile(r'doanh thu|doanh so|\bdthu\b|nhieu tien|thu ve|tien nhat|tien ban|gia tri')
TOP_BY_QTY = re.compile(r'ban chay|ban nhieu|ban duoc nhieu|ban ra nhieu|hot nhat|so luong|\bsl\b')
# rulebook terms for "which customer": "trung thành nhất", "sộp nhất" ("sốp" alone is slang for the shop)
CUSTOMER_LOYAL = re.compile(r'\btrung thanh nhat\b|\bkhach(?: hang)? (?:\w+ )?trung thanh\b')
CUSTOMER_BIG = re.compile(r'\bkhach(?: hang)? (?:\w+ )?sop\b|\bsop nhat\b')
# a judgement of a person / supplier the rulebook does not define ("khách khó tính nhất", "NCC uy tín", "thợ nhiệt
# tình nhất", "nhân viên có tận tâm không"): the data cannot answer it (train gold: unanswerable) -> abstain.
# Only with a ranking / person / yes-no context ("trong kho tính theo giá vốn" is not "khó tính").
SUBJECTIVE = (r'kho tinh|de tinh|trung thuc|uy tin|nhiet tinh|than thien|vui ve|de thuong|tot bung|chu dao|dang tin'
              r'|tan tam|tan tuy|le phep|lich su|hao phong|keo kiet|kho chieu|cau ky|thong minh|chuyen nghiep'
              r'|nhanh nhen|kho ua|de chiu|vui tinh|hien lanh|ky tinh')
SUBJECTIVE_ASK = re.compile(
    rf'\b(?:{SUBJECTIVE})\b(?:\s+\w+){{0,2}}\s+nhat\b'
    rf'|\b(?:ncc|nha cung cap|khach(?: hang)?|nhan vien|tho|ban)\b(?:\s+\w+){{0,3}}\s+(?:{SUBJECTIVE})\b'
    rf'|\bco\s+(?:\w+\s+){{0,2}}(?:{SUBJECTIVE})\b')
CUSTOMER_FICKLE = re.compile(r'\bhay doi y\b|\bdoi y nhieu nhat\b')
PRODUCT_FAVOURED = re.compile(r'\b(?:duoc )?ua chuong nhat\b')
DAY_BUSY = re.compile(r'\bngay\b.*\bdat khach nhat\b|\bdat khach nhat\b.*\bngay\b')
PEAK_HOUR = re.compile(r'\bgio cao diem\b')


def top_k(q: str):
    """k named in the question, or None."""
    m = TOPK2.search(q)
    if m:
        return int(m.group(1))
    for m in TOPK.finditer(q):
        if not NOT_K_BEFORE.search(q[:m.start(1)]):
            return int(m.group(1))
    return None


def _num(v):
    m = re.search(r'\d+(?:[.,]\d+)?', str(v))
    return float(m.group().replace(',', '.')) if m else None


_MIN_ORDERS = ('threshold', 'min_orders', 'min_value', 'n', 'count', 'min', 'strict', 'as_percent')
MISPLACED_PARAMS = {'order_count': ('min_value', 'strict'), 'days_min_revenue': ('min_value', 'strict'),
                    'customers_min_orders': _MIN_ORDERS, 'products_min_orders': _MIN_ORDERS, 'debt_total': ('min_age',)}
RANGE_ALIASES = {'start': ('start_date', 'from', 'date_from', 'begin'), 'end': ('end_date', 'to', 'date_to', 'until')}


def normalize_params(intent: dict) -> list[str]:
    notes = []
    params = intent.get('params')
    if not isinstance(params, dict):
        params = intent['params'] = {}
    filters = intent.get('filters') or {}
    if isinstance(filters.get('params'), dict):
        params.update({k: v for k, v in filters.pop('params').items() if k not in params})
        notes.append('moved filters.params -> params')
    metric = intent.get('metric')
    # the LLM often writes a threshold next to the filters ({"filters": {"min_value": 500000}}). It is the same
    # request with the key one level off: move it, but only for a metric that really uses that key - for any other
    # metric it stays an unknown filter (abstain), never a silently ignored condition.
    for key in MISPLACED_PARAMS.get(metric, ()):
        if key in filters and not isinstance(filters[key], (dict, list)):
            value = filters.pop(key)
            if params.get(key) is None:
                params[key] = value
            notes.append(f'moved filters.{key} -> params')
    for p in intent.get('periods') or []:              # a range written with other key names
        if isinstance(p, dict) and p.get('type') == 'range':
            for want, alts in RANGE_ALIASES.items():
                alt = next((a for a in alts if p.get(a)), None)
                if not p.get(want) and alt:
                    p[want] = p.pop(alt)
                    notes.append(f'period.{alt} -> {want}')
    if metric in ('customers_min_orders', 'products_min_orders') and 'threshold' not in params:
        for alt in ('min_orders', 'min_value', 'n', 'count', 'min'):
            if params.get(alt) is not None:
                params['threshold'] = _num(params.pop(alt))
                notes.append(f'params.{alt} -> threshold')
                break
    if metric == 'debt_aging' and params.get('buckets') and not all(isinstance(b, (int, float)) for b in params['buckets']):
        edges = set()
        for b in params['buckets']:
            nums = [int(x) for x in re.findall(r'\d+', str(b))]
            if nums:
                edges.add(nums[-1] if len(nums) > 1 else nums[0])
        params['buckets'] = sorted(e for e in edges if e > 0)
        notes.append(f'buckets -> {params["buckets"]}')
    if metric == 'price_effect' and not params.get('date'):
        cand = params.pop('compare_date', None) or next(
            (p.get('date') for p in intent.get('periods') or [] if isinstance(p, dict) and p.get('date')), None)
        if cand:
            params['date'] = cand
            notes.append('price_effect date from periods')
    if intent.get('shift_compare'):
        if intent.get('compare') or (filters or {}).get('shift'):
            notes.append('shift_compare: dropped period compare / shift filter')
        intent['compare'] = None
        filters.pop('shift', None)
        periods = [{k: v for k, v in p.items() if k != 'shift'} for p in intent.get('periods') or [] if isinstance(p, dict)]
        intent['periods'] = periods[:1]
    intent['filters'] = filters
    return notes


STATUS_SAID = {'hoàn thành': re.compile(r'hoan thanh|hoan tat|thanh cong|\bxong\b|\bda giao\b|giao xong'),
               'huỷ': re.compile(r'\bhuy\b|\bbom\b|cancel'),
               'trả hàng': re.compile(r'\btra\b|\bhoan\b|return|refund'),
               'đang giao': re.compile(r'dang giao|chua giao|van chuyen|dang xu ly|\bcho\b')}
ORDER_LEVEL_METRICS = ('revenue', 'order_count', 'avg_order_value', 'quantity', 'cancel_rate', 'cancelled_count')
CHANNEL_CUES = [('zalo', re.compile(r'\b(?:qua|ben|tren|kenh) zalo\b|\bzalo oa\b')),
                ('phone', re.compile(r'\b(?:qua|bang|dat qua|goi) dien thoai\b|\bdat hang qua dien thoai\b')),
                ('facebook', re.compile(r'\b(?:qua|tren|kenh) (?:facebook|fb|messenger)\b')),
                ('store', re.compile(r'\b(?:ban|mua|don) tai quay\b|\btai quay\b'))]
PAYMENT_CUES = [('cash', re.compile(r'\btien mat\b|\b(?:tra|thanh toan|bang) (?:bang )?tm\b')),
                ('transfer', re.compile(r'\bchuyen khoan\b|\b(?:tra|thanh toan|bang) (?:bang )?ck\b')),
                ('ewallet', re.compile(r'\bvi dien tu\b|\bmomo\b|\bzalopay\b|\bvnpay\b'))]


# two values of one dimension named in the question ("COD và tiền mặt mỗi loại bao nhiêu", "tại quầy bao nhiêu, qua điện
# thoại bao nhiêu"): one number per value, in the order of the question; not for comparisons / shares
COD_CUE = ('cod', re.compile(r'\bcod\b|\bxi o di\b|\bthu ho\b'))
SPLIT_BLOCK = re.compile(r'%|phan tram|chenh|hon bao nhieu|kem bao nhieu|\bgap\b|chiem|ti trong|ty trong|tang|giam')


def named_values(q: str, cues) -> list:
    hits = sorted((m.start(), c) for c, rx in cues for m in [rx.search(q)] if m)
    out = []
    for _, c in hits:
        if c not in out:
            out.append(c)
    return out


NON_RX_CUE =re.compile(r'\b(?:khong|hong|hok|ko|k|kg|chua) (?:can )?ke don\b|\b(?:tru|ngoai|bo) (?:cac )?(?:thuoc|hang|mat hang) ke don\b')
RX_CUE = re.compile(r'\bke don\b')
ACTIVE_CUE = re.compile(r'\bhoat chat ([a-z0-9]+(?:(?: \+ | )[a-z0-9]+)*?)(?= (?:thang|tuan|nam|hom|ngay|quy|tu|trong|ban|tinh|'
                        r'den|da|duoc|chiem|thu|cua|o|tai|dau|la|nay|qua|vua|gan|cuoi|tong|co|a|nhi|nguoi|nen|uong)\b|\s*$)')


def plain_text(v) -> str:
    from .values import plain
    return plain(str(v))


CUE_GROUPS = ('compare_drop', 'compare_kind', 'topk', 'strict', 'top_by', 'status', 'channel_payment', 'pharmacy', 'shift',
              'price_effect', 'expiry', 'what_counted', 'ground', 'compare_add', 'split', 'delivery', 'service')
# rulebook §5 "hiệu ứng tăng giá": units sold in the N days from the price change vs the N days before it
PRICE_CHANGE_CUE = re.compile(r'\b(?:tang|len|doi|dieu chinh|nang) gia\b')
PRICE_WINDOW_CUE = re.compile(r'\b(\d{1,3}) ngay\b')
PRICE_BEFORE_CUE = re.compile(r'\btruoc\b')
PRICE_DATE_SAID = re.compile(r'\b\d{1,2}[/-]\d{1,2}\b|\bngay \d{1,2}\b|\d{4}-\d{2}-\d{2}')
EXPIRY_CUE = re.compile(r'\bhet han\b|\bhan (?:su )?dung\b|\bhsd\b|\bcan date\b')
# which quantity the question counts, on positive evidence only (abbreviations: đh = đơn hàng, bq = bình quân)
ORDER_NOUN = r'(?:don|dh|don hang|hoa don|bill)'
MONEY_WORDS = re.compile(r'doanh thu|doanh so|\bdthu\b|\btien\b|gia tri|binh quan|bin quan|\bbq\b|trung binh|trung bih|\btb\b')
COUNT_ORDERS_CUE = re.compile(rf'\b(?:so|bao nhieu|may|tong so|tong bao nhieu) {ORDER_NOUN}\b')
AVG_WORDS = re.compile(r'binh quan|bin quan|\bbq\b|trung binh|trung bih|\btb\b')
PER_ORDER_CUE = re.compile(rf'\b(?:moi|1|mot|tren 1|tren moi) {ORDER_NOUN}\b')
GROSS_PROFIT_CUE = re.compile(r'\blai gop\b|\bloi nhuan gop\b')
COUNT_UNITS_CUE = re.compile(r'\b(?:may|bao nhieu) (?:dia|ly|coc|chai|lon|hop|goi|phan|to|vien|tuyp|thung|chiec|cay|bich|kg)\b')
REPAID_CUE = re.compile(r'\btra (?:bot )?no\b|\bthu (?:duoc )?(?:tien )?no\b|\bdoi (?:duoc )?(?:bao nhieu )?(?:tien )?no\b')
# a filter must have a ground in the question: the model copies names from the shop list or invents a value
GROUND_KEYS = ('product', 'customer', 'staff', 'customer_group', 'group')
GROUND_GENERIC = {'tiem', 'quan', 'shop', 'cua', 'hang', 'z', 'khach', 'nhom', 'cac', 'don', 'ca', 'nv', 'nhan', 'vien',
                  'san', 'pham', 'sp', 'mon', 'mat', 'loai', 'the', 'va', 'cua', 'cho'}
CODE_TOKEN = re.compile(r'\b[a-z]{1,4}\d{2,}\b')
PAYMENT_ANY = re.compile(r'thanh toan|\btra\b|chuyen khoan|\bck\b|tien mat|\btm\b|\bthe\b|\bvi\b|momo|zalo ?pay|vnpay|\bcod\b|'
                         r'xi o di|\bqr\b|quet ma|ngan hang|\bbank|\bno\b|\bchiu\b|\bthieu\b|ghi so|tra sau|cash|transfer')
SHIFT_SAID = re.compile(r'\b(?:ca|buoi) (?:sang|chieu)\b')
CHANNEL_ANY = re.compile(r'zalo|dien thoai|facebook|\bfb\b|messenger|shopee|grab|tai quay|online|offline|truc tiep|kenh|'
                         r'\bapp\b|\bweb|hotline|\bgoi\b|lazada|tiktok|tai cho')
NO_VALUE = {'all', 'any', 'none', 'tat ca', 'null', 'khong'}


def _grounded(value, q: str, need=0.5) -> bool:
    toks = [t for t in plain_text(value).split() if t not in GROUND_GENERIC]
    if not toks:
        return False
    words = set(q.split())
    return sum(t in words for t in toks) / len(toks) >= need


COMPARE_ADD_CUE = re.compile(r'\bso (?:voi |vs |doi |sv )?(?:cung ky )?(?:thang|tuan|nam|quy|ky) (?:truoc|roi|ngoai|trc)\b|'
                             r'\b(?:len|tang) hay (?:xuong|giam)\b|\bcao hay thap\b')
PCT_CUE = re.compile(r'%|phan tram')
WHICH_ITEM_CUE = re.compile(r'\b(?:sp|san pham|hang|mon|mat hang)\b (?:nao|mo|gi)\b')
NEW_DEBT_CUE = re.compile(r'\bno them\b')
# rulebook "Giao nhiều đợt": the question counts delivery rounds ("mấy đợt giao", "đếm số đợt", "chở bao nhiêu đợt
# hàng"); "đơn được giao từ 2 đợt trở lên" counts orders by rounds (not defined in the rulebook -> min_batches, abstain)
DELIVERY_COUNT_CUE = re.compile(r'\b(?:may|bao nhieu|bn|so|dem|tong cong|total)\b[^.?]{0,25}\bdot\b')
DELIVERY_CONTEXT = re.compile(r'\bgiao\b|\bcho\b|\bxe\b|\bdot hang\b')
DELIVERY_MIN_CUE = re.compile(r'\b(?:tu|tren|it nhat) (\d+) dot\b|\b(\d+) dot tro len\b|\bthanh (\d+) dot\b')
# service shops (rulebook "Sửa xe"): tickets / visits, workers' commission, warranty tickets, distinct vehicles.
# The metrics answer only on a service book (else abstain), so the cues need words no sales question uses.
SVC_COUNT = r'\b(?:bao nhieu|bn|may|mi|nhieu|dem|so)\b'
SVC_TICKET = re.compile(r'\b(?:luot xe|nuot xe|luot|nuot|phieu sua(?: xe)?|phieu)\b(?! (?:nhap|thu|chi|xuat))')
SVC_MONEY = re.compile(r'doanh thu|doanh so|\bdthu\b|\btien\b|\bgia tri\b')
SVC_COMMISSION = re.compile(r'\b(?:hoa|hue) hong\b')
SVC_WORKER = re.compile(r'\btho\b')
SVC_WHICH_WORKER = re.compile(r'\btho (?:mo|nao)\b|\bai\b|\btho\b[^?]{0,40}\bla ai\b')
SVC_ALL_WORKERS = re.compile(r'\bbang\b|\btung tho\b|\bmoi tho\b|\bcac tho\b|\btat ca tho\b|\bxep\b')
SVC_TOP = re.compile(r'\bnhat\b|\bnhut\b')
SVC_DAYS = re.compile(r'\bcham chi\b|\bsieng\b|\bsieng nang\b|\bnhieu ngay\b')
SVC_WARRANTY = re.compile(r'\bbao hanh\b')
SVC_RATE = re.compile(r'%|phan tram|\bti le\b|\bty le\b|\bchiem\b')
SVC_DISTINCT_VEHICLES = re.compile(r'\bxe\b[^?]{0,40}\bkhac nhau\b|\bmoi xe tinh (?:mot|1) lan\b|\bchiec\b[^?]{0,30}\bkhac nhau\b')
SVC_REPEAT = re.compile(r'\b(?:tu|it nhat) (\d) lan\b|\bkhach quen\b')
PRICE_EFFECT_FROM = ('quantity', 'revenue')          # §5 counts units; a question that names revenue keeps revenue
PRICE_NOT_UNITS = re.compile(r'doanh thu|doanh so|\bdthu\b|\bso don\b|bao nhieu don|may don')


def service_cues(intent: dict, q: str) -> list[str]:
    """Rulebook "Sửa xe" questions -> service metrics (q: accent-free, padded with spaces)."""
    filters = intent.get('filters') or {}
    count = re.search(SVC_COUNT, q)
    want, params, keep = None, {}, ('staff',)
    if SVC_COMMISSION.search(q) and SVC_WORKER.search(q):
        which = bool(SVC_WHICH_WORKER.search(q) and SVC_TOP.search(q))
        want = 'commission'
        if which:
            params, keep = {'k': 1}, ()
        elif SVC_ALL_WORKERS.search(q) or not filters.get('staff'):
            params, keep = {'table': True}, ()
    elif SVC_WORKER.search(q) and SVC_WHICH_WORKER.search(q) and SVC_TOP.search(q):
        many_tickets = re.search(r'\bnhieu (?:luot|nuot|phieu|xe)\b', q)
        by = 'days' if SVC_DAYS.search(q) else 'orders' if many_tickets else \
            'revenue' if SVC_MONEY.search(q) else None
        if by:
            want, params, keep = 'top_staff', {'by': by}, ()
    elif SVC_WARRANTY.search(q) and count and (SVC_TICKET.search(q) or re.search(r'\bxe\b', q)):
        if AVG_WORDS.search(q):
            want = 'avg_order_value'                   # "không tính xe bảo hành, bình quân 1 phiếu": paid tickets
        elif SVC_RATE.search(q):
            want = 'warranty_rate'
        else:
            want = 'warranty_count'
    elif SVC_DISTINCT_VEHICLES.search(q) and count and not SVC_REPEAT.search(q):
        model = filters.get('product')
        if isinstance(model, str) and model.strip():
            model = re.sub(r'^\s*(?:xe|chiec xe|chiec|dong xe)\s+', '', model, flags=re.I).strip()
            want, params, keep = 'vehicle_count', {'model': model}, ()
    elif intent.get('metric') in ('revenue', 'order_count', 'quantity', 'avg_order_value') and count \
            and SVC_TICKET.search(q) and not SVC_MONEY.search(q) and not AVG_WORDS.search(q):
        want, keep = 'order_count', ('staff', 'product', 'group')   # a job filter stays -> the metric abstains
    if not want:
        return []
    old = intent.get('metric')
    intent['metric'] = want
    intent['filters'] = {k: v for k, v in filters.items() if k in keep}
    intent['params'] = params
    intent['share_of_total'], intent['split_by'] = False, None
    if intent.get('answerable') is False:              # the shop vocabulary says what is counted
        intent['answerable'] = None
    if not COMPARE_CUE.search(q):
        intent['compare'], intent['output'] = None, None
    return [f'metric {old} -> {want} {params} (service book vocabulary)']


def apply_cues(intent: dict, q: str, skip=()) -> list[str]:
    """q: accent-free normalised question. skip: CUE_GROUPS to leave out (tests/cue_audit.py measures each)."""
    notes = []
    if not q:
        return notes
    q = f' {q} '
    metric = intent.get('metric')
    # price change effect: "tăng giá ... N ngày kể từ ... so với N ngày trước" -> price_effect with that N
    if 'price_effect' not in skip and PRICE_CHANGE_CUE.search(q) and PRICE_BEFORE_CUE.search(q):
        win = PRICE_WINDOW_CUE.search(q)
        if win and metric in PRICE_EFFECT_FROM and not PRICE_NOT_UNITS.search(q):
            notes.append(f'metric {metric} -> price_effect (price change + N days before/after)')
            intent['metric'] = metric = 'price_effect'
            intent['compare'], intent['output'] = None, None
        if win and metric == 'price_effect':
            params = intent.setdefault('params', {})
            if params.get('days') != int(win.group(1)):
                params['days'] = int(win.group(1))
                notes.append(f'days -> {params["days"]}')
    if metric == 'price_effect' and 'price_effect' not in skip:
        params = intent.setdefault('params', {})
        # no date written in the question: the model's date is a guess (often as_of) -> find the change in the data
        if params.get('date') and not PRICE_DATE_SAID.search(q):
            notes.append(f'dropped date {params.pop("date")!r} (question names no date: found from the prices)')
    # the quantity counted: orders, average per order, gross profit, units, debt repaid
    if 'what_counted' not in skip:
        want = None
        if metric == 'revenue' and AVG_WORDS.search(q) and PER_ORDER_CUE.search(q):
            want = 'avg_order_value'
        elif metric == 'revenue' and COUNT_ORDERS_CUE.search(q) and not MONEY_WORDS.search(q):
            want = 'order_count'
        elif metric == 'revenue' and GROSS_PROFIT_CUE.search(q):
            want = 'gross_profit'
        elif metric == 'order_count' and COUNT_UNITS_CUE.search(q) and not re.search(rf'\b{ORDER_NOUN}\b', q):
            want = 'quantity'
        elif metric in ('revenue', 'debt_total') and REPAID_CUE.search(q) and not re.search(r'\bno them\b', q):
            want = 'new_debt_and_repaid'
            intent.setdefault('params', {})['part'] = 'repaid'
        elif metric == 'gross_profit' and WHICH_ITEM_CUE.search(q) and re.search(r'\bnhat\b|\bnhut\b', q):
            want = 'top_products'
            intent.setdefault('params', {})['by'] = 'profit'
        if want:
            notes.append(f'metric {metric} -> {want} (what the question counts)')
            intent['metric'] = metric = want
        if metric == 'new_debt_and_repaid':          # which part: new debt, repaid, or both (two numbers)
            params = intent.setdefault('params', {})
            new = bool(NEW_DEBT_CUE.search(q))
            repaid = bool(REPAID_CUE.search(q) or re.search(r'\btra bot\b|\btra (?:duoc|dc)\b', q))
            part = None if new and repaid else 'new' if new else 'repaid' if repaid else params.get('part')
            if params.get('part') != part:
                notes.append(f'part {params.get("part")} -> {part}')
                params['part'] = part
    # a comparison the model left out: "so tháng trước lên hay xuống bao nhiêu %"
    periods = intent.get('periods') or []
    if 'compare_add' not in skip and not intent.get('compare') and len(periods) == 1 and not intent.get('shift_compare') \
            and metric in ORDER_LEVEL_METRICS + ('gross_profit',) and COMPARE_ADD_CUE.search(q) and PCT_CUE.search(q) \
            and not (re.search(r'\bca sang\b', q) and re.search(r'\bca chieu\b', q)):
        intent['compare'] = 'same_period_last_year' if LAST_YEAR_CUE.search(q) else 'previous'
        intent['output'] = 'pct'
        notes.append(f'compare {intent["compare"]} from cue')
    # delivery rounds
    if 'delivery' not in skip and DELIVERY_CONTEXT.search(q) and (DELIVERY_COUNT_CUE.search(q) or DELIVERY_MIN_CUE.search(q)):
        if metric != 'delivery_batches':
            notes.append(f'metric {metric} -> delivery_batches (question counts delivery rounds)')
            intent['metric'] = metric = 'delivery_batches'
            intent['filters'] = {}
        mn = DELIVERY_MIN_CUE.search(q)
        if mn:
            intent.setdefault('params', {})['min_batches'] = int(next(g for g in mn.groups() if g))
    if 'service' not in skip and intent.get('metric') != 'delivery_batches':
        found = service_cues(intent, q)
        if found:
            notes += found
            metric = intent['metric']
    # lots / expiry dates ("hết hạn", "hạn dùng", "HSD"): only the expiring metric answers these
    if 'expiry' not in skip and metric not in (None, 'expiring') and EXPIRY_CUE.search(q):
        notes.append(f'metric {metric} -> expiring (question is about expiry dates)')
        intent['metric'] = metric = 'expiring'
    # comparison
    if 'compare_drop' not in skip and intent.get('compare') and not COMPARE_CUE.search(q):
        notes.append(f'dropped compare {intent["compare"]} (no comparison words)')
        intent['compare'] = None
        if intent.get('output') in ('pct', 'diff'):
            intent['output'] = None
    if 'compare_kind' not in skip and intent.get('compare') in ('previous', 'same_period_last_year'):
        want = 'same_period_last_year' if LAST_YEAR_CUE.search(q) else 'previous' if PREVIOUS_CUE.search(q) else None
        if want and want != intent['compare']:
            notes.append(f'compare {intent["compare"]} -> {want}')
            intent['compare'] = want
    # top-k
    params = intent.setdefault('params', {})
    if 'topk' not in skip and metric in ('top_products', 'top_customers', 'debt_table'):
        k = top_k(q)
        if k and k != int(params.get('k') or 1) and 1 < k <= 20:
            params['k'] = k
            notes.append(f'k -> {params["k"]}')
    if 'strict' not in skip and (params.get('min_value') is not None or params.get('threshold') is not None):
        strict = None
        if re.search(r'tro len|it nhat|toi thieu|\bdat\b|≥|>=', q):
            strict = False
        elif re.search(r'\btren\b|hon\b|vuot|>', q):
            strict = True
        if strict is not None and bool(params.get('strict')) != strict:
            params['strict'] = strict
            notes.append(f'strict -> {strict}')
    if 'top_by' not in skip and metric == 'top_products':
        want = 'profit' if TOP_BY_PROFIT.search(q) else 'revenue' if TOP_BY_REVENUE.search(q) else \
            'qty' if TOP_BY_QTY.search(q) else None
        if want and params.get('by', 'qty') != want:
            notes.append(f'by {params.get("by")} -> {want}')
            params['by'] = want
    if 'top_by' not in skip:
        hit = SUBJECTIVE_ASK.search(q)
        if hit:
            params['undefined_term'] = hit.group(0).strip()
            notes.append(f'undefined judgement {hit.group(0).strip()!r} -> abstain')
    if 'top_by' not in skip:
        # rulebook §3 ranking terms whose metric the model often misses ("khách hay đổi ý nhất" -> best_day ...)
        want = ('top_customers', 'cancelled') if CUSTOMER_FICKLE.search(q) else \
            ('top_products', 'orders') if PRODUCT_FAVOURED.search(q) else \
            ('best_day', 'orders') if DAY_BUSY.search(q) else \
            ('best_day', 'hour') if PEAK_HOUR.search(q) else None
        if want and (metric, params.get('by')) != want:
            notes.append(f'{metric}/{params.get("by")} -> {want[0]}/{want[1]} (rulebook ranking term)')
            intent['metric'] = metric = want[0]
            params['by'] = want[1]
            intent['compare'], intent['output'], intent['share_of_total'] = None, None, False
    if 'top_by' not in skip and metric == 'top_customers':
        # rulebook: "khách trung thành nhất" = most days with a purchase; "khách sộp nhất" = highest average order
        # value among customers with >= 3 orders (not the most money, not the most orders)
        want = 'days' if CUSTOMER_LOYAL.search(q) else 'avg_order' if CUSTOMER_BIG.search(q) else None
        if want and params.get('by') != want:
            notes.append(f'by {params.get("by")} -> {want} (rulebook term)')
            params['by'] = want
    filters = intent.setdefault('filters', {})
    # filters with no ground in the question (copied from the shop's name list, or invented): dropped
    if 'ground' not in skip:
        for key in [k for k in GROUND_KEYS if filters.get(k)]:
            if key in ('product', 'customer', 'staff') and CODE_TOKEN.search(q):
                continue                              # the question names it by code; the model may give the name
            v = filters[key]
            if isinstance(v, list):
                kept = [x for x in v if _grounded(x, q)]
                if kept != v:
                    notes.append(f'dropped {key} {[x for x in v if x not in kept]!r} (not in the question)')
                    if kept:
                        filters[key] = kept
                    else:
                        filters.pop(key)
            elif isinstance(v, str) and not _grounded(v, q):
                notes.append(f'dropped {key} {filters.pop(key)!r} (not in the question)')
        pm = filters.get('payment_method')
        if pm is not None and (plain_text(pm) in NO_VALUE or not PAYMENT_ANY.search(q)):
            notes.append(f'dropped payment_method {filters.pop("payment_method")!r} (no payment word in the question)')
        if filters.get('shift') and not SHIFT_SAID.search(q):
            notes.append(f'dropped shift {filters.pop("shift")!r} (no "ca sáng/ca chiều" in the question)')
        ch = filters.get('channel')
        if ch is not None and (plain_text(ch) in NO_VALUE or not CHANNEL_ANY.search(q)):
            notes.append(f'dropped channel {filters.pop("channel")!r} (no channel word in the question)')
    # status filter the model added on its own: the metric already says it (cancelled_count + "cancelled"), or the
    # question names no status at all ("tổng cộng bao nhiêu đơn" + "completed"). Kept only on positive evidence.
    if 'status' not in skip and filters.get('status'):
        from .rules import status_filter_value
        st = status_filter_value(filters['status'])
        said = STATUS_SAID.get(st)
        if (st == 'huỷ' and metric in ('cancelled_count', 'cancel_rate')) or (said is not None and not said.search(q)):
            notes.append(f'dropped status {filters.pop("status")!r} (not asked in the question)')
    # sales channel / payment method named in the question (fixed vocabulary)
    split = None
    if 'split' not in skip and metric in ('revenue', 'order_count', 'avg_order_value') and not SPLIT_BLOCK.search(q) \
            and len(intent.get('periods') or []) <= 1:
        for key, cues in (('payment_method', PAYMENT_CUES + [COD_CUE]), ('channel', CHANNEL_CUES)):
            vals = named_values(q, cues)
            if len(vals) >= 2:
                split = key
                intent['split_by'] = [key, vals]
                intent['compare'], intent['output'], intent['share_of_total'] = None, None, False
                filters.pop(key, None)
                notes.append(f'split by {key} {vals}')
                break
    if 'channel_payment' not in skip and metric in ORDER_LEVEL_METRICS:
        ch = None if split == 'channel' else next((c for c, rx in CHANNEL_CUES if rx.search(q)), None)
        pm = None if split == 'payment_method' else next((c for c, rx in PAYMENT_CUES if rx.search(q)), None)
        if ch and filters.get('channel') != ch:
            filters['channel'] = ch
            notes.append(f'channel -> {ch}')
            if filters.get('payment_method') and not pm:
                notes.append(f'dropped payment_method {filters.pop("payment_method")!r} (it named the channel)')
        if pm and filters.get('payment_method') != pm:
            filters['payment_method'] = pm
            notes.append(f'payment_method -> {pm}')
    # pharmacy: prescription drugs / active ingredient (rulebook "Nhà thuốc")
    if 'pharmacy' not in skip and metric in ORDER_LEVEL_METRICS:
        rx = False if NON_RX_CUE.search(q) else True if RX_CUE.search(q) else None
        ai = ACTIVE_CUE.search(q)
        ai = ai.group(1).strip() if ai else None
        if rx is not None or ai:
            for k in ('product', 'group'):            # the LLM tends to guess a product/group here
                v = filters.get(k)
                if v and (plain_text(v) not in q or re.search(r'\bke don\b|\bhoat chat\b', plain_text(v))):
                    notes.append(f'dropped {k} {v!r} (question names a drug attribute)')
                    filters.pop(k)
            if intent.get('answerable') is False:
                intent['answerable'] = None
        if rx is not None and filters.get('prescription') != rx:
            filters['prescription'] = rx
            notes.append(f'prescription -> {rx}')
        if ai and filters.get('active_ingredient') != ai:
            filters['active_ingredient'] = ai
            notes.append(f'active_ingredient -> {ai}')
    # shift
    if 'shift' in skip:
        return notes
    morning, afternoon = bool(re.search(r'\bca sang\b', q)), bool(re.search(r'\bca chieu\b', q))
    if morning and afternoon and not intent.get('shift_compare'):
        intent['shift_compare'] = True
        intent['compare'] = None
        filters.pop('shift', None)
        notes.append('shift_compare from cue')
    elif (morning ^ afternoon) and not filters.get('shift'):
        filters['shift'] = 'sang' if morning else 'chieu'
        notes.append(f'shift -> {filters["shift"]}')
    return notes
