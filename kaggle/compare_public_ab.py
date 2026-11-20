"""Compare public-split runs on the SAME shops by the ChatGPT reference (measuring stick only, see score_public_ref.py).

python kaggle/compare_public_ab.py NAME=<run_public dir> [NAME=<run_public dir> ...] [--rule-gate] [--shops dev_001 dev_003 ...]

<run_public dir> holds submission.jsonl and logs/<shop>/<id>.json. For a run made with --sql (logs carry `agree`) two more
variants are derived offline from the same run: "<NAME>+agree" (answer only when metric and SQL agree) and
"<NAME>+calib" (calibration.json of the repo applied to the logged rows, as predict.sh does).
The Docker guards of score_public_ref.py are applied to every variant (rulebook gate only with --rule-gate). Prints counts per variant: all shops,
the 4 public shops kept unread (totals only) and the other shops. Never prints questions.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'kaggle'))
from datamate.calibration import Calibrator      # noqa: E402
from datamate.scoring import is_correct, to_submission   # noqa: E402
from score_public_ref import REF, SPLIT, gated_ids, guards, load    # noqa: E402

UNREAD = {'dev_001', 'dev_007', 'dev_009', 'dev_010'}     # public shops whose errors nobody reads (HIEN_TRANG.md §4)


RAW = {}


def variants(name, run: Path):
    rows = {r['id']: r for r in load(run / 'submission.jsonl')}
    logs = {}
    for f in run.glob('logs/*/*.json'):
        if f.name != 'shop_report.json':
            d = json.loads(f.read_text(encoding='utf-8'))
            logs[d['id']] = d
    out = {name: rows}
    RAW[name] = RAW[name + '+agree'] = RAW[name + '+calib'] = rows     # the shop guard counts the RAW output of the run
    if any('agree' in d for d in logs.values()):
        out[name + '+agree'] = {i: (r if r['type'] == 'abstain' or logs.get(i, {}).get('agree') == 'agree'
                                    else {'id': i, 'type': 'abstain'}) for i, r in rows.items()}
        cal_path = ROOT / 'calibration.json'
        if cal_path.exists():
            cal, calib = Calibrator.load(cal_path), {}
            for i, r in rows.items():
                d = logs.get(i)
                try:
                    calib[i] = r if d is None else dict(to_submission(cal.decide(d)), id=i)
                except Exception:
                    calib[i] = r
            out[name + '+calib'] = calib
    return out


def main():
    argv = sys.argv[1:]
    shops = set()
    argv = [a for a in argv if a != '--rule-gate']
    if '--shops' in argv:
        k = argv.index('--shops')
        shops, argv = set(argv[k + 1:]), argv[:k]
    ref = {r['id']: r for r in load(REF)}
    questions = load(SPLIT / 'questions.jsonl')
    shop = {q['id']: q['business_id'] for q in questions}
    gated = gated_ids(questions) if '--rule-gate' in sys.argv else set()
    table = {}
    for spec in argv:
        name, _, path = spec.partition('=')
        table.update(variants(name, Path(path)))
    common = set.intersection(*(set(v) for v in table.values()))
    if shops:
        common = {i for i in common if shop[i] in shops}
    print(f'{len(common)} câu chung, {len({shop[i] for i in common})} shop')
    print(f'{"cấu hình":16s} {"trả lời":>8s} {"khớp":>6s} {"khác":>6s} {"điểm/câu":>9s} | giữ kín: khớp/khác | còn lại: khớp/khác | shop bị chặn')
    for name, rows in table.items():
        _, bad = guards([RAW[name][i] for i in sorted(common)], shop, gated)
        rows, _ = guards([rows[i] for i in sorted(common)], shop, gated)
        rows = [{'id': r['id'], 'type': 'abstain'} if shop[r['id']] in bad else r for r in rows]
        c = collections.Counter()
        for r in rows:
            if r['type'] == 'abstain':
                continue
            try:
                good = bool(is_correct(r, ref[r['id']]))
            except Exception:
                good = False
            c[(shop[r['id']] in UNREAD, good)] += 1
        ok, ko = c[(True, True)] + c[(False, True)], c[(True, False)] + c[(False, False)]
        print(f'{name:16s} {ok + ko:8d} {ok:6d} {ko:6d} {(ok - ko) / max(len(common), 1):+9.3f} | '
              f'{c[(True, True)]}/{c[(True, False)]} | {c[(False, True)]}/{c[(False, False)]} | {sorted(bad)}')


if __name__ == '__main__':
    main()
