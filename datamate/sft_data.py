"""Step 1 of v6: answer-verified intent data for LoRA finetuning.

For every train question we look for an intent JSON that the metric library turns into the
gold answer of answers.jsonl. Candidates, in order of trust:

  seeds      intents already proposed by a reader of the question: logged Qwen outputs (raw and
             post-processed) and the GPU-free scripted parser (a labelling tool used only here
             and in tests, never at inference);
  neighbours one edit away from a seed in the intent vocabulary (metric swapped with a related
             metric, comparison / output mode, top-k from a number written in the question,
             ranking key, strict threshold, a filter dropped or a product named in the question,
             periods from the date tagger, share / shift flags), then two edits for the pairs
             that move together (compare + output, metric + ranking key);
  last       "answerable": false - only when the gold says unanswerable and nothing that
             reaches the library's own Unanswerable matches.

The first candidate whose answer is correct is kept, after the same post-processing used at
inference, so the target is what the finetuned model should emit. Nothing depends on
question ids or business ids: the search space is the intent schema itself.

python -m datamate.sft_data --train-root DATA/train --answers DATA/train/answers.jsonl \
       --out sft [--qwen-logs run_llm/logs] [--cache cache] [--val-frac 0.2] [--businesses ...]
Writes sft/all.jsonl (one row per question, labelled or not), sft/train.jsonl, sft/val.jsonl
(chat format for train_lora.py), sft/split.json and sft/report.json (coverage per shop/source).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from .intent import build_compact_messages, canonical_intent, parse_intent, relevant_names
from .metrics import NO_PERIOD
from .normalize import norm as rule_norm
from .periods import Calendar
from .pipeline import answer, load_shop_cached, postprocess_intent, question_context
from .scoring import is_correct, to_submission
from .splits import save_split, shop_split

METRIC_NEIGHBORS = {
    'revenue': ['quantity', 'order_count', 'avg_order_value', 'best_day', 'gross_profit', 'top_products'],
    'quantity': ['revenue', 'order_count', 'purchase_minus_sales'],
    'order_count': ['revenue', 'quantity', 'cancelled_count', 'customers_min_orders'],
    'avg_order_value': ['revenue'],
    'top_products': ['top_customers', 'revenue', 'quantity', 'unsold_products'],
    'top_customers': ['top_products', 'debt_table'],
    'best_day': ['revenue'],
    'debt_total': ['debtor_count', 'debt_table', 'new_debt_and_repaid', 'debt_aging'],
    'debtor_count': ['debt_total', 'customers_min_orders'],
    'debt_table': ['debt_total', 'top_customers'],
    'debt_aging': ['debt_total'],
    'new_debt_and_repaid': ['debt_total'],
    'cancelled_count': ['cancel_rate', 'order_count'],
    'cancel_rate': ['cancelled_count'],
    'gross_profit': ['net_profit', 'revenue'],
    'net_profit': ['gross_profit'],
    'purchase_total': ['avg_purchase_price', 'top_supplier'],
    'top_supplier': ['purchase_total'],
    'avg_purchase_price': ['unit_price', 'purchase_total'],
    'stock': ['stock_value', 'purchase_minus_sales'],
    'stock_value': ['stock'],
    'unit_price': ['avg_purchase_price', 'revenue'],
    'price_effect': ['quantity'],
    'customers_min_orders': ['products_min_orders', 'top_customers'],
    'products_min_orders': ['customers_min_orders'],
    'unsold_products': ['top_products'],
    'days_min_revenue': ['revenue'],
    'purchase_minus_sales': ['stock', 'quantity'],
}
BY = {'top_products': ['qty', 'revenue', 'profit'], 'top_customers': ['revenue', 'orders']}
MAX_CANDIDATES = 160


def _money_numbers(q: str):
    """Numbers written in the question, money suffixes expanded (k, nghìn, tr, triệu)."""
    out = []
    for m in re.finditer(r'(\d+(?:[.,]\d+)*)\s*(k|nghin|ngan|tr|trieu|cu)?\b', q):
        raw, suf = m.group(1), m.group(2)
        if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', raw):
            v = float(re.sub(r'[.,]', '', raw))
        else:
            v = float(raw.replace(',', '.'))
        v *= {'k': 1e3, 'nghin': 1e3, 'ngan': 1e3, 'tr': 1e6, 'trieu': 1e6, 'cu': 1e6}.get(suf, 1)
        out.append(v)
    return out


def neighbours(seed: dict, qn: str, names: dict, tagged, as_of):
    """Intents one edit away from seed (desc, intent). Generic over the intent schema."""
    def mk(desc, **change):
        it = copy.deepcopy(seed)
        for k, v in change.items():
            if k in ('params', 'filters'):
                d = dict(it.get(k) or {})
                for kk, vv in v.items():
                    if vv is None:
                        d.pop(kk, None)
                    else:
                        d[kk] = vv
                it[k] = d
            else:
                it[k] = v
        return desc, it

    metric = seed.get('metric')
    params = seed.get('params') or {}
    filters = seed.get('filters') or {}
    periods = seed.get('periods') or []
    if tagged and tagged != periods:
        yield mk('periods=tagger', periods=tagged)
    for m in METRIC_NEIGHBORS.get(metric, []):
        yield mk(f'metric={m}', metric=m)
    for c in (None, 'previous', 'same_period_last_year', 'explicit'):
        if c != seed.get('compare'):
            yield mk(f'compare={c}', compare=c)
    for o in (None, 'pct', 'diff'):
        if o != seed.get('output'):
            yield mk(f'output={o}', output=o)
    ints = sorted({int(v) for v in _money_numbers(qn) if v == int(v) and 2 <= v <= 20})
    if metric in ('top_products', 'top_customers', 'debt_table'):
        for k in ints:
            if k != params.get('k'):
                yield mk(f'k={k}', params={'k': k})
        for b in BY.get(metric, []):
            if b != params.get('by'):
                yield mk(f'by={b}', params={'by': b})
        yield mk('as_list', params={'as_list': not params.get('as_list')})
        yield mk('order=asc', params={'order': None if params.get('order') == 'asc' else 'asc'})
    for key in ('min_value', 'threshold'):
        if key in params:
            yield mk('strict', params={'strict': not params.get('strict')})
            for v in _money_numbers(qn):
                if v != params[key]:
                    yield mk(f'{key}={v:g}', params={key: v})
    for flag in ('as_percent', 'split_big_unit'):
        if flag in params:
            yield mk(flag, params={flag: not params.get(flag)})
    for key in list(filters):
        yield mk(f'drop {key}', filters={key: None})
    for p in relevant_names(qn, {'products': names.get('products', [])}, per_kind=3).get('products', []):
        if p != filters.get('product'):
            yield mk(f'product={p}', filters={'product': p})
    if metric in NO_PERIOD:
        yield mk('as_of=today', periods=[{'type': 'as_of', 'date': as_of}])
    yield mk('share_of_total', share_of_total=not seed.get('share_of_total'))
    if len(periods) > 1:
        for o in ('increasing', 'argmax'):
            yield mk(f'output={o}', output=o, compare=None)


def pairs(seed: dict):
    """Two-edit moves that only make sense together."""
    for c in ('previous', 'same_period_last_year', 'explicit'):
        for o in ('pct', 'diff'):
            if (c, o) != (seed.get('compare'), seed.get('output')):
                it = copy.deepcopy(seed)
                it.update(compare=c, output=o)
                yield f'compare={c}+output={o}', it
    for m in METRIC_NEIGHBORS.get(seed.get('metric'), []):
        for b in BY.get(m, []):
            it = copy.deepcopy(seed)
            it['metric'] = m
            it['params'] = {**(it.get('params') or {}), 'by': b}
            yield f'metric={m}+by={b}', it


class Verifier:
    def __init__(self, shop, calendar):
        self.shop, self.cal = shop, calendar

    def check(self, rec, intent, gold, norm, tagged):
        """(ok, final_intent, out). final_intent = post-processed + name-snapped intent."""
        it = copy.deepcopy(intent)
        postprocess_intent(it, norm, tagged)
        holder = {}

        def fn(q, a, names):
            holder['it'] = it
            return it
        out = answer(self.shop, rec, fn, self.cal)
        sub = to_submission(out)
        return is_correct(sub, gold), holder.get('it', it), out


def seeds_for(rec, shop, qwen_logs, scripted):
    out = []
    if qwen_logs:
        f = Path(qwen_logs) / rec['business_id'] / f"{rec['id']}.json"
        if f.exists():
            row = json.loads(f.read_text(encoding='utf-8'))
            for raw in row.get('llm_raw') or []:
                it = parse_intent(raw)
                if it:
                    out.append(('qwen_raw', it))
                    break
            if isinstance(row.get('intent'), dict) and row['intent'].get('metric'):
                out.append(('qwen_final', row['intent']))
    if scripted is not None:
        try:
            it = scripted(rec['question'], rec.get('as_of_date'), shop.names)
            if it:
                out.append(('scripted', it))
        except Exception:
            pass
    uniq, seen = [], set()
    for src, it in out:
        key = json.dumps(canonical_intent(it), sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            uniq.append((src, it))
    return uniq


def label_question(rec, gold, shop, verifier, seeds, max_candidates=MAX_CANDIDATES):
    norm, tagged, _ = question_context(rec['question'], rec.get('as_of_date'), shop.names, rule_norm)
    tried = set()
    n = 0

    def attempt(src, desc, dist, it):
        nonlocal n
        key = json.dumps(canonical_intent(it), sort_keys=True, ensure_ascii=False, default=str)
        if key in tried or n >= max_candidates:
            return None
        tried.add(key)
        n += 1
        ok, final, out = verifier.check(rec, it, gold, norm, tagged)
        if ok:
            return {'source': src, 'edit': desc, 'distance': dist, 'intent': canonical_intent(final),
                    'status': out.get('status')}
        return None

    for src, it in seeds:
        hit = attempt(src, '', 0, it)
        if hit:
            hit['seeds_ok'] = [s for s, i in seeds if s == src]
            return hit, n
    for src, it in seeds:
        for desc, cand in neighbours(it, norm or '', shop.names, tagged, rec.get('as_of_date')):
            hit = attempt(src, desc, 1, cand)
            if hit:
                return hit, n
    for src, it in seeds:
        for desc, cand in pairs(it):
            hit = attempt(src, desc, 2, cand)
            if hit:
                return hit, n
    if gold.get('type') == 'unanswerable' and seeds:
        src, it = seeds[0]
        cand = {**copy.deepcopy(it), 'answerable': False}
        hit = attempt(src, 'answerable=false', 1, cand)
        if hit:
            return hit, n
    return None, n


def build(train_root, answers, out_dir, qwen_logs=None, cache=None, val_frac=0.2, businesses=None,
          use_scripted=True, val_shops=None, log=print, augment=0, seed=0):
    root = Path(train_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    questions = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    gold = {r['id']: r for r in (json.loads(l) for l in Path(answers).read_text(encoding='utf-8').splitlines() if l.strip())}
    shops = sorted({q['business_id'] for q in questions if q['id'] in gold and (root / 'data' / q['business_id']).is_dir()})
    if businesses:
        shops = [s for s in shops if s in set(businesses)]
    scripted = None
    if use_scripted:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
        try:
            from scripted_intent import scripted_intent as scripted
        except Exception as exc:
            log(f'scripted parser unavailable: {exc!r}')
    cal = Calendar(root / 'calendar.csv')
    rows, sigs = [], {}
    started = time.time()
    for biz in shops:
        t0 = time.time()
        shop = load_shop_cached(root / 'data' / biz, biz, cache)
        sigs[biz] = '+'.join(sorted(shop.views.has))
        ver = Verifier(shop, cal)
        tried_total, c = 0, Counter()
        for rec in (q for q in questions if q['business_id'] == biz and q['id'] in gold):
            g = gold[rec['id']]
            seeds = seeds_for(rec, shop, qwen_logs, scripted)
            hit, n = label_question(rec, g, shop, ver, seeds)
            tried_total += n
            norm, tagged, _ = question_context(rec['question'], rec.get('as_of_date'), shop.names, rule_norm)
            row = {'id': rec['id'], 'business_id': biz, 'question': rec['question'], 'as_of': rec.get('as_of_date'),
                   'gold_type': g['type'], 'n_candidates': n, 'seeds': [s for s, _ in seeds]}
            if hit:
                row.update(hit)
                row['messages'] = build_compact_messages(rec['question'], rec.get('as_of_date'), shop.names, norm, tagged)
                if augment:
                    row['aug'] = _augment(rec, shop, augment, seed)
                c['labelled'] += 1
                c[f"d{hit['distance']}"] += 1
            else:
                c['unlabelled'] += 1
            rows.append(row)
        log(f'{biz}: {dict(c)} candidates {tried_total} ({time.time() - t0:.0f}s)')
    if val_shops is None:
        train_shops, val_shops = shop_split(shops, val_frac, signatures=sigs)
    else:
        train_shops = [s for s in shops if s not in set(val_shops)]
    save_split(out / 'split.json', train_shops, sorted(val_shops), signatures=sigs)
    n_aug = Counter()
    with (out / 'all.jsonl').open('w', encoding='utf-8') as fa, \
            (out / 'train.jsonl').open('w', encoding='utf-8') as ft, \
            (out / 'val.jsonl').open('w', encoding='utf-8') as fv, \
            (out / 'val_noise.jsonl').open('w', encoding='utf-8') as fn:
        for r in rows:
            r['split'] = 'val' if r['business_id'] in val_shops else 'train'
            aug = r.pop('aug', None) or {}
            fa.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')
            if r.get('intent'):
                target = [{'role': 'assistant', 'content': json.dumps(r['intent'], ensure_ascii=False)}]
                ex = {'id': r['id'], 'business_id': r['business_id'], 'messages': r['messages'] + target}
                (fv if r['split'] == 'val' else ft).write(json.dumps(ex, ensure_ascii=False) + '\n')
                # train shops: TRAIN_FAMILIES only; held-out shops: one variant of every family (measurement only)
                for a in (aug.get('train', []) if r['split'] == 'train' else aug.get('probe', [])):
                    ex = {'id': f"{r['id']}~{a['family']}", 'business_id': r['business_id'], 'family': a['family'],
                          'messages': a['messages'] + target}
                    (ft if r['split'] == 'train' else fn).write(json.dumps(ex, ensure_ascii=False) + '\n')
                    n_aug[f"{r['split']}:{a['family']}"] += 1
    if augment:
        log(f'augmented: {dict(sorted(n_aug.items()))}')
    rep = report(rows)
    rep['augmented'] = dict(n_aug)
    rep['split'] = {'train': train_shops, 'val': sorted(val_shops)}
    rep['seconds'] = round(time.time() - started)
    (out / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    return rep


def _augment(rec, shop, k, seed):
    """Noisy copies of a labelled question (label unchanged): k train-family variants + one probe per family."""
    import random
    from .augment import HELDOUT_FAMILIES, TRAIN_FAMILIES, apply, variants
    names = list(shop.names.get('products', [])) + list(shop.names.get('customers', []))
    s = seed * 1_000_003 + sum(map(ord, rec['id']))

    def pack(fam, text):
        norm, tagged, _ = question_context(text, rec.get('as_of_date'), shop.names, rule_norm)
        return {'family': fam, 'question': text,
                'messages': build_compact_messages(text, rec.get('as_of_date'), shop.names, norm, tagged)}
    train = [pack(f, t) for f, t in variants(rec['question'], TRAIN_FAMILIES, k, s, names)]
    probe = []
    for i, fam in enumerate(TRAIN_FAMILIES + HELDOUT_FAMILIES):
        t = apply(rec['question'], fam, random.Random(s + 7919 * (i + 1)), names)
        if t != rec['question']:
            probe.append(pack(fam, t))
    return {'train': train, 'probe': probe}


def report(rows):
    per_shop = defaultdict(Counter)
    by_source, by_dist, by_metric, by_gold = Counter(), Counter(), defaultdict(Counter), defaultdict(Counter)
    for r in rows:
        lab = bool(r.get('intent'))
        per_shop[r['business_id']]['labelled' if lab else 'unlabelled'] += 1
        by_gold[r['gold_type']]['labelled' if lab else 'unlabelled'] += 1
        if lab:
            by_source[r['source']] += 1
            by_dist[r['distance']] += 1
            by_metric[r['intent'].get('metric')]['n'] += 1
    n = len(rows)
    lab = sum(1 for r in rows if r.get('intent'))
    return {'questions': n, 'labelled': lab, 'coverage': round(lab / max(n, 1), 4),
            'by_source': dict(by_source), 'by_distance': {str(k): v for k, v in sorted(by_dist.items())},
            'by_gold_type': {k: dict(v) for k, v in by_gold.items()},
            'per_shop': {k: dict(v) for k, v in sorted(per_shop.items())},
            'by_metric': {k: v['n'] for k, v in sorted(by_metric.items(), key=lambda kv: -kv[1]['n'])}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-root', required=True)
    ap.add_argument('--answers', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--qwen-logs', default=None)
    ap.add_argument('--cache', default=None)
    ap.add_argument('--val-frac', type=float, default=0.2)
    ap.add_argument('--val-shops', nargs='*', default=None)
    ap.add_argument('--no-scripted', action='store_true')
    ap.add_argument('--businesses', nargs='*', default=None)
    ap.add_argument('--augment', type=int, default=0,
                    help='noisy variants per labelled train question (datamate/augment.py TRAIN_FAMILIES); '
                         'also writes val_noise.jsonl (every family, held-out shops) for measurement')
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args(argv)
    rep = build(args.train_root, args.answers, args.out, args.qwen_logs, args.cache, args.val_frac,
                args.businesses, not args.no_scripted, args.val_shops, augment=args.augment, seed=args.seed)
    print(json.dumps({k: v for k, v in rep.items() if k != 'per_shop'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
