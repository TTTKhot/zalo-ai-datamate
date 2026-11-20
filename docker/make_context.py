"""Assemble the Docker build context (/code layout of the organisers' guide) from this repository + model files.

python docker/make_context.py --qwen <dir of Qwen3.5-4B> [--submit <run>/datamate_submit] [--state <run>/state]
                              [--no-lora] [--no-xlmr] [--out build/docker_context]

  --qwen    local copy of Qwen/Qwen3.5-4B (config.json, *.safetensors, tokenizer files)
  --submit  datamate_submit/ of a Kaggle run: models/intent_lora, models/xlmr_ans, calibration.json
  --state   state/ of the same run: sft/ (LoRA training data), train logs, reports, splits (training evidence)
Writes build/docker_context/{Dockerfile, .dockerignore, requirements.txt, predict.sh, README.md, calibration.json,
src/, models/, training_code/} and training_code/data_manifest.json (sizes + SHA-256 of every packaged file).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'docker'
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', 'checkpoint*', '*.tmp')
BASE_MODELS = {
    'Qwen3.5-4B': dict(source='https://huggingface.co/Qwen/Qwen3.5-4B', revision='851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a',
                       released='2026-02-27', license='Apache-2.0', params=4_659_865_088,
                       role='intent JSON, SQL cross-check, table-mapping check (fp16)'),
    'xlmr_ans': dict(source='https://huggingface.co/FacebookAI/xlm-roberta-base',
                     revision='e73636d4f797dec63c3081bb6ed5c7b0bb3f2089', released='2019-11 (paper), HF 2022-03-02',
                     license='MIT', params=278_045_955, role='fine-tuned classifier P(answerable | question, shop)'),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def copy(src: Path, dst: Path):
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def manifest(ctx: Path, roots: list[str]) -> list[dict]:
    rows = []
    for r in roots:
        base = ctx / r
        for f in sorted(p for p in base.rglob('*') if p.is_file()) if base.exists() else []:
            rows.append({'path': '/code/' + f.relative_to(ctx).as_posix(), 'bytes': f.stat().st_size, 'sha256': sha256(f)})
    return rows


def count_params(folder: Path) -> int:
    """Exact parameter count from the safetensors headers of a model folder (0 if none)."""
    import struct
    total = 0
    for f in folder.glob('*.safetensors'):
        with f.open('rb') as fh:
            n = struct.unpack('<Q', fh.read(8))[0]
            header = json.loads(fh.read(n))
        for k, v in header.items():
            if k != '__metadata__':
                p = 1
                for d in v['shape']:
                    p *= d
                total += p
    return total


def count_lines(p: Path) -> int:
    return sum(1 for l in p.read_text(encoding='utf-8').splitlines() if l.strip()) if p.exists() else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qwen', required=True)
    ap.add_argument('--submit', default='')
    ap.add_argument('--state', default='')
    ap.add_argument('--no-lora', action='store_true')
    ap.add_argument('--no-xlmr', action='store_true')
    ap.add_argument('--out', default=str(ROOT / 'build' / 'docker_context'))
    a = ap.parse_args()
    ctx = Path(a.out)
    if ctx.exists():
        shutil.rmtree(ctx)
    ctx.mkdir(parents=True)
    t0 = time.time()

    # inference part
    for name in ('Dockerfile', '.dockerignore', 'requirements.txt'):
        copy(HERE / name, ctx / name)
    copy(ROOT / 'predict.sh', ctx / 'predict.sh')
    (ctx / 'predict.sh').write_bytes((ctx / 'predict.sh').read_bytes().replace(b'\r\n', b'\n'))
    copy(ROOT / 'datamate', ctx / 'src' / 'datamate')
    qwen = Path(a.qwen)
    assert (qwen / 'config.json').exists() and list(qwen.glob('*.safetensors')), f'{qwen}: no config.json / *.safetensors'
    copy(qwen, ctx / 'models' / 'Qwen3.5-4B')
    sub = Path(a.submit) if a.submit else None
    used = ['Qwen3.5-4B']
    if sub and (sub / 'models' / 'intent_lora').exists() and not a.no_lora:
        copy(sub / 'models' / 'intent_lora', ctx / 'models' / 'intent_lora')
        used.append('intent_lora')
    if sub and (sub / 'models' / 'xlmr_ans').exists() and not a.no_xlmr:
        copy(sub / 'models' / 'xlmr_ans', ctx / 'models' / 'xlmr_ans')
        used.append('xlmr_ans')
    cal = sub / 'calibration.json' if sub and (sub / 'calibration.json').exists() else ROOT / 'calibration.json'
    copy(cal, ctx / 'calibration.json')

    # training part (code, data, evidence)
    tc = ctx / 'training_code'
    copy(ROOT / 'datamate', tc / 'src' / 'datamate')
    for f in ('tests', 'notebooks', 'kaggle', 'sqlvote'):
        if (ROOT / f).exists():
            copy(ROOT / f, tc / 'src' / f)
    copy(ROOT / 'requirements.txt', tc / 'requirements.txt')
    copy(ROOT / 'data' / 'train', tc / 'data' / 'train')
    st = Path(a.state) if a.state else None
    if st and st.exists():
        for name in ('sft', 'split.json', 'calibration.json', 'questions_val.jsonl', 'manifest.json'):
            if (st / name).exists():
                copy(st / name, tc / 'data' / name if name != 'manifest.json' else tc / 'logs' / name)
        for f in st.glob('report_*.md'):
            copy(f, tc / 'logs' / f.name)
        for f in st.rglob('train_log.json'):
            copy(f, tc / 'logs' / f'{f.parent.name}_train_log.json')
        for d in st.glob('results_*'):
            copy(d, tc / 'logs' / 'calibration_evidence' / d.name)
    for m in ('intent_lora', 'xlmr_ans'):
        cfgs = [p for p in (ctx / 'models' / m).glob('*.json')] if (ctx / 'models' / m).exists() else []
        for p in cfgs:
            copy(p, tc / 'configs' / m / p.name)
    copy(ROOT / 'kaggle' / 'config.json', tc / 'configs' / 'kaggle_config.json')
    sft_train = tc / 'data' / 'sft' / 'train.jsonl'
    n_train, n_val = count_lines(sft_train), count_lines(tc / 'data' / 'sft' / 'val.jsonl')
    trained = 'intent_lora' in used or 'xlmr_ans' in used
    (tc / 'train.sh').write_text(TRAIN_SH, encoding='utf-8', newline='\n')
    (tc / 'README.md').write_text(TRAIN_README.format(
        lora='yes' if 'intent_lora' in used else 'no (not packaged, not used at inference)',
        xlmr='yes' if 'xlmr_ans' in used else 'no (not packaged, not used at inference)',
        n_train=n_train, n_val=n_val,
        none='' if trained else '\n**No model was fine-tuned for this image**: only base Qwen3.5-4B weights are used; '
                                 'the calibration table is the only fitted artifact.\n'), encoding='utf-8')

    # README of /code
    rows = ['| Model | Folder | Public source | Revision | Original release | License | Parameters | Role |',
            '|---|---|---|---|---|---|---|---|']
    total = 0
    for m in used:
        n = count_params(ctx / 'models' / m)
        if m == 'intent_lora':
            rows.append(f'| LoRA adapter (r=16) on Qwen3.5-4B | `models/intent_lora` | trained by us (training_code) | — | '
                        f'— | Apache-2.0 (base) | {n / 1e9:.3f} B | intent JSON step only; off for mapping and SQL |')
            total += n
            continue
        b = BASE_MODELS[m]
        n = n or b['params']
        rows.append(f"| {m if m != 'xlmr_ans' else 'XLM-RoBERTa base (fine-tuned)'} | `models/{m}` | {b['source']} | "
                    f"`{b['revision'][:12]}` | {b['released']} | {b['license']} | {n / 1e9:.3f} B | {b['role']} |")
        total += n
    data_text = (f'LoRA training pairs (question → intent JSON verified against the gold answer), {n_train} train / '
                 f'{n_val} validation rows, made by `datamate/sft_data.py` (+ `datamate/augment.py` variants), in '
                 '`training_code/data/sft/`.') if n_train else 'none.'
    readme = (HERE / 'README_code.md').read_text(encoding='utf-8')
    readme = readme.replace('__MODEL_TABLE__', '\n'.join(rows)).replace('__TOTAL_PARAMS__', f'{total / 1e9:.2f} B') \
                   .replace('__DATA_TEXT__', data_text)
    (ctx / 'README.md').write_text(readme, encoding='utf-8')

    # manifest (paths, sizes, SHA-256, sources)
    files = manifest(ctx, ['models', 'training_code/data', 'training_code/logs', 'training_code/configs'])
    qs = [json.loads(l) for l in (tc / 'data' / 'train' / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    man = {'created': time.strftime('%Y-%m-%d %H:%M'), 'base_models': {m: BASE_MODELS[m] for m in used if m in BASE_MODELS},
           'datasets': {'train (provided by the organisers)': {'path': '/code/training_code/data/train',
                                                               'shops': len({q['business_id'] for q in qs}), 'questions': len(qs)},
                        'sft (self-generated)': {'path': '/code/training_code/data/sft', 'train_rows': n_train, 'val_rows': n_val}},
           'files': files}
    (tc / 'data_manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    size = sum(f['bytes'] for f in files)
    print(f'context: {ctx}  models: {used}  files hashed: {len(files)} ({size / 1e9:.2f} GB)  {time.time() - t0:.0f}s')


TRAIN_SH = """#!/usr/bin/env bash
# Reproduce the trained artifacts (GPU: Kaggle T4 x2 was used; ~4-7 h). Same steps as notebooks/datamate_v6_kaggle.ipynb.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$HERE/src"
TRAIN="$HERE/data/train"; OUT=${OUT:-/tmp/datamate_train}; QWEN=${QWEN:-/code/models/Qwen3.5-4B}
mkdir -p "$OUT"
# 1. LoRA training data: intent labels verified against the gold answers (+ surface variants), split by shop
python -m datamate.sft_data --train-root "$TRAIN" --answers "$TRAIN/answers.jsonl" --out "$OUT/sft" --augment 2 --seed 0
# 2. LoRA on the intent step (QLoRA 4-bit NF4, r=16, alpha=32, lr 2e-4, 1 epoch, seed 0)
python -m datamate.train_lora --model "$QWEN" --train "$OUT/sft/train.jsonl" --val "$OUT/sft/val.jsonl" \\
       --noise-val "$OUT/sft/val_noise.jsonl" --out "$OUT/intent_lora" --epochs 1 --limit 3000 --seed 0
# 3. predictions on the validation shops, scoring, XLM-R answerability and the calibration table:
#    see notebooks/build_notebook.py sections 3-8 (python -m datamate.predict / score_run / answerability / calibration)
"""

TRAIN_README = """# Training code and data

Everything needed to rebuild the fitted parts of the image. Code: `src/datamate/` (same package as inference),
`src/notebooks/build_notebook.py` (generates the Kaggle notebook that ran every step), `src/kaggle/` (run scripts),
`src/tests/` (tests; `tests/scripted_intent.py` is a rule parser used ONLY to seed training labels, never at inference).
Dependencies: `requirements.txt` (+ torch 2.x, transformers==5.20.2, bitsandbytes for 4-bit training).
Hardware used: Kaggle, 2 x NVIDIA T4 16 GB. Seeds: 0. Nondeterminism: GPU kernels in training.
{none}
| Artifact | Packaged / used |
|---|---|
| LoRA adapter `models/intent_lora` | {lora} |
| XLM-R classifier `models/xlmr_ans` | {xlmr} |
| Calibration table `calibration.json` | yes (fitted on the predictions of held-out train shops) |

## Data
- `data/train/`: the provided training split (business files, questions.jsonl, answers.jsonl, rulebook.md, calendar.csv).
- `data/sft/`: self-generated LoRA pairs: {n_train} train / {n_val} validation rows (validation = held-out shops).
  Built by `python -m datamate.sft_data`: an intent JSON is kept only if the metric library computes the gold answer
  from it; `datamate/augment.py` adds surface variants (no accents, abbreviations, telex, filler) with the label unchanged.
- `data/split.json`, `data/questions_val.jsonl`: shop split and validation questions (when present).
- `data_manifest.json`: path, size and SHA-256 of every packaged file; public URL + revision of base models.

## Commands
`bash train.sh` (steps 1-2), then the notebook sections listed in it. Logs of our run: `logs/`
(`*_train_log.json`: loss, exact match per noise family; `report_*.md`; `calibration_evidence/`: scored predictions
used to fit `calibration.json`).
"""

if __name__ == '__main__':
    main()
