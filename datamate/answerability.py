"""Step 3 of v6: XLM-R classifier "can this shop's data answer this question?".

Input pair: (question, shop capabilities). Capabilities are written from the canonical views,
in the same Vietnamese words for every shop: which concepts the data has (sales lines,
orders, payments, purchases, stock, expenses ...) and which canonical columns are filled
(cost, customers, payment method, staff, order time, product groups, expiry ...).
Label: 1 if the gold answer is a value, 0 if answers.jsonl says unanswerable.
The probability is a feature for calibration (datamate.calibration), never a hard rule.

python -m datamate.answerability build   --train-root T --answers A --out ans_data [--cache C]
python -m datamate.answerability train   --data ans_data --model xlm-roberta-base --out models/xlmr_ans
python -m datamate.answerability predict --model models/xlmr_ans --results results_llm [--data ans_data]
       (adds p_answerable to every row of results/<biz>.json; or use AnswerabilityModel in predict.py)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

from .normalize import norm as rule_norm

CONCEPT_VI = {
    'sales_line': 'dòng bán hàng', 'order': 'đơn hàng', 'product': 'danh mục hàng', 'unit_conversion': 'quy đổi đơn vị',
    'customer': 'danh sách khách', 'purchase': 'phiếu nhập', 'purchase_line': 'chi tiết nhập hàng',
    'stock_snapshot': 'tồn kho', 'payment': 'thanh toán / trả nợ', 'expense': 'chi phí', 'supplier': 'nhà cung cấp',
    'staff': 'nhân viên', 'price_history': 'lịch sử giá',
}
COLUMN_VI = {
    ('sales_lines', 'unit_cost'): 'giá vốn', ('sales_lines', 'line_cost'): 'giá vốn',
    ('products', 'unit_cost'): 'giá vốn', ('sales_lines', 'customer_key'): 'khách hàng',
    ('sales_lines', 'customer_group'): 'nhóm khách', ('sales_lines', 'payment_method'): 'hình thức thanh toán',
    ('sales_lines', 'staff'): 'nhân viên bán', ('orders', 'hour'): 'giờ bán', ('sales_lines', 'channel'): 'kênh bán',
    ('products', 'group'): 'nhóm hàng', ('sales_lines', 'line_discount'): 'giảm giá',
    ('orders', 'paid_amount'): 'số tiền đã trả', ('orders', 'shipping_fee'): 'phí giao hàng', ('orders', 'vat'): 'VAT',
    ('purchase_lines', 'expiry_date'): 'hạn dùng', ('stock_snapshot', 'expiry_date'): 'hạn dùng',
    ('purchase_lines', 'lot'): 'lô hàng', ('purchases', 'supplier'): 'nhà cung cấp',
    ('purchase_lines', 'supplier'): 'nhà cung cấp', ('products', 'is_prescription'): 'thuốc kê đơn',
    ('products', 'active_ingredient'): 'hoạt chất', ('sales_lines', 'delivery_date'): 'ngày giao',
    ('sales_lines', 'order_status'): 'trạng thái đơn',
}


def capabilities(views) -> str:
    has = sorted(CONCEPT_VI.get(c, c) for c in views.has)
    cols = []
    for (table, col), label in COLUMN_VI.items():
        df = views.frames.get(table)
        if df is not None and col in df and df[col].notna().any() and label not in cols:
            if col == 'order_status' and set(df[col].dropna().unique()) <= {'hoàn thành'}:
                continue
            cols.append(label)
    span = f'{views.data_start} đến {views.data_end}' if views.data_start else 'không rõ'
    return f'dữ liệu có: {", ".join(has) or "không"}; cột: {", ".join(sorted(cols)) or "không"}; thời gian {span}'


def pair_text(question, caps):
    q = rule_norm(question)
    return f'{question} | {q}', caps


# ------------------------------------------------------------------ data
def build(train_root, answers, out_dir, cache=None, log=print):
    from .pipeline import load_shop_cached
    root = Path(train_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    questions = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    gold = {r['id']: r for r in (json.loads(l) for l in Path(answers).read_text(encoding='utf-8').splitlines() if l.strip())}
    caps = {}
    rows = []
    for biz in sorted({q['business_id'] for q in questions}):
        folder = root / 'data' / biz
        if not folder.is_dir():
            continue
        try:
            shop = load_shop_cached(folder, biz, cache)
            caps[biz] = capabilities(shop.views)
        except Exception as exc:
            log(f'{biz}: {exc!r}')
            continue
    for q in questions:
        if q['business_id'] not in caps:
            continue
        g = gold.get(q['id'])
        a, b = pair_text(q['question'], caps[q['business_id']])
        rows.append({'id': q['id'], 'business_id': q['business_id'], 'text_a': a, 'text_b': b,
                     'label': None if g is None else int(g['type'] != 'unanswerable')})
    with (out / 'pairs.jsonl').open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    (out / 'capabilities.json').write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding='utf-8')
    n_pos = sum(r['label'] == 1 for r in rows)
    n_neg = sum(r['label'] == 0 for r in rows)
    log(f'pairs {len(rows)}: answerable {n_pos}, unanswerable {n_neg}, shops {len(caps)}')
    return rows


# ------------------------------------------------------------------ model
class AnswerabilityModel:
    def __init__(self, model_dir, device=None, max_len=256):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True).to(self.device)
        self.model.eval()
        self.max_len = max_len

    def predict(self, pairs, batch=32):
        out = []
        for i in range(0, len(pairs), batch):
            a, b = zip(*pairs[i:i + batch])
            enc = self.tok(list(a), list(b), truncation=True, max_length=self.max_len, padding=True,
                           return_tensors='pt').to(self.device)
            with self.torch.no_grad():
                logits = self.model(**enc).logits.float()
            out += self.torch.softmax(logits, -1)[:, 1].tolist()
        return out

    def p_answerable(self, question, views=None, caps=None):
        caps = caps if caps is not None else capabilities(views)
        return self.predict([pair_text(question, caps)])[0]


def auc(labels, scores):
    pos = [s for l, s in zip(labels, scores) if l == 1]
    neg = [s for l, s in zip(labels, scores) if l == 0]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def train(data_dir, model_name, out_dir, split=None, epochs=3, lr=2e-5, batch=16, max_len=256, seed=0, log=print):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    from .splits import load_split, shop_split
    random.seed(seed)
    torch.manual_seed(seed)
    rows = [json.loads(l) for l in (Path(data_dir) / 'pairs.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    rows = [r for r in rows if r['label'] is not None]
    if split and Path(split).exists():
        tr_shops, va_shops = load_split(split)
    else:
        tr_shops, va_shops = shop_split({r['business_id'] for r in rows})
    tr = [r for r in rows if r['business_id'] in set(tr_shops)]
    va = [r for r in rows if r['business_id'] in set(va_shops)]
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2).to(dev)
    n_pos = sum(r['label'] for r in tr)
    n_neg = len(tr) - n_pos
    weight = torch.tensor([len(tr) / max(2 * n_neg, 1), len(tr) / max(2 * n_pos, 1)], device=dev)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weight)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    steps = math.ceil(len(tr) / batch) * epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    use_amp = dev == 'cuda'
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)

    def batches(data, shuffle):
        idx = list(range(len(data)))
        if shuffle:
            random.shuffle(idx)
        for i in range(0, len(idx), batch):
            part = [data[j] for j in idx[i:i + batch]]
            enc = tok([r['text_a'] for r in part], [r['text_b'] for r in part], truncation=True, max_length=max_len,
                      padding=True, return_tensors='pt').to(dev)
            yield enc, torch.tensor([r['label'] for r in part], device=dev)

    def predict(data):
        model.eval()
        out = []
        with torch.no_grad():
            for enc, _ in batches(data, False):
                out += torch.softmax(model(**enc).logits.float(), -1)[:, 1].tolist()
        model.train()
        return out

    log(f'train {len(tr)} ({n_neg} unanswerable) val {len(va)} ({sum(1 - r["label"] for r in va)} unanswerable)')
    history = []
    started = time.time()
    model.train()
    for ep in range(epochs):
        total = 0.0
        for enc, y in batches(tr, True):
            with torch.autocast('cuda', dtype=torch.float16, enabled=use_amp):
                loss = loss_fn(model(**enc).logits.float(), y)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            total += loss.item()
        ev = {'epoch': ep + 1, 'train_loss': round(total / max(1, math.ceil(len(tr) / batch)), 4)}
        if va:
            p = predict(va)
            labels = [r['label'] for r in va]
            ev['val_auc'] = auc(labels, p)
            ev['val_acc@0.5'] = round(sum((s > 0.5) == bool(l) for s, l in zip(p, labels)) / len(va), 4)
            ev['val_recall_unans@0.5'] = round(sum(s <= 0.5 for s, l in zip(p, labels) if l == 0) /
                                               max(1, sum(1 for l in labels if l == 0)), 4)
        history.append(ev)
        log(str(ev))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    (out / 'train_log.json').write_text(json.dumps({'history': history, 'train_shops': tr_shops, 'val_shops': va_shops,
                                                     'minutes': round((time.time() - started) / 60, 1)}, indent=1))
    return history


def attach(model_dir, results_dir, data_dir=None, log=print):
    """Add p_answerable to every row of results/<biz>.json (rows need 'question' and a shop id = file stem)."""
    m = AnswerabilityModel(model_dir)
    caps = json.loads((Path(data_dir) / 'capabilities.json').read_text(encoding='utf-8')) if data_dir else {}
    for f in sorted(Path(results_dir).glob('biz_*.json')):
        if f.name.endswith('.meta.json'):
            continue
        rows = json.loads(f.read_text(encoding='utf-8'))
        cap = caps.get(f.stem)
        if cap is None:
            meta = Path(results_dir) / f'{f.stem}.meta.json'
            cap = json.loads(meta.read_text(encoding='utf-8')).get('capabilities') if meta.exists() else None
        if cap is None:
            log(f'{f.stem}: no capabilities, skipped')
            continue
        ps = m.predict([pair_text(r.get('question', ''), cap) for r in rows])
        for r, p in zip(rows, ps):
            r['p_answerable'] = round(p, 4)
        f.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        log(f'{f.stem}: {len(rows)} rows')


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--train-root', required=True)
    b.add_argument('--answers', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--cache', default=None)
    t = sub.add_parser('train')
    t.add_argument('--data', required=True)
    t.add_argument('--model', default='xlm-roberta-base')
    t.add_argument('--out', required=True)
    t.add_argument('--split', default=None)
    t.add_argument('--epochs', type=int, default=3)
    t.add_argument('--lr', type=float, default=2e-5)
    t.add_argument('--batch', type=int, default=16)
    p = sub.add_parser('predict')
    p.add_argument('--model', required=True)
    p.add_argument('--results', required=True)
    p.add_argument('--data', default=None)
    args = ap.parse_args(argv)
    if args.cmd == 'build':
        build(args.train_root, args.answers, args.out, args.cache)
    elif args.cmd == 'train':
        train(args.data, args.model, args.out, args.split, args.epochs, args.lr, args.batch)
    else:
        attach(args.model, args.results, args.data)


if __name__ == '__main__':
    main()
