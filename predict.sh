#!/usr/bin/env bash
# DataMate - entry point of the Docker image: bash /code/predict.sh (no arguments).
# Reads /data (read-only), writes /result/submission.jsonl (updated while running) and one log per question in
# /result/logs/<business_id>/<id>.json (id, answer, elapsed_ms, thinking, code, inputs, output + pipeline fields).
# Every setting is fixed here: model, precision, greedy decoding (no sampling, so no seed), one process per GPU.
set -euo pipefail
CODE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA=/data
OUT=/result
MODELS="$CODE/models"
export PYTHONPATH="$CODE/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1
export HF_HOME=/tmp/hf_home MPLCONFIGDIR=/tmp/mpl
mkdir -p "$OUT/logs"

# Fixed configuration = the one measured on shops outside training (docs/HIEN_TRANG.md, 15/11): Qwen3.5-4B fp16,
# full prompt, rulebook gate OFF (16/11: the gate cost ~0.02 on the public leaderboard; `-- --rule-gate` turns it on).
# NO LoRA adapter, NO SQL route, NO calibration table, NO XLM-R, even if their files
# are in the image: each of them lowered or did not change the score on unseen shops (and SQL doubles the run time).
# The whole-shop guard and "unanswerable -> abstain" are applied by datamate.launch when it writes submission.jsonl.
# fp16 weights (no 4-bit): RTX 5090 has room for them and bitsandbytes is not needed

echo "[predict.sh] start $(date -Is) models: $(ls "$MODELS" | tr '\n' ' ')" | tee "$OUT/run.log"
python -u -m datamate.launch --data-root "$DATA" --out-dir "$OUT" --model "$MODELS/Qwen3.5-4B" \
    2>&1 | tee -a "$OUT/run.log"
echo "[predict.sh] done $(date -Is)" | tee -a "$OUT/run.log"
