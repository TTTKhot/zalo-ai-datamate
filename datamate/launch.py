"""Run datamate.predict on every GPU of the machine and keep /result/submission.jsonl up to date.

Called by /code/predict.sh (no arguments, fixed settings). Shops are split between GPUs (balanced by number of
questions, one process per GPU, CUDA_VISIBLE_DEVICES set per process; no NCCL, no tensor parallelism). Each process
writes its own part file line by line; this launcher merges the parts into submission.jsonl every few seconds
(atomic replace) so answers already computed are saved if the run is stopped, and once more at the end, where every
question without an answer is written as abstain.
Every merge applies the two general guards of apply_guards (whole-shop abstain, unanswerable -> abstain).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .runstate import read_jsonl_tolerant


def gpu_count() -> int:
    try:
        import torch
        return torch.cuda.device_count()
    except Exception:
        return 0


def split_shops(questions: list, n: int) -> list[list[str]]:
    """Greedy balance of shops over n workers by number of questions (largest first, stable)."""
    counts = {}
    for q in questions:
        counts[q['business_id']] = counts.get(q['business_id'], 0) + 1
    groups, load = [[] for _ in range(n)], [0] * n
    for biz in sorted(counts, key=lambda b: (-counts[b], b)):
        i = min(range(n), key=lambda k: (load[k], k))
        groups[i].append(biz)
        load[i] += counts[biz]
    return [g for g in groups if g]


UNANSWERABLE_CAP = 0.2      # set on train: the real share of unanswerable questions per train shop is at most 10.2%


def apply_guards(questions: list, got: dict, cap: float = UNANSWERABLE_CAP, gated=frozenset()):
    """Two general guards on the merged answers (measured on shops never seen in training):
      1. a shop where more than `cap` of its questions come out "unanswerable" was read wrong (tables mapped to the
         wrong roles): abstain on the whole shop. The share is taken over the questions the pipeline really evaluated:
         `gated` ids (stopped earlier by the rulebook gate) are left out, else a shop with many gated questions
         hides its unanswerable share and slips under the cap;
      2. every remaining "unanswerable" -> abstain (its precision on unseen shops is far below 50%, a wrong one is -1).
    Returns (answers by id, {id: reason} of the answers turned into abstain, blocked shops). `got` is not changed."""
    total, unans = {}, {}
    for q in questions:
        biz = q['business_id']
        total.setdefault(biz, 0), unans.setdefault(biz, 0)
        if q['id'] in gated:
            continue
        total[biz] += 1
        unans[biz] = unans.get(biz, 0) + ((got.get(q['id']) or {}).get('type') == 'unanswerable')
    blocked = {b for b in total if total[b] and unans[b] / total[b] > cap}
    out, why = {}, {}
    for q in questions:
        r = got.get(q['id'])
        if r is None:
            continue
        if r.get('type') != 'abstain' and q['business_id'] in blocked:
            why[q['id']] = (f"shop guard: {unans[q['business_id']]}/{total[q['business_id']]} evaluated questions of this shop "
                            f"came out unanswerable (> {cap:.0%}) - the shop's tables were probably read wrong")
        elif r.get('type') == 'unanswerable':
            why[q['id']] = 'unanswerable guard: "unanswerable" is not reliable on unseen shops - abstain'
        out[q['id']] = {'id': q['id'], 'type': 'abstain'} if q['id'] in why else r
    return out, why, blocked


_GATED, _SEEN = set(), set()


def gated_ids(questions: list, got: dict, log_dir: Path | None) -> set:
    """Ids stopped by the rulebook gate of datamate.predict (log field route == 'rule_gate'); found once, then cached."""
    if log_dir is None:
        return set()
    for q in questions:
        r = got.get(q['id'])
        if r is None or r.get('type') != 'abstain' or q['id'] in _SEEN:
            continue
        _SEEN.add(q['id'])                         # predict writes the log before the answer line: read once
        try:
            log = json.loads((log_dir / q['business_id'] / f"{q['id']}.json").read_text(encoding='utf-8'))
            if log.get('route') == 'rule_gate':
                _GATED.add(q['id'])
        except Exception:
            pass
    return _GATED


def annotate_logs(questions: list, log_dir: Path, why: dict) -> None:
    """The per-question log must show the FINAL answer: keep the pipeline's own line in `answer_before_guard`."""
    biz = {q['id']: q['business_id'] for q in questions}
    for qid, reason in why.items():
        f = log_dir / biz[qid] / f'{qid}.json'
        try:
            log = json.loads(f.read_text(encoding='utf-8'))
            if 'guard' not in log:
                log['answer_before_guard'] = log.get('answer')
            log['answer'], log['guard'] = {'type': 'abstain'}, reason
            tmp = f.with_name(f.name + '.tmp')
            tmp.write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
            os.replace(tmp, f)
        except Exception as exc:                       # a missing / torn log must not stop the run
            print(f'[launch] log of {qid} not annotated: {exc!r}', flush=True)


def merge(questions: list, parts: list[Path], out: Path, final: bool, log_dir: Path | None = None,
          gate_on: bool = False) -> int:
    got = {}
    for p in parts:
        rows, _ = read_jsonl_tolerant(p) if p.exists() else ([], 0)
        for r in rows:
            if isinstance(r, dict) and r.get('id'):
                got[r['id']] = r
    gated = gated_ids(questions, got, log_dir) if gate_on else frozenset()   # gate off (default): nothing to leave out
    guarded, why, blocked = apply_guards(questions, got, gated=gated)
    lines = []
    for q in questions:
        if q['id'] in guarded:
            lines.append(guarded[q['id']])
        elif final:
            lines.append({'id': q['id'], 'type': 'abstain'})
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_text(''.join(json.dumps(r, ensure_ascii=False, default=str) + '\n' for r in lines), encoding='utf-8')
    os.replace(tmp, out)
    if final:
        print(f'[launch] guards: {len(why)} answers -> abstain, shops blocked: {sorted(blocked)}', flush=True)
        (out.parent / 'guards.json').write_text(json.dumps({'cap': UNANSWERABLE_CAP, 'blocked_shops': sorted(blocked),
                                                            'abstained': why}, ensure_ascii=False, indent=1), encoding='utf-8')
        if log_dir is not None:
            annotate_logs(questions, log_dir, why)
    return len(got)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', default='/data')
    ap.add_argument('--out-dir', default='/result')
    ap.add_argument('--model', required=True)
    ap.add_argument('--gpus', type=int, default=-1, help='-1: all visible GPUs')
    ap.add_argument('--every', type=float, default=15.0, help='seconds between merges')
    ap.add_argument('predict_args', nargs=argparse.REMAINDER, help='extra arguments for datamate.predict (after --)')
    a = ap.parse_args(argv)
    started = time.time()
    data, out_dir = Path(a.data_root), Path(a.out_dir)
    qfile = data / 'questions.jsonl'
    questions = [json.loads(l) for l in qfile.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'logs').mkdir(exist_ok=True)
    parts_dir = out_dir / 'parts'
    parts_dir.mkdir(exist_ok=True)
    n = gpu_count() if a.gpus < 0 else a.gpus
    groups = split_shops(questions, max(n, 1))
    extra = [x for x in a.predict_args if x != '--']
    gate_on = '--rule-gate' in extra and '--no-rule-gate' not in extra     # rulebook gate of datamate.predict, off by default
    print(f'[launch] {len(questions)} questions, {len({q["business_id"] for q in questions})} shops, '
          f'{n} GPU(s) -> {len(groups)} process(es)', flush=True)
    procs, parts = [], []
    for i, shops in enumerate(groups):
        part = parts_dir / f'submission.gpu{i}.jsonl'
        parts.append(part)
        env = dict(os.environ)
        if n > 0:
            env['CUDA_VISIBLE_DEVICES'] = str(i)
        cmd = [sys.executable, '-u', '-m', 'datamate.predict', '--data-root', str(data), '--questions', str(qfile),
               '--model', a.model, '--out', str(part), '--log-dir', str(out_dir / 'logs'), '--businesses', *shops, *extra]
        logf = open(out_dir / f'predict.gpu{i}.log', 'w', encoding='utf-8')
        procs.append((subprocess.Popen(cmd, env=env, stdout=logf, stderr=subprocess.STDOUT), logf))
        print(f'[launch] process {i}: {len(shops)} shops', flush=True)
    out = out_dir / 'submission.jsonl'
    while any(p.poll() is None for p, _ in procs):
        time.sleep(a.every)
        done = merge(questions, parts, out, final=False, log_dir=out_dir / 'logs', gate_on=gate_on)
        print(f'[launch] {done}/{len(questions)} answers saved, {time.time() - started:.0f}s', flush=True)
    codes = [p.returncode for p, _ in procs]
    for _, f in procs:
        f.close()
    done = merge(questions, parts, out, final=True, log_dir=out_dir / 'logs', gate_on=gate_on)
    print(f'[launch] done: {done}/{len(questions)} answered by the pipeline, exit codes {codes}, '
          f'total {time.time() - started:.0f}s', flush=True)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == '__main__':
    sys.exit(main())
