"""Score submissions of the public split against the ChatGPT-made reference (measuring stick ONLY).

python kaggle/score_public_ref.py <submission.jsonl> [<submission.jsonl> ...] [--policy] [--by-shop]

The reference (runs/tham_chieu_gpt/tham_chieu_day_du_co_tin_cay.jsonl) is NOT gold: it was solved by another AI. It is
used only to COMPARE configurations offline; never train on it, never fit thresholds on it, never ship it.
Calibration against 4 real leaderboard scores: leaderboard ~= reference score + 0.04.

--policy applies the guards of the Docker run before scoring (the same function, `datamate.launch.apply_guards`):
  1. a shop with more than 20% of its questions answered "unanswerable" -> abstain on the whole shop (mapping failed);
  2. every remaining "unanswerable" -> abstain (precision of that answer on unseen shops is far below 50%).
--rule-gate (with --policy) also abstains on questions caught by the rulebook gate, as `predict.py --rule-gate` does.
  The gate is OFF by default in the shipped code since 16/11 (it lost ~0.02 on the leaderboard).
Prints counts only.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.launch import UNANSWERABLE_CAP, apply_guards   # noqa: E402
from datamate.normalize import norm          # noqa: E402
from datamate.rulebook import Gate           # noqa: E402
from datamate.scoring import is_correct      # noqa: E402

SPLIT = ROOT / 'public_test' / 'public_test'
REF = ROOT / 'runs' / 'tham_chieu_gpt' / 'tham_chieu_day_du_co_tin_cay.jsonl'


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8-sig').splitlines() if l.strip()]


def guards(rows, shop, gated=frozenset()):
    """The Docker guards (`launch.apply_guards`) on `rows`; `gated` ids (rulebook gate, only with --rule-gate) abstain
    and, as in launch, are left out of a shop's unanswerable share."""
    questions = [{'id': r['id'], 'business_id': shop[r['id']]} for r in rows]
    got = {r['id']: r for r in rows}
    guarded, _, bad = apply_guards(questions, got, cap=UNANSWERABLE_CAP, gated=set(gated))
    out = [{'id': r['id'], 'type': 'abstain'} if r['id'] in gated else guarded[r['id']] for r in rows]
    return out, bad


def gated_ids(questions):
    gate = Gate.from_file(SPLIT / 'rulebook.md')          # same call as kaggle/apply_gate.py
    return {q['id'] for q in questions if gate.check(norm(q['question']))}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    use_policy, by_shop = '--policy' in sys.argv, '--by-shop' in sys.argv
    ref = {r['id']: r for r in load(REF)}
    questions = load(SPLIT / 'questions.jsonl')
    shop = {q['id']: q['business_id'] for q in questions}
    gated = gated_ids(questions) if use_policy and '--rule-gate' in sys.argv else set()
    for path in args:
        rows = load(path)
        note = ''
        if use_policy:
            rows, bad = guards(rows, shop, gated)
            note = f' | shop bị chặn: {sorted(bad)}'
        c = w = 0
        per = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            if r['type'] == 'abstain':
                continue
            try:
                good = bool(is_correct(r, ref[r['id']]))
            except Exception:
                good = False
            c += good
            w += not good
            per[shop[r['id']]][0 if good else 1] += 1
        print(f'{Path(path).name}: trả lời {c + w} | khớp {c} | khác {w} | điểm tham chiếu {(c - w) / len(questions):+.3f} '
              f'(ước leaderboard {(c - w) / len(questions) + 0.04:+.3f}){note}')
        if by_shop:
            print('   ', {s: f'{v[0]}/{v[1]}' for s, v in sorted(per.items())})


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'kaggle'))
    main()
