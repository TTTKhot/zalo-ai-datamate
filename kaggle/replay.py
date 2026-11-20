"""Re-run logged Qwen outputs through the current code (no GPU) and score them, old vs new.

python kaggle/replay.py [runs/<stamp>] [--run lora_sql] [--train data/train] [--no-sql] [--show changed|all|none]

v6 logs: <run>/state/run_<name>/logs/<biz>/<id>.json (+ shop_report.json). Replayed per question:
  intent  llm_raw (with the repair round) -> current parser / cue rules / validate / metric library
  hint    the logged ViT5 hint, if any
  SQL     sql_raw -> current validate_sql / duckdb / agreement (unless --no-sql)
  p_answerable copied from the log
Scores are raw (before the abstain threshold), like datamate.score_run. "old" = verdict of the log
as written on Kaggle, "new" = current code; "metric-only" = same output without the SQL route.

Limits: the table mapping is rebuilt with heuristics only (the mapper's LLM output is not logged),
so a shop whose Kaggle mapping relied on the LLM can differ. And see CLAUDE.md: replaying the very
errors the rules were written from is an OPTIMISTIC estimate.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.llm import ReplayBackend                    # noqa: E402
from datamate.normalize import norm                      # noqa: E402
from datamate.periods import Calendar                    # noqa: E402
from datamate.pipeline import answer, llm_intent_fn, load_shop, question_context  # noqa: E402
from datamate.score_run import strip_sql                 # noqa: E402
from datamate.scoring import is_correct, to_submission   # noqa: E402

PREFERRED = ['lora_sql_hint', 'lora_sql', 'v5']           # most complete GPU run first


def verdict(out, g):
    raw = dict(out, status=out.get('original_status', out.get('status')))
    sub = to_submission(raw)
    if sub['type'] == 'abstain':
        return 'abstain'
    return 'correct' if is_correct(sub, g) else 'wrong'


def find_logs(run: Path, name):
    runs = {p.parent.name[4:]: p for p in run.rglob('logs') if p.is_dir() and p.parent.name.startswith('run_')}
    if name:
        if name not in runs:
            sys.exit(f'Không có run_{name}/logs; có: {sorted(runs)}')
        return runs[name], name
    for n in PREFERRED:
        if n in runs:
            return runs[n], n
    if runs:
        n = sorted(runs)[0]
        return runs[n], n
    logs = next((p for p in run.rglob('logs') if p.is_dir()), None)      # v5 layout: run_llm/logs, any logs/
    if logs is None:
        sys.exit(f'Không thấy thư mục logs trong {run}')
    return logs, logs.parent.name


def score(c):
    return c['correct'] - c['wrong']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', nargs='?', default=None)
    ap.add_argument('--run', dest='name', default=None, help='tên lần chạy trong state/run_<tên> (vd v5, lora_sql)')
    ap.add_argument('--train', default=str(ROOT / 'data' / 'train'))
    ap.add_argument('--no-sql', action='store_true', help='không phát lại đường SQL')
    ap.add_argument('--show', choices=['changed', 'all', 'none'], default='changed',
                    help='changed: câu đổi kết quả; all: mọi câu sai/bỏ trống sau khi phát lại')
    a = ap.parse_args()
    run = Path(a.run or (ROOT / 'runs' / 'LATEST').read_text().strip())
    train = Path(a.train)
    gold = {r['id']: r for r in map(json.loads, next(train.glob('answers*.jsonl')).read_text(encoding='utf-8').splitlines()) if r}
    qs = {q['id']: q for q in map(json.loads, (train / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines()) if q}
    cal = Calendar(train / 'calendar.csv')
    logs, name = find_logs(run, a.name)
    print(f'phát lại {logs} ({name})')
    tot = {k: collections.Counter() for k in ('old', 'new', 'metric')}
    moves = collections.Counter()
    for bdir in sorted(p for p in logs.iterdir() if p.is_dir()):
        files = [f for f in sorted(bdir.glob('*.json')) if f.name != 'shop_report.json']
        if not files:
            continue
        shop = load_shop(train / 'data' / bdir.name, bdir.name)
        c = {k: collections.Counter() for k in tot}
        for f in files:
            log = json.loads(f.read_text(encoding='utf-8'))
            q, g = qs.get(log['id']), gold.get(log['id'])
            if q is None or g is None:
                continue
            hint = log.get('hint')
            fn = llm_intent_fn(ReplayBackend(log.get('llm_raw') or []), norm,
                               hint_fn=(lambda _q, _names, h=hint: h) if hint else None)
            out = answer(shop, q, fn, cal)
            sql_raw = log.get('sql_raw')
            if sql_raw and not a.no_sql:
                from datamate.sqlpath import SqlRoute, attach_sql
                try:
                    n, tagged, _ = question_context(q['question'], q.get('as_of_date'), shop.names, norm)
                    route = SqlRoute(shop, ReplayBackend(sql_raw), cal)
                    out = attach_sql(out, route.ask(q['question'], q.get('as_of_date'), n, tagged))
                except Exception as exc:
                    out.update(agree='nosql', sql_error=repr(exc))
            if log.get('p_answerable') is not None:
                out['p_answerable'] = log['p_answerable']
            v = {'old': verdict(log, g), 'new': verdict(out, g), 'metric': verdict(strip_sql(out), g)}
            for k in c:
                c[k][v[k]] += 1
            moves[(v['old'], v['new'])] += 1
            if (a.show == 'changed' and v['old'] != v['new']) or (a.show == 'all' and v['new'] != 'correct'):
                print(f"  {bdir.name} {v['old']}→{v['new']}: {q['question'][:80]} | {str(out.get('answer'))[:60]} "
                      f"vs {str(g.get('answer'))[:60]} | {out.get('reason')} | agree={out.get('agree')}")
        print(f"{bdir.name}: cũ {score(c['old'])} → mới {score(c['new'])} (chỉ metric {score(c['metric'])})  {dict(c['new'])}")
        for k in tot:
            tot[k] += c[k]
    print(f"TOTAL cũ {score(tot['old'])} {dict(tot['old'])}")
    print(f"TOTAL mới {score(tot['new'])} {dict(tot['new'])}  | chỉ metric {score(tot['metric'])}")
    print('chuyển trạng thái:', {f'{o}→{n}': k for (o, n), k in sorted(moves.items()) if o != n})


if __name__ == '__main__':
    main()
