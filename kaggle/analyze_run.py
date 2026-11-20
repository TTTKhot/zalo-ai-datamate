"""Summarise a downloaded run: score of every result set, wrong/abstain of the best one grouped by
metric and by SQL agreement, compact error list, and the notebook's before/after reports.

python kaggle/analyze_run.py [runs/<stamp>] [--results results_lora_sql]   -> prints summary, writes <run>/errors.md

v6 layout (v6_state.zip extracted): <run>/state/results_<name>/biz_*.json, state/report_*.md,
state/run_<name>/logs/<biz>/<id>.json. v5 layout: <run>/**/results_llm/. Scores are on the shops
the notebook evaluated (v6: held-out val shops), raw = before the abstain threshold; the
threshold-applied numbers are in the report_*.md tables (leave-one-shop-out).
"""
import argparse
import collections
import json
import sys
from pathlib import Path

# most complete pipeline first (same order the notebook uses to pick the calibration source)
PREFERRED = ['results_lora_sql_hint', 'results_lora_sql_ans', 'results_lora_sql', 'results_lora', 'results_v5',
             'results_llm', 'results_scripted']

ap = argparse.ArgumentParser()
ap.add_argument('run', nargs='?', default=None)
ap.add_argument('--results', default=None, help='tên thư mục kết quả để liệt kê lỗi (mặc định: bản đầy đủ nhất)')
a = ap.parse_args()
run = Path(a.run or Path('runs/LATEST').read_text().strip())

res_dirs = {p.name: p for p in run.rglob('results_*') if p.is_dir() and any(p.glob('biz_*.json'))}
if not res_dirs:
    logs = sorted(run.glob('*.log'))
    sys.exit(f'Không thấy results_* trong {run} (kernel lỗi? xem {logs[0] if logs else "file .log"})')
main_name = a.results or next((n for n in PREFERRED if n in res_dirs), sorted(res_dirs)[0])
if main_name not in res_dirs:
    sys.exit(f'Không có {main_name}; có: {sorted(res_dirs)}')


def load(folder):
    out = {}
    for f in sorted(folder.glob('biz_*.json')):
        if not f.name.endswith('.meta.json'):
            out[f.stem] = json.loads(f.read_text(encoding='utf-8'))
    return out


def fmt(c):
    return f"đúng {c['correct']} sai {c['wrong']} bỏ trống {c['abstain']} → {c['correct'] - c['wrong']}"


lines = ['# Run ' + run.name, '', '## Mọi bộ kết quả (raw, trước ngưỡng)', '']
order = sorted(res_dirs, key=lambda n: PREFERRED.index(n) if n in PREFERRED else len(PREFERRED))
for name in order:
    shops = load(res_dirs[name])
    c = collections.Counter(r['verdict'] for rows in shops.values() for r in rows)
    lines.append(f"- {name} ({len(shops)} shop): {fmt(c)}" + ('  ← chi tiết bên dưới' if name == main_name else ''))

shops = load(res_dirs[main_name])
lines += ['', f'## {main_name} theo shop', '']
total = collections.Counter()
by_metric = collections.defaultdict(collections.Counter)
by_agree = collections.defaultdict(collections.Counter)
errors = []
for biz, rows in shops.items():
    c = collections.Counter(r['verdict'] for r in rows)
    total += c
    lines.append(f'- {biz}: {fmt(c)}')
    for r in rows:
        m = (r.get('intent') or {}).get('metric')
        by_metric[m][r['verdict']] += 1
        if r.get('agree') is not None:
            by_agree[r['agree']][r['verdict']] += 1
        if r['verdict'] != 'correct':
            it = {k: v for k, v in (r.get('intent') or {}).items() if v not in (None, False, {}, [])}
            extra = ''
            if r.get('agree') is not None or r.get('p_answerable') is not None:
                extra = (f"\n  agree: {r.get('agree')} | route: {r.get('route', 'metric')} | p_ans: {r.get('p_answerable')}"
                         f" | sql: {str(r.get('sql') or '')[:160]} | sql_value: {str(r.get('sql_value'))[:80]}")
            errors.append(f"- [{biz}] {r['verdict']} | {r.get('id')} | {r.get('question')}\n"
                          f"  intent: {json.dumps(it, ensure_ascii=False)}\n"
                          f"  answer: {str(r.get('answer'))[:100]} | gold: {str(r.get('gold'))[:100]} | "
                          f"reason: {r.get('reason')} | fixes: {r.get('fixes')}" + extra)
summary_end = len(lines)
lines += ['', f"**Tổng {main_name}: {fmt(total)}**", '', '## Theo metric', '']
for m, c in sorted(by_metric.items(), key=lambda kv: -(kv[1]['wrong'] + kv[1]['abstain'])):
    lines.append(f'- {m}: {dict(c)}')
if by_agree:
    lines += ['', '## Theo khớp metric/SQL (agree)', '']
    for k, c in sorted(by_agree.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f'- {k}: {dict(c)}')

reports = sorted(run.rglob('report_*.md'))
if reports:
    lines += ['', '## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)', '']
    seen = set()
    for f in reports:
        if f.name in seen:                       # same report downloaded loose and inside v6_state.zip
            continue
        seen.add(f.name)
        lines += [f'### {f.stem}', '', f.read_text(encoding='utf-8').split('```json')[0].strip(), '']
g = res_dirs[main_name] / 'grouped_eval.json'
if g.exists():                                   # v5 notebook output
    ge = json.loads(g.read_text())
    lines += ['', '## Giữ kín theo shop (sau ngưỡng)', '', '```',
              json.dumps({k: (v if k == 'raw' else v['with_policy']) for k, v in ge.items()}, indent=1), '```']
lines += ['', '## Câu sai / bỏ trống', ''] + errors

text = '\n'.join(lines)
(run / 'errors.md').write_text(text, encoding='utf-8')
head = lines[:summary_end + 4 + min(len(by_metric), 12)]
print('\n'.join(head))
for name in sorted({f.name for f in reports}):
    f = next(r for r in reports if r.name == name)
    print(f'\n### {f.stem}\n' + f.read_text(encoding='utf-8').split('```json')[0].strip())
print(f'\n→ chi tiết: {run / "errors.md"}')
