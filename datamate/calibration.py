"""Answer-or-abstain policy learned from train results.

Score is +1 / -1 / 0, so answering is worth it only when P(correct) > 0.5.
P(correct) is estimated per bucket of features that exist at inference time, with a Beta prior so
rare buckets fall back to their parent bucket instead of trusting 1-2 examples.

Features
  metric, status, flags      how the answer was reached (v5)
  agree   (v6, step 2)       metric route vs SQL route: agree | disagree | nosql | sql_only
  ans     (v6, step 3)       XLM-R P(answerable) bin: u2 <0.2 <= u1 <0.5 <= a1 <0.8 <= a2

Buckets, most general first (each shrunk to the previous one):
  () -> (status) [-> (status, agree)] [-> (status, agree, ans)] -> (metric, status, ...) -> (..., flags)
Without agree / ans the chain is exactly v5's.

Rescue (v6, step 3): a question the pipeline abstains on is answered "unanswerable" when, among
train rows that also abstained with the same answerability bin, the gold was unanswerable with
shrunk probability > threshold.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ANS_EDGES = ((0.2, 'u2'), (0.5, 'u1'), (0.8, 'a1'), (1.01, 'a2'))


def ans_bin(p):
    if p is None:
        return None
    for edge, name in ANS_EDGES:
        if p < edge:
            return name
    return 'a2'


def features(row: dict, use_agree=True, use_ans=True) -> dict:
    """Inference-time features of one pipeline output (no gold, no ids)."""
    intent = row.get('intent') or {}
    flags = []
    if intent.get('compare'):
        flags.append('compare')
    if len(intent.get('periods') or []) > 1:
        flags.append('multi_period')
    if (intent.get('filters') or {}).get('product'):
        flags.append('product')
    if row.get('repairs'):
        flags.append('repaired')
    if row.get('fixes'):
        flags.append('fixed')
    if row.get('route') == 'sql':
        flags.append('sql')
    return {'metric': intent.get('metric', '?'), 'status': row.get('status', 'abstain'),
            'flags': '+'.join(sorted(flags)) or '-',
            'agree': row.get('agree') if use_agree else None,
            'ans': ans_bin(row.get('p_answerable')) if use_ans else None}


def _keys(f: dict):
    extra = tuple(x for x in (f'agree:{f["agree"]}' if f.get('agree') else None,
                              f'ans:{f["ans"]}' if f.get('ans') else None) if x)
    chain = [(), (f['status'],)]
    for i in range(1, len(extra) + 1):
        chain.append((f['status'],) + extra[:i])
    chain.append((f['metric'], f['status']) + extra)
    chain.append((f['metric'], f['status']) + extra + (f['flags'],))
    return list(reversed(chain))                      # most specific first (v5 order)


class Calibrator:
    def __init__(self, prior_strength: float = 4.0, threshold: float = 0.5, use_agree=True, use_ans=True,
                 rescue=True, rescue_prior=0.2):
        self.k = prior_strength
        self.threshold = threshold
        self.use_agree, self.use_ans, self.rescue = use_agree, use_ans, rescue
        self.rescue_prior = rescue_prior
        self.stats = {}
        self.rescue_stats = {}

    def _f(self, row):
        return features(row, self.use_agree, self.use_ans)

    def fit(self, rows):
        """rows: pipeline outputs with 'verdict' in {'correct','wrong','abstain'} and 'gold_type'."""
        counts = defaultdict(lambda: [0, 0])
        rescue = defaultdict(lambda: [0, 0])
        for r in rows:
            f = self._f(r)
            if r.get('verdict') in ('correct', 'wrong'):
                for key in _keys(f):
                    counts[key][0] += r['verdict'] == 'correct'
                    counts[key][1] += 1
            if r.get('status') == 'abstain' and r.get('gold_type') and f.get('ans'):
                for key in (('rescue',), ('rescue', f['ans'])):
                    rescue[key][0] += r['gold_type'] == 'unanswerable'
                    rescue[key][1] += 1
        self.stats = {k: tuple(v) for k, v in counts.items()}
        self.rescue_stats = {k: tuple(v) for k, v in rescue.items()}
        return self

    def p_correct(self, row) -> float:
        p = 0.5                                     # uninformed root prior
        for key in reversed(_keys(self._f(row))):   # root -> most specific, each shrunk to its parent
            hit, n = self.stats.get(key, (0, 0))
            p = (hit + self.k * p) / (n + self.k)
        return p

    def p_unanswerable_given_abstain(self, row):
        b = self._f(row).get('ans')
        if b is None:
            return None
        # only the abstain rows of the same bin count: an unseen bin keeps the low prior and is never rescued
        hit, n = self.rescue_stats.get(('rescue', b), (0, 0))
        return (hit + self.k * self.rescue_prior) / (n + self.k)

    def decide(self, row) -> dict:
        """Return row with status turned into abstain when expected score is negative (or rescued)."""
        status = row.get('status')
        if status == 'abstain':
            if self.rescue:
                p = self.p_unanswerable_given_abstain(row)
                if p is not None and p > self.threshold:
                    return dict(row, status='unanswerable', original_status='abstain', p_correct=round(p, 3),
                                reason=f'answerability model: p_unanswerable={p:.2f} (pipeline: {row.get("reason")})')
            return row
        if status not in ('answered', 'unanswerable'):
            return row
        p = self.p_correct(row)
        out = dict(row, p_correct=round(p, 3))
        if p <= self.threshold:
            out.update(status='abstain', reason=f'calibrated p={p:.2f} <= {self.threshold}', original_status=status)
        return out

    def save(self, path):
        Path(path).write_text(json.dumps({
            'version': 6, 'k': self.k, 'threshold': self.threshold, 'use_agree': self.use_agree,
            'use_ans': self.use_ans, 'rescue': self.rescue, 'rescue_prior': self.rescue_prior,
            'stats': [[list(k), list(v)] for k, v in self.stats.items()],
            'rescue_stats': [[list(k), list(v)] for k, v in self.rescue_stats.items()]},
            ensure_ascii=False, indent=1), encoding='utf-8')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        cal = cls(data['k'], data['threshold'], data.get('use_agree', False), data.get('use_ans', False),
                  data.get('rescue', False), data.get('rescue_prior', 0.2))
        cal.stats = {tuple(k): tuple(v) for k, v in data['stats']}
        cal.rescue_stats = {tuple(k): tuple(v) for k, v in data.get('rescue_stats', [])}
        return cal


def _cli():
    """python -m datamate.calibration --results results/ --out calibration.json  (fit on all train shops)"""
    import argparse
    from .eval_grouped import load_results
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True, nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--prior', type=float, default=4.0)
    ap.add_argument('--no-agree', action='store_true')
    ap.add_argument('--no-ans', action='store_true')
    ap.add_argument('--no-rescue', action='store_true')
    args = ap.parse_args()
    rows = []
    for folder in args.results:
        by_shop, _ = load_results(folder)
        rows += [r for rs in by_shop.values() for r in rs]
    cal = Calibrator(args.prior, use_agree=not args.no_agree, use_ans=not args.no_ans,
                     rescue=not args.no_rescue).fit(rows)
    cal.save(args.out)
    print('buckets', len(cal.stats), 'rescue buckets', len(cal.rescue_stats), 'saved', args.out)


if __name__ == '__main__':
    _cli()
