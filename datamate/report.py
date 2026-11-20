"""Before / after table for v6 steps, on held-out shops only.

python -m datamate.report --runs v5=results_v5 lora=results_lora lora_sql=results_lora_sql \
       [--sft sft/all.jsonl] [--shops biz_105 biz_112 ...] [--folds 0] [--out report.md]

For every run (score_run output dir) and every calibration variant, the abstain policy is fitted
on the other shops of the same run (GroupKFold; --folds 0 = leave-one-shop-out) and applied to
the held-out shop, so "policy" numbers are what an unseen shop would get. Variants:
  raw          no policy (answer whenever the pipeline answers)
  v5           metric/status/flags buckets only
  +agree       + metric-route vs SQL-route agreement (step 2)
  +ans         + XLM-R answerability bin (step 3)
  +ans+rescue  + abstain -> unanswerable when the classifier is confident (step 3)
  all          everything available in the run
With --sft, also the exact-match rate of predicted intents vs the answer-verified labels.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .eval_grouped import evaluate, load_results, score
from .intent import canonical_intent

VARIANTS = {
    'v5': dict(use_agree=False, use_ans=False, rescue=False),
    '+agree': dict(use_agree=True, use_ans=False, rescue=False),
    '+ans': dict(use_agree=False, use_ans=True, rescue=False),
    '+ans+rescue': dict(use_agree=False, use_ans=True, rescue=True),
    'all': dict(use_agree=True, use_ans=True, rescue=True),
}


def has_feature(rows, key):
    return any(r.get(key) not in (None, 'nosql') for r in rows)


def intent_em(rows, labels):
    hit = n = 0
    for r in rows:
        lab = labels.get(r['id'])
        if lab is None:
            continue
        n += 1
        pred = r.get('intent')
        hit += isinstance(pred, dict) and canonical_intent(pred) == lab
    return (round(hit / n, 4) if n else None), n


def run_report(runs: dict, shops=None, folds=0, sft=None):
    labels = {}
    if sft:
        for l in Path(sft).read_text(encoding='utf-8').splitlines():
            r = json.loads(l)
            if r.get('intent'):
                labels[r['id']] = canonical_intent(r['intent'])
    table = []
    for name, folder in runs.items():
        by_shop, sigs = load_results(folder)
        if shops:
            by_shop = {s: v for s, v in by_shop.items() if s in set(shops)}
            sigs = {s: v for s, v in sigs.items() if s in by_shop}
        rows = [r for v in by_shop.values() for r in v]
        k = len(by_shop) if folds in (0, None) else min(folds, len(by_shop))
        line = {'run': name, 'shops': len(by_shop), 'n': len(rows), 'raw': score(rows)}
        for vname, kw in VARIANTS.items():
            if kw['use_agree'] and not has_feature(rows, 'agree'):
                continue
            if kw['use_ans'] and not has_feature(rows, 'p_answerable'):
                continue
            if len(by_shop) < 2:
                continue
            rep = evaluate(by_shop, sigs, k, **kw)
            line[vname] = rep['group_kfold']['with_policy']
        if labels:
            line['intent_em'], line['intent_n'] = intent_em(rows, labels)
        line['by_metric'] = by_metric(rows)
        table.append(line)
    return table


def by_metric(rows):
    out = {}
    for r in rows:
        m = (r.get('intent') or {}).get('metric', '?')
        out.setdefault(m, Counter())[r['verdict']] += 1
    return {m: dict(c) for m, c in sorted(out.items(), key=lambda kv: -sum(kv[1].values()))}


def to_markdown(table):
    cols = ['raw'] + list(VARIANTS)
    head = '| run | shops | n | ' + ' | '.join(cols) + ' | intent EM |\n|' + '---|' * (len(cols) + 4)
    lines = [head]
    for t in table:
        cells = []
        for c in cols:
            s = t.get(c)
            cells.append(f"{s['score']} ({s['correct']}✓ {s['wrong']}✗ {s['abstain']}–)" if s else '·')
        em = f"{t['intent_em']:.1%} of {t['intent_n']}" if t.get('intent_em') is not None else '·'
        lines.append(f"| {t['run']} | {t['shops']} | {t['n']} | " + ' | '.join(cells) + f' | {em} |')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', nargs='+', required=True, help='name=results_dir')
    ap.add_argument('--shops', nargs='*', default=None)
    ap.add_argument('--split', default=None, help='split.json: use its val shops')
    ap.add_argument('--folds', type=int, default=0)
    ap.add_argument('--sft', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    runs = dict(r.split('=', 1) for r in args.runs)
    shops = args.shops
    if args.split:
        shops = json.loads(Path(args.split).read_text())['val']
    table = run_report(runs, shops, args.folds, args.sft)
    md = to_markdown(table)
    print(md)
    if args.out:
        Path(args.out).write_text(md + '\n\n```json\n' + json.dumps(table, ensure_ascii=False, indent=1) + '\n```\n',
                                  encoding='utf-8')


if __name__ == '__main__':
    main()
