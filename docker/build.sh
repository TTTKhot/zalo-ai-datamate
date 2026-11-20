#!/usr/bin/env bash
# Build, check and export the submission image (run in Git Bash on Windows, or any bash with docker).
#   bash docker/build.sh <team_name> [public_test_dir]
# Steps: docker build -> inspect -> layout -> import check offline -> plumbing smoke test on the public test with a
# FAKE model (no GPU on this machine: checks reading /data read-only, logs, submission format, no network)
# -> docker save | gzip -> uncompressed size + MD5 (files in build/export/).
set -euo pipefail
export MSYS_NO_PATHCONV=1                       # keep /data, /result, /code paths as they are in Git Bash
TEAM=${1:?usage: bash docker/build.sh <team_name> [public_test_dir]}
PUBLIC=${2:-public_test/public_test}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CTX="$ROOT/build/docker_context"
IMG="zaic2026_datamate_${TEAM}:final"
EXP="$ROOT/build/export"
win() { if command -v cygpath >/dev/null; then cygpath -m "$1"; else echo "$1"; fi; }
[ -f "$CTX/Dockerfile" ] || { echo "chưa có $CTX - chạy python docker/make_context.py trước"; exit 1; }

echo "== 1. build $IMG"
docker build --platform linux/amd64 -t "$IMG" "$(win "$CTX")"
docker image inspect -f '{{.Os}}/{{.Architecture}} {{.Size}}' "$IMG"
docker run --rm --network none --entrypoint "" "$IMG" find /code -maxdepth 2 -not -path '/code/models/*/*' | sort

echo "== 2. thư viện và cấu hình (offline)"
docker run --rm --network none --entrypoint "" "$IMG" python -c "
import torch, transformers, json
print('torch', torch.__version__, 'cuda build', torch.version.cuda, 'arch list', torch.cuda.get_arch_list() if torch.cuda.is_available() else '(no GPU here)')
from transformers import AutoConfig
c = AutoConfig.from_pretrained('/code/models/Qwen3.5-4B', local_files_only=True)
print('Qwen config ok:', type(c).__name__)
import importlib.util, torch.nn as nn, peft
from peft import LoraConfig, get_peft_model
print('peft', peft.__version__, '| torchao cài:', importlib.util.find_spec('torchao') is not None)
get_peft_model(nn.Sequential(nn.Linear(8, 8)), LoraConfig(target_modules=['0'], r=2))   # torchao cũ làm bước này lỗi (Kaggle 14/11)
print('gắn LoRA lên lớp Linear fp: ok')
"

echo "== 3. chạy thử đường ống trên public test với model GIẢ (không mạng, /data chỉ đọc)"
OUT="$ROOT/build/smoke_result"
rm -rf "$OUT"; mkdir -p "$OUT"
docker run --rm --network none --shm-size=16g --entrypoint bash \
    -e DATAMATE_TEST_BACKEND=fake_backend:FakeQwen -e DATAMATE_TEST_DATA=/data \
    -e PYTHONPATH=/code/training_code/src/tests \
    -v "$(win "$ROOT/$PUBLIC"):/data:ro" -v "$(win "$OUT"):/result" "$IMG" /code/predict.sh
python - "$(win "$OUT")" "$(win "$ROOT/$PUBLIC/questions.jsonl")" <<'PY'      # Windows python: E:/..., not /e/...
import json, sys, pathlib
out, qf = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
qs = [json.loads(l) for l in qf.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
sub = [json.loads(l) for l in (out / 'submission.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
assert [s['id'] for s in sub] == [q['id'] for q in qs], 'submission không đủ / sai thứ tự câu'
bad = 0
for q in qs:
    f = out / 'logs' / q['business_id'] / f"{q['id']}.json"
    log = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    bad += not all(k in log for k in ('id', 'answer', 'elapsed_ms', 'thinking'))
types = {}
for s in sub:
    types[s['type']] = types.get(s['type'], 0) + 1
print(f'submission: {len(sub)} câu {types}; log thiếu trường bắt buộc: {bad}')
assert bad == 0
PY

echo "== 4. xuất file nộp (lâu: ~15-30 phút)"
mkdir -p "$EXP"
cd "$EXP"
set -o pipefail
docker save "$IMG" | gzip > "zaic2026_datamate_${TEAM}.tar.gz"
md5sum "zaic2026_datamate_${TEAM}.tar.gz" > "zaic2026_datamate_${TEAM}.tar.gz.md5"
SIZE=$(gzip -dc "zaic2026_datamate_${TEAM}.tar.gz" | wc -c)
echo "$SIZE" > "zaic2026_datamate_${TEAM}.tar.size"
ls -l "zaic2026_datamate_${TEAM}".*
echo "MD5: $(cat "zaic2026_datamate_${TEAM}.tar.gz.md5")"
echo "kích thước .tar chưa nén (byte): $SIZE  (giới hạn 100 GB)"
