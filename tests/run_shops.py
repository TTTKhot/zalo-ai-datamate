"""GPU-free end-to-end run: real data -> mapping -> views -> scripted intent -> metric -> score.

python tests/run_shops.py --train-root DATA/train --answers DATA/train/answers.jsonl biz_101 biz_104 ...
Writes results/<biz>.json (per question: intent, answer, gold, verdict, seconds).
"""
from __future__ import annotations

import argparse
import json
import pickle
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-root', required=True)
    ap.add_argument('--answers', required=True)
    ap.add_argument('--out', default=str(ROOT / 'results'))
    ap.add_argument('--cache', default='')
    ap.add_argument('--rule-gate', action='store_true', help='abstain on questions using new / uncovered rules '
                    'of <train-root>/rulebook.md (datamate.rulebook.Gate), as predict.py does')
    ap.add_argument('biz', nargs='+')
    args = ap.parse_args()
    root = Path(args.train_root)
    questions = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    gold = {r['id']: r for r in map(json.loads, Path(args.answers).read_text(encoding='utf-8').splitlines()) if r}
    cal = Calendar(root / 'calendar.csv')
    gate = None
    if args.rule_gate:
        from datamate.rulebook import Gate
        gate = Gate.from_file(root / 'rulebook.md')
    Path(args.out).mkdir(parents=True, exist_ok=True)
    if args.cache:
        Path(args.cache).mkdir(parents=True, exist_ok=True)   # e.g. /tmp/shopcache does not exist on Windows
    total = Counter()
    for biz in args.biz:
        cache = Path(args.cache) / f'{biz}_shop.pkl' if args.cache else None
        if cache and cache.exists():
            shop = pickle.loads(cache.read_bytes())
        else:
            shop = load_shop(root / 'data' / biz, biz)
            if cache:
                cache.write_bytes(pickle.dumps(shop))
        rows, by_metric = [], defaultdict(Counter)
        for rec in (q for q in questions if q['business_id'] == biz):
            out = answer(shop, rec, scripted_intent, cal, gate=gate)
            sub = to_submission(out)
            g = gold.get(rec['id'])
            if g is None:
                verdict = 'no_gold'
            elif sub['type'] == 'abstain':
                verdict = 'abstain'
            else:
                verdict = 'correct' if is_correct(sub, g) else 'wrong'
            out.update(verdict=verdict, gold_type=None if g is None else g['type'], gold=None if g is None else (g.get('answer') if g['type'] != 'unanswerable' else 'UNANSWERABLE'))
            rows.append(out)
            metric = (out.get('intent') or {}).get('metric', '?')
            by_metric[metric][verdict] += 1
            total[verdict] += 1
        c = Counter(r['verdict'] for r in rows)
        print(f"{biz}: correct {c['correct']} wrong {c['wrong']} abstain {c['abstain']} / {len(rows)}  "
              f"score {c['correct'] - c['wrong']}  (load {shop.seconds}s)")
        for m, cnt in sorted(by_metric.items(), key=lambda kv: -sum(kv[1].values())):
            print(f"    {m:24} {dict(cnt)}")
        from datamate.answerability import capabilities
        meta = {'concepts': sorted(shop.views.has), 'capabilities': capabilities(shop.views)}
        (Path(args.out) / f'{biz}.meta.json').write_text(json.dumps(meta), encoding='utf-8')
        (Path(args.out) / f'{biz}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print('TOTAL', dict(total), 'score', total['correct'] - total['wrong'])


if __name__ == '__main__':
    main()
