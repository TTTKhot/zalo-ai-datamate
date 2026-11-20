"""One Kaggle round trip (v6): push code -> run notebooks/datamate_v6_kaggle.ipynb on GPU -> wait
-> download v6_state.zip + state/report_*.md -> summary (kaggle/analyze_run.py).

python kaggle/kaggle_cycle.py -m "mô tả"            # full cycle with kaggle/config.json
python kaggle/kaggle_cycle.py --only fetch          # just download + summarise the last run
python kaggle/kaggle_cycle.py --only list           # list output files of the last run (no download)
python kaggle/kaggle_cycle.py --biz biz_101 biz_103 --max 40 --step lora_train=0 xlmr=0   # override config
python kaggle/kaggle_cycle.py --quick -m "..."      # handoff quick mode: 40 câu/shop val, LoRA limit 800, 1 epoch

Config (kaggle/config.json) -> variables of the notebook's config cell ("# ==== 0. CẤU HÌNH"):
  business_ids -> BUSINESS_IDS          val_frac -> VAL_FRAC        val_shops -> VAL_SHOPS
  max_q_per_shop_eval -> MAX_Q_PER_SHOP_EVAL   quantize_4bit -> QUANTIZE_4BIT
  use_llm_mapper -> USE_LLM_MAPPER      run -> RUN (merged)          lora -> LORA (merged)
Overrides are appended at the end of that cell, so the notebook's defaults stay readable.
Extra inputs: "kernel_sources" (earlier kernel outputs, e.g. a v5 run with run_llm/logs as SFT seeds),
"extra_datasets" (e.g. a dataset holding an earlier v6 state/ to continue from).

Needs: pip install -U kaggle, token in ~/.kaggle (Kaggle → Settings → API Tokens),
and "kaggle_username" in kaggle/config.json.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KDIR = ROOT / 'kaggle'
BUILD = ROOT / '.kaggle_build'
RUNS = ROOT / 'runs'
NOTEBOOK = ROOT / 'notebooks' / 'datamate_v6_kaggle.ipynb'
CONFIG_CELL_MARK = 'CẤU HÌNH'

# config.json key -> notebook variable
SCALAR_VARS = {'business_ids': 'BUSINESS_IDS', 'val_frac': 'VAL_FRAC', 'val_shops': 'VAL_SHOPS',
               'max_q_per_shop_eval': 'MAX_Q_PER_SHOP_EVAL', 'quantize_4bit': 'QUANTIZE_4BIT',
               'use_llm_mapper': 'USE_LLM_MAPPER', 'hf_model_id': 'HF_MODEL_ID',
               'eval_pick': 'EVAL_PICK', 'baseline_sql': 'BASELINE_SQL', 'public_shops': 'PUBLIC_SHOPS',
               'parallel_gpus': 'PARALLEL_GPUS'}
DICT_VARS = {'run': 'RUN', 'lora': 'LORA', 'sqlvote': 'SQLVOTE'}
# output files worth downloading (paths relative to /kaggle/working); everything else (Qwen weights,
# cache, code copy, datamate_submit/) stays on Kaggle
FETCH = [r'v6_state\.zip', r'state/report_[^/]+\.md', r'public_submission\.jsonl']
FETCH_SUBMIT = [r'datamate_submit\.zip']


def sh(*args, check=True):
    print('$', ' '.join(map(str, args)), flush=True)
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out[-2000:])
    if check and r.returncode:
        sys.exit(f'command failed ({r.returncode})')
    return out


def username(cfg):
    """Kaggle username: config.json "kaggle_username", else KAGGLE_USERNAME, else legacy kaggle.json."""
    import os
    if cfg.get('kaggle_username'):
        return cfg['kaggle_username']
    if os.environ.get('KAGGLE_USERNAME'):
        return os.environ['KAGGLE_USERNAME']
    for p in (Path.home() / '.kaggle' / 'kaggle.json', Path.home() / '.config' / 'kaggle' / 'kaggle.json'):
        if p.exists():
            return json.loads(p.read_text())['username']
    sys.exit('Điền "kaggle_username" vào kaggle/config.json')


def push_code(user, cfg, msg):
    d = BUILD / 'code'
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for name in ('datamate', 'tests', 'sqlvote'):
        shutil.copytree(ROOT / name, d / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('Dockerfile', 'predict.sh', 'requirements.txt', 'calibration.json', 'README.md'):
        if (ROOT / name).exists():
            shutil.copy(ROOT / name, d / name)
    ds = f"{user}/{cfg['code_dataset']}"
    (d / 'dataset-metadata.json').write_text(json.dumps({'id': ds, 'title': cfg['code_dataset'],
                                                         'licenses': [{'name': 'CC0-1.0'}]}))
    out = sh('kaggle', 'datasets', 'version', '-p', d, '-m', msg, '--dir-mode', 'zip', check=False)
    if 'not found' in out.lower() or '404' in out:
        sh('kaggle', 'datasets', 'create', '-p', d, '--dir-mode', 'zip')
    for _ in range(60):                      # wait until the new version is processed
        status = sh('kaggle', 'datasets', 'status', ds, check=False).lower()
        if 'ready' in status:
            return
        time.sleep(10)
    print('!! dataset chưa ready sau 10 phút, vẫn tiếp tục')


def config_overrides(cfg) -> list[str]:
    lines = []
    for key, var in SCALAR_VARS.items():
        if key in cfg:
            lines.append(f'{var} = {cfg[key]!r}')
    for key, var in DICT_VARS.items():
        if cfg.get(key):
            lines.append(f'{var} = {{**{var}, **{dict(cfg[key])!r}}}')
    return lines


def patch_notebook(src: Path, dst: Path, cfg):
    nb = json.loads(src.read_text(encoding='utf-8'))
    cell = next((c for c in nb['cells'] if c['cell_type'] == 'code' and CONFIG_CELL_MARK in ''.join(c['source'])), None)
    if cell is None:
        sys.exit(f'Không thấy ô cấu hình ("{CONFIG_CELL_MARK}") trong {src.name}')
    s = ''.join(cell['source'])
    used = [var for key, var in {**SCALAR_VARS, **DICT_VARS}.items() if key in cfg]
    missing = [v for v in used if not re.search(rf'^{v}\s*=', s, re.M)]
    if missing:                              # notebook renamed a variable: fail instead of silently ignoring
        sys.exit(f'Ô cấu hình của notebook không còn biến {missing} — sửa SCALAR_VARS/DICT_VARS trong kaggle_cycle.py')
    extra = config_overrides(cfg)
    if cfg.get('_env'):                      # A/B switches read by datamate/ (predict subprocesses inherit them)
        extra.append(f'import os as _os; _os.environ.update({cfg["_env"]!r})')
    if extra:
        s = s.rstrip('\n') + '\n# ==== ghi đè từ kaggle/config.json (kaggle_cycle.py) ====\n' + '\n'.join(extra) + '\n'
        print('cấu hình notebook:\n  ' + '\n  '.join(extra))
    cell['source'] = s.splitlines(keepends=True)
    dst.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')


def push_kernel(user, cfg):
    d = BUILD / 'kernel'
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    patch_notebook(NOTEBOOK, d / 'notebook.ipynb', cfg)
    meta = {'id': f"{user}/{cfg['kernel_slug']}", 'title': cfg['kernel_slug'], 'code_file': 'notebook.ipynb',
            'language': 'python', 'kernel_type': 'notebook', 'is_private': True,
            'enable_gpu': True, 'enable_internet': True,
            'dataset_sources': [f"{user}/{cfg['code_dataset']}", cfg['train_dataset'], *cfg.get('extra_datasets', [])],
            'kernel_sources': list(cfg.get('kernel_sources', [])),
            'model_sources': [cfg['model_source']] if cfg.get('model_source') else []}
    (d / 'kernel-metadata.json').write_text(json.dumps(meta, indent=1))
    args = ['kaggle', 'kernels', 'push', '-p', d]
    if cfg.get('accelerator'):
        out = sh(*args, '--accelerator', cfg['accelerator'], check=False)
        if 'unrecognized' in out.lower() or 'error' in out.lower():
            sh(*args)                         # older CLI: default GPU
    else:
        sh(*args)


def wait(user, cfg, poll=120):
    ref = f"{user}/{cfg['kernel_slug']}"
    t0 = time.time()
    while True:
        s = sh('kaggle', 'kernels', 'status', ref, check=False).lower()
        if 'kernelworkerstatus.complete' in s or 'status "complete"' in s:
            return True
        if any(k in s for k in ('kernelworkerstatus.error', 'kernelworkerstatus.cancel', 'status "error"', 'status "cancel')):
            return False
        if 'kernelworkerstatus' not in s and 'status "' not in s:     # network timeout etc.: keep waiting
            print('!! không đọc được trạng thái (mạng?), thử lại', flush=True)
        print(f'... đang chạy {(time.time() - t0) / 60:.0f} phút', flush=True)
        time.sleep(poll)


def list_output(user, slug):
    """All output files of the latest kernel version (paged) + the kernel log, without downloading."""
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    api = KaggleApi()
    api.authenticate()
    files, log, token = [], None, None
    with api.build_kaggle_client() as k:
        while True:
            req = ApiListKernelSessionOutputRequest()
            req.user_name, req.kernel_slug = user, slug
            req.page_size = 200                # explicit paging (v6 output has thousands of log files); 1000 -> HTTP 400
            if token:
                req.page_token = token
            resp = k.kernels.kernels_api_client.list_kernel_session_output(req)
            files += list(resp.files or [])
            log = log or resp.log
            token = resp.next_page_token
            if not token:
                return files, log


def download(url, dst: Path):
    import requests
    dst.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dst, 'wb') as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def fetch(user, cfg, with_submit=False):
    stamp = time.strftime('%Y%m%d-%H%M')
    out = RUNS / stamp
    out.mkdir(parents=True, exist_ok=True)
    slug = cfg['kernel_slug']
    pats = [re.compile(p) for p in FETCH + (FETCH_SUBMIT if with_submit else [])]
    try:
        files, log = list_output(user, slug)
    except Exception as exc:                  # API changed: fall back to the CLI (downloads everything)
        print('!! không liệt kê được output qua API:', repr(exc), '→ tải toàn bộ bằng CLI')
        sh('kaggle', 'kernels', 'output', f'{user}/{slug}', '-p', out, check=False)
        files, log = [], None
    if log:
        (out / f'{slug}.log').write_text(log, encoding='utf-8')
    for item in files:
        name = item.file_name.replace('\\', '/')
        if any(p.fullmatch(name) for p in pats):
            print('tải', name, flush=True)
            download(item.url, out / name)
    z = out / 'v6_state.zip'
    if z.exists():
        zipfile.ZipFile(z).extractall(out)    # -> out/state/{run_*,results_*,report_*.md,sft,...}
    elif files:
        print('!! không có v6_state.zip (RUN["package"] tắt hoặc kernel lỗi trước bước đóng gói)')
    (RUNS / 'LATEST').write_text(str(out))
    return out


def parse_steps(items):
    steps = {}
    for it in items or []:
        k, _, v = it.partition('=')
        steps[k] = v.strip().lower() in ('1', 'true', 'yes', 'on', '')
    return steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['push', 'run', 'fetch', 'list'])
    ap.add_argument('--biz', nargs='*', help='BUSINESS_IDS')
    ap.add_argument('--max', type=int, help='MAX_Q_PER_SHOP_EVAL (câu mỗi shop val)')
    ap.add_argument('--val-shops', nargs='*', help='VAL_SHOPS cố định')
    ap.add_argument('--pick', choices=['first', 'last'], help='EVAL_PICK: câu đầu/cuối mỗi shop')
    ap.add_argument('--hf-model', help="HF_MODEL_ID, vd Qwen/Qwen3.5-9B")
    ap.add_argument('--sql-baseline', action='store_true', help='BASELINE_SQL: baseline chạy kèm SQL')
    ap.add_argument('--step', nargs='*', help="bật/tắt bước trong RUN, vd lora_train=0 vit5=1")
    ap.add_argument('--sqlvote', nargs='*', help="bật bước sqlvote + tham số SQLVOTE, vd limit_per_shop=4 shops=biz_101,biz_105 k=4")
    ap.add_argument('--quick', action='store_true',
                    help='chế độ nhanh của handoff v6: MAX_Q_PER_SHOP_EVAL=40, LORA limit=800 epochs=1')
    ap.add_argument('--with-submit', action='store_true', help='tải thêm datamate_submit.zip')
    ap.add_argument('--lora', nargs='*', help='ghi đè LORA, vd epochs=1 limit=3000 max_hours=3.5 augment=2')
    ap.add_argument('--public', metavar='DATASET',
                    help='chạy thêm bộ test không đáp án (dataset Kaggle riêng tư, vd thunhngl/datamate-public-test) '
                         '→ public_submission.jsonl; kèm --step public_sql=1 nếu muốn đường SQL')
    ap.add_argument('--public-shops', nargs='*', help='PUBLIC_SHOPS: chỉ các shop này của bộ test')
    ap.add_argument('--fp16', action='store_true', help='QUANTIZE_4BIT=False: Qwen fp16 như trong Docker image (4B vừa 1 T4)')
    ap.add_argument('--one-process', action='store_true',
                    help='PARALLEL_GPUS=False: một tiến trình predict thấy cả 2 GPU, Qwen chia qua 2 T4 (device_map=auto, '
                         '~29 GB như 5090 32 GB) - tránh OOM của mapper LLM trên 1 T4 16 GB (private 20/11), chậm ~2 lần')
    ap.add_argument('--kernel',help='kernel_slug khác config (chạy song song, không ghi đè output kernel đang chạy)')
    ap.add_argument('--dataset', nargs='*', help='thêm dataset Kaggle vào Add Input, vd thunhngl/datamate-lora-run7 '
                                                 '(kèm --step public_lora=1 để bộ test dùng adapter đó)')
    ap.add_argument('--env', nargs='*', default=[], metavar='KEY=VAL',
                    help='biến môi trường cho lần chạy, vd DATAMATE_README_CONVENTIONS_FIRST=1 (chạy A/B cùng code)')
    ap.add_argument('-m', '--message', default='auto')
    a = ap.parse_args()
    cfg = json.loads((KDIR / 'config.json').read_text(encoding='utf-8'))
    if a.kernel:
        cfg['kernel_slug'] = a.kernel
    if a.fp16:
        cfg['quantize_4bit'] = False
    if a.one_process:
        cfg['parallel_gpus'] = False
    if a.env:
        cfg['_env'] = dict(kv.split('=', 1) for kv in a.env)
    if a.public:
        cfg['extra_datasets'] = [*cfg.get('extra_datasets', []), a.public]
        cfg['run'] = {**cfg.get('run', {}), 'public': True}
    if a.public_shops:
        cfg['public_shops'] = a.public_shops
    if a.dataset:
        cfg['extra_datasets'] = [*cfg.get('extra_datasets', []), *a.dataset]
    if a.quick:                                # explicit --max below still wins
        cfg['max_q_per_shop_eval'] = 40
        cfg['lora'] = {**cfg.get('lora', {}), 'limit': 800, 'epochs': 1}
    if a.biz:
        cfg['business_ids'] = a.biz
    if a.max is not None:
        cfg['max_q_per_shop_eval'] = a.max
    if a.val_shops:
        cfg['val_shops'] = a.val_shops
    if a.pick:
        cfg['eval_pick'] = a.pick
    if a.hf_model:
        cfg['hf_model_id'] = a.hf_model
    if a.sql_baseline:
        cfg['baseline_sql'] = True
    if a.sqlvote is not None:
        cfg['run'] = {**cfg.get('run', {}), 'sqlvote': True}
        sv = {}
        for it in a.sqlvote:
            key, _, v = it.partition('=')
            sv[key] = int(v) if v.lstrip('-').isdigit() else v
        cfg['sqlvote'] = {**cfg.get('sqlvote', {}), **sv}
    if a.lora:
        lo = {}
        for it in a.lora:
            key, _, v = it.partition('=')
            try:
                lo[key] = int(v) if v.lstrip('-').isdigit() else float(v)
            except ValueError:
                lo[key] = v
        cfg['lora'] = {**cfg.get('lora', {}), **lo}
    if a.step:
        cfg['run'] = {**cfg.get('run', {}), **parse_steps(a.step)}
    user = username(cfg)
    if a.only == 'list':
        files, log = list_output(user, cfg['kernel_slug'])
        for f in files:
            print(f.file_name)
        print(len(files), 'file; log', 'có' if log else 'không')
        return
    if a.only in (None, 'push'):
        push_code(user, cfg, a.message)
    if a.only in (None, 'run'):
        push_kernel(user, cfg)
        ok = wait(user, cfg)
        print('Kernel', 'xong' if ok else 'LỖI — xem file .log trong runs/<thời gian>/')
    if a.only in (None, 'run', 'fetch'):
        out = fetch(user, cfg, a.with_submit)
        sh(sys.executable, ROOT / 'kaggle' / 'analyze_run.py', out, check=False)


if __name__ == '__main__':
    main()
