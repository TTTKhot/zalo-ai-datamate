"""Invariance check on the QUESTION text: rewrite how the month is written and check the answer does not change.

python tests/perturb_questions.py --train-root data/train [--cache .cache/shops] [--out broken.json] biz_101 biz_102 ...

Every "tháng M/YYYY" / "tháng M năm YYYY" (with or without accents, leading zero) in a train question is rewritten in
one family at a time (all occurrences of the question):
  T      T5/2026          Th2    Th5/26          thg    thg 5/2026      bare4  5/2026
  bare2  5/26             dash   tháng 5-2026    Tdot   T.5/2026        pad    05/2026
  Thg    Thg5/2026 (no space)
The forms are general Vietnamese shorthand for a month (written independently of datamate/normalize.py).
Questions without a month-year are skipped (counted). For each family the tool counts
  lost   = original correct, variant not correct
  gained = original not correct, variant correct
  diff   = submitted answer of the variant differs from the original's (right or wrong)
Only for shops you may look at: held-out shops of kaggle/config.json `val_shops` are refused.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from datamate.periods import Calendar                       # noqa: E402
from datamate.pipeline import answer, load_shop              # noqa: E402
from datamate.scoring import is_correct, to_submission       # noqa: E402
from scripted_intent import scripted_intent                  # noqa: E402

# "tháng 5/2026", "Tháng 05 năm 2026", "thang 5/2026", "tháng 5 / 2026"
MONTH_YEAR = re.compile(r'(?<![\w])(?:tháng|thang)\s+0?(\d{1,2})\s*(?:/|\s(?:năm|nam)\s)\s*(\d{4})(?![\d/])',
                        re.IGNORECASE)

FAMILIES = {
    'T': lambda m, y: f'T{m}/{y}',
    'Th2': lambda m, y: f'Th{m}/{y % 100:02d}',
    'thg': lambda m, y: f'thg {m}/{y}',
    'bare4': lambda m, y: f'{m}/{y}',
    'bare2': lambda m, y: f'{m}/{y % 100:02d}',
    'dash': lambda m, y: f'tháng {m}-{y}',
    'Tdot': lambda m, y: f'T.{m}/{y}',
    'pad': lambda m, y: f'{m:02d}/{y}',
    'Thg': lambda m, y: f'Thg{m}/{y}',
}


def rewrite(question: str, family: str) -> str | None:
    fn = FAMILIES[family]
    new, n = MONTH_YEAR.subn(lambda mt: fn(int(mt.group(1)), int(mt.group(2))), question)
    return new if n else None


def get_shop(root: Path, biz: str, cache_dir: str):
    cache = Path(cache_dir) / f'{biz}_shop.pkl' if cache_dir else None
    if cache and cache.exists():
        return pickle.loads(cache.read_bytes())
    shop = load_shop(root / 'data' / biz, biz)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(shop))
    return shop


def run_one(shop, rec, cal):
    sub = to_submission(answer(shop, rec, scripted_intent, cal))
    return sub


def verdict(sub, g):
    if sub['type'] == 'abstain':
        return 'abstain'
    return 'correct' if g and is_correct(sub, g) else 'wrong'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-root', required=True)
    ap.add_argument('--families', nargs='*', default=list(FAMILIES))
    ap.add_argument('--cache', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--examples', type=int, default=0, help='print N rewritten questions per family and exit')
    ap.add_argument('biz', nargs='+')
    args = ap.parse_args()
    root = Path(args.train_root)
    hold = set(json.loads((ROOT / 'kaggle' / 'config.json').read_text(encoding='utf-8')).get('val_shops') or [])
    bad = [b for b in args.biz if b in hold]
    if bad:
        sys.exit(f'refusing held-out shops {bad} (kaggle/config.json val_shops)')
    unknown = [f for f in args.families if f not in FAMILIES]
    if unknown:
        sys.exit(f'unknown families {unknown}; known: {list(FAMILIES)}')
    questions = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    questions = [q for q in questions if q['business_id'] in set(args.biz)]
    if args.examples:
        with_month = [q for q in questions if MONTH_YEAR.search(q['question'])][:args.examples]
        for q in with_month:
            print('GỐC ', q['question'])
            for fam in args.families:
                print(f'  {fam:6s}', rewrite(q['question'], fam))
        return
    gold = {r['id']: r for r in map(json.loads, (root / 'answers.jsonl').read_text(encoding='utf-8').splitlines()) if r}
    cal = Calendar(root / 'calendar.csv')
    total, by_shop, broken = Counter(), defaultdict(Counter), []
    for biz in args.biz:
        shop = get_shop(root, biz, args.cache)
        qs = [q for q in questions if q['business_id'] == biz]
        n_month = 0
        for rec in qs:
            variants = {fam: rewrite(rec['question'], fam) for fam in args.families}
            if not any(variants.values()):
                continue
            n_month += 1
            g = gold.get(rec['id'])
            base = run_one(shop, rec, cal)
            v0 = verdict(base, g)
            for fam, text in variants.items():
                sub = run_one(shop, dict(rec, question=text), cal)
                v1 = verdict(sub, g)
                same = json.dumps(sub, sort_keys=True, ensure_ascii=False, default=str) == \
                    json.dumps(base, sort_keys=True, ensure_ascii=False, default=str)
                key = 'kept' if v0 == 'correct' and v1 == 'correct' else \
                    'lost' if v0 == 'correct' else 'gained' if v1 == 'correct' else 'still_not'
                for c in (total, by_shop[biz]):
                    c[(fam, key)] += 1
                    c[(fam, 'diff')] += not same
                if key in ('lost', 'gained') or not same:
                    broken.append({'biz': biz, 'family': fam, 'id': rec['id'], 'kind': key, 'same_answer': same,
                                   'question': rec['question'], 'variant': text, 'base_verdict': v0,
                                   'new_verdict': v1, 'base_answer': base, 'new_answer': sub})
        line = '  '.join(f"{f} −{by_shop[biz][(f, 'lost')]}/+{by_shop[biz][(f, 'gained')]}/≠{by_shop[biz][(f, 'diff')]}"
                         for f in args.families)
        print(f'{biz}: {n_month}/{len(qs)} câu có tháng-năm  {line}', flush=True)
        total['month_q'] += n_month
        total['all_q'] += len(qs)
    print(f"\n=== {total['month_q']}/{total['all_q']} câu có tháng-năm (còn lại bỏ qua)")
    print('họ      giữ/gốc đúng        mất  thêm  đáp án khác')
    for fam in args.families:
        k, l = total[(fam, 'kept')], total[(fam, 'lost')]
        print(f"{fam:7s} {k}/{k + l} ({100.0 * k / max(k + l, 1):.1f}%)  {l:5d} {total[(fam, 'gained')]:5d} "
              f"{total[(fam, 'diff')]:6d}")
    if args.out:
        Path(args.out).write_text(json.dumps(broken, ensure_ascii=False, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
