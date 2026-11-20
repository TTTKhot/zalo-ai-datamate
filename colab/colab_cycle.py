"""One Colab round trip (v6) — the Colab twin of kaggle/kaggle_cycle.py, for smoke tests and small runs.

python colab/colab_cycle.py --smoke -m "mô tả"                 # biz_101, 5 câu, không LoRA/XLM-R
python colab/colab_cycle.py --biz biz_101 biz_103 --max 20 --step lora_train=0 xlmr=0 -m "..."
python colab/colab_cycle.py --only fetch -s dm-20261113-1500   # tải lại state từ session còn sống (--keep-vm)

Flow:
  1. patch notebooks/datamate_v6_kaggle.ipynb exactly like kaggle_cycle.py (config cell overrides from
     kaggle/config.json + CLI flags), turn its code cells into one script, /kaggle/* -> /content/*;
  2. `colab run --gpu T4 --keep -s <name>` that script. The script prints READY_MARK as soon as it runs
     (= a T4 VM was granted) and then waits for the input bundle;
  3. if READY_MARK does not appear within --gpu-wait seconds (default 300) or `colab run` fails before
     it, stop the session and fall back to kaggle/kaggle_cycle.py with the same settings;
  4. upload bundle.zip (code + train data of the selected shops only), the script unzips it to
     /content/input and runs the notebook cells. Qwen is downloaded from Hugging Face on every run
     (no Drive cache): the notebook's local_or_download() finds no local copy and calls snapshot_download;
  5. download /content/work/v6_state.zip -> runs/<stamp>/ (extracted to state/, like Kaggle), the full
     stdout -> runs/<stamp>/<session>.log, write runs/LATEST, `colab stop`, run kaggle/analyze_run.py.
  So analyze_run.py and replay.py read Colab runs exactly like Kaggle runs.

A failing cell does not abort the run: the error is printed, later cells still run, state/ is always
zipped, and the exit code is non-zero. Needs `colab` CLI on PATH (or ~/.local/bin) and a logged-in account.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kaggle'))
import kaggle_cycle as kc  # noqa: E402  (same notebook patching / step parsing as Kaggle)

BUILD = ROOT / '.colab_build'
RUNS = ROOT / 'runs'
TRAIN = Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train'))
READY_MARK = '@@DATAMATE_COLAB_READY@@'
REMOTE_BUNDLE = '/content/bundle.zip'
REMOTE_OK = '/content/bundle.ok'
REMOTE_STATE = '/content/work/v6_state.zip'
CODE_FILES = ('Dockerfile', 'predict.sh', 'requirements.txt', 'calibration.json', 'README.md')
TRAIN_FILES = ('questions.jsonl', 'answers.jsonl', 'calendar.csv', 'rulebook.md')
SMOKE = dict(business_ids=['biz_101'], val_shops=['biz_101'], max_q_per_shop_eval=5,
             run=dict(scripted=False, sft=True, baseline=True, lora_train=False, lora_eval=False,
                      xlmr=False, vit5=False, package=True))
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}


def colab_exe() -> str:
    exe = shutil.which('colab') or str(Path.home() / '.local' / 'bin' / ('colab.exe' if os.name == 'nt' else 'colab'))
    if not Path(exe).exists():
        sys.exit('Không thấy Colab CLI (pip install google-colab-cli)')
    return exe


def colab(*args, check=True):
    print('$ colab', ' '.join(map(str, args)), flush=True)
    r = subprocess.run([colab_exe(), *map(str, args)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV)
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out[-2000:])
    if check and r.returncode:
        raise RuntimeError(f'colab {args[0]} failed ({r.returncode})')
    return out


# ---------------------------------------------------------------- build
REMOTE_HEAD = r'''
import os, sys, time, zipfile, traceback, subprocess
print(%(mark)r, flush=True)
try:
    print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                         capture_output=True, text=True).stdout.strip(), flush=True)
except Exception as exc:
    print('nvidia-smi:', exc)
t0 = time.time()
while not os.path.exists(%(ok)r):
    if time.time() - t0 > 1800:
        raise SystemExit('bundle chưa được upload sau 30 phút')
    time.sleep(5)
os.makedirs('/content/input', exist_ok=True)
os.makedirs('/content/work', exist_ok=True)
import glob as _glob
_parts = sorted(_glob.glob(%(bundle)r + '.part*'))
if _parts:                                   # bundle uploaded in chunks (large uploads drop on TLS errors)
    with open(%(bundle)r, 'wb') as _f:
        for _p in _parts:
            _f.write(open(_p, 'rb').read())
zipfile.ZipFile(%(bundle)r).extractall('/content/input')
print('bundle ok sau', round(time.time() - t0), 'giây', flush=True)
try:
    display
except NameError:
    display = print
_CELLS = %(cells)r
_errors = []
_G = globals()
for _i, _src in enumerate(_CELLS):
    print(f'\n===== ô {_i} =====', flush=True)
    try:
        exec(compile(_src, f'<cell {_i}>', 'exec'), _G)
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        _errors.append(_i)
import shutil
if not os.path.exists(%(state)r) and os.path.isdir('/content/work/state'):
    shutil.make_archive('/content/work/v6_state', 'zip', '/content/work', 'state')
print('ô lỗi:', _errors or 'không', flush=True)
if _errors:
    raise SystemExit(1)
'''


def build_script(cfg) -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    nb_path = BUILD / 'notebook.ipynb'
    kc.patch_notebook(kc.NOTEBOOK, nb_path, cfg)
    nb = json.loads(nb_path.read_text(encoding='utf-8'))
    cells = []
    for c in nb['cells']:
        if c['cell_type'] != 'code':
            continue
        src = ''.join(c['source']).replace('/kaggle/working', '/content/work').replace('/kaggle/input', '/content/input')
        if cfg.get('_public'):                 # phiên Colab ~1 giờ: không chờ 15 phút biên dịch causal_conv1d
            src = src.replace('timeout=900)', 'timeout=120)')
        cells.append(src)
    script = REMOTE_HEAD % dict(mark=READY_MARK, ok=REMOTE_OK, bundle=REMOTE_BUNDLE, state=REMOTE_STATE, cells=cells)
    if cfg.get('_env'):                        # A/B switches read by datamate/ (inherited by predict subprocesses)
        head = 'import os, sys, time, zipfile, traceback, subprocess\n'
        script = script.replace(head, head + f'os.environ.update({cfg["_env"]!r}); print("env", {cfg["_env"]!r})\n', 1)
    out = BUILD / 'remote_job.py'
    out.write_text(script, encoding='utf-8')
    return out


def build_bundle(cfg) -> Path:
    """code/ (like the Kaggle code dataset) + train/ restricted to the selected shops."""
    z = BUILD / 'bundle.zip'
    shops = cfg.get('business_ids') or None
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in ('datamate', 'tests', 'sqlvote'):
            for p in (ROOT / name).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                    zf.write(p, Path('code') / p.relative_to(ROOT))
        for name in CODE_FILES:
            if (ROOT / name).exists():
                zf.write(ROOT / name, Path('code') / name)
        for name in TRAIN_FILES:
            if (TRAIN / name).exists():
                zf.write(TRAIN / name, Path('train') / name)
        for d in sorted((TRAIN / 'data').iterdir()):
            if d.is_dir() and (shops is None or d.name in shops):
                for p in d.rglob('*'):
                    if p.is_file():
                        zf.write(p, Path('train') / p.relative_to(TRAIN))
        pub = cfg.get('_public')
        if pub:                                # bộ test không đáp án → public/ (notebook ô 4b: PUBLIC_ROOT)
            n = add_public(zf, Path(pub['root']), pub.get('shops'), pub.get('done') or [])
            print(f'public: {n} câu trong bundle')
    print(f'bundle {z.stat().st_size / 1e6:.1f} MB ({len(shops) if shops else "mọi"} shop)')
    return z


def add_public(zf, root: Path, shops, done_files) -> int:
    """Chỉ suy luận: questions.jsonl lọc theo shop và bỏ câu đã có trong các file submission `done_files`
    (chạy nối nhiều phiên Colab ngắn), kèm data của các shop còn câu, calendar, rulebook. Không in nội dung."""
    done = set()
    for f in done_files:
        for line in Path(f).read_text(encoding='utf-8').splitlines():
            if line.strip():
                done.add(json.loads(line)['id'])
    keep = []
    for line in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            q = json.loads(line)
            if (not shops or q['business_id'] in shops) and q['id'] not in done:
                keep.append(line)
    left = {json.loads(line)['business_id'] for line in keep}
    zf.writestr('public/questions.jsonl', '\n'.join(keep) + '\n')
    for name in ('calendar.csv', 'rulebook.md'):
        if (root / name).exists():
            zf.write(root / name, Path('public') / name)
    for d in sorted((root / 'data').iterdir()):
        if d.is_dir() and d.name in left:
            for p in d.rglob('*'):
                if p.is_file():
                    zf.write(p, Path('public') / p.relative_to(root))
    return len(keep)


# ---------------------------------------------------------------- run
def split_file(src: Path, size=8 * 1024 * 1024) -> list[Path]:
    """bundle.zip -> bundle.zip.part000, part001, ... (each uploaded on its own)."""
    for old in src.parent.glob(src.name + '.part*'):
        old.unlink()
    parts = []
    with open(src, 'rb') as f:
        while chunk := f.read(size):
            p = src.with_name(f'{src.name}.part{len(parts):03d}')
            p.write_bytes(chunk)
            parts.append(p)
    return parts


def upload_retry(session, src, dst, tries=4):
    """colab upload drops large files on transient TLS errors (SSLEOFError): retry with backoff."""
    for i in range(tries):
        try:
            return colab('upload', '-s', session, src, dst)
        except RuntimeError:
            if i == tries - 1:
                raise
            print(f'>> upload lỗi, thử lại lần {i + 2}/{tries} sau {10 * (i + 1)} giây', flush=True)
            time.sleep(10 * (i + 1))


def run_colab(script: Path, bundle: Path, session: str, log_path: Path, gpu: str, gpu_wait: int) -> str:
    """Returns 'ok' | 'failed' (ran but script errored) | 'no_gpu' (never got a VM in time)."""
    cmd = [colab_exe(), 'run', '--gpu', gpu, '--keep', '-s', session, '--timeout', '3600', str(script)]
    print('$', ' '.join(cmd), flush=True)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding='utf-8', errors='replace', env=ENV, bufsize=1)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in p.stdout] + [lines.put(None)], daemon=True).start()
    ready, uploaded, t0 = False, False, time.time()
    with open(log_path, 'w', encoding='utf-8') as log:
        while True:
            try:
                line = lines.get(timeout=5)
            except queue.Empty:
                line = ''
            if line is None:
                break
            if line:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
                if READY_MARK in line:
                    ready = True
                    print(f'>> có GPU sau {(time.time() - t0) / 60:.1f} phút', flush=True)
            if ready and not uploaded:
                uploaded = True               # the script is now polling for REMOTE_OK
                for part in split_file(bundle):
                    upload_retry(session, part, f'{REMOTE_BUNDLE}.{part.name.rsplit(".", 1)[-1]}')
                ok = BUILD / 'bundle.ok'
                ok.write_text('ok')
                upload_retry(session, ok, REMOTE_OK)
            if not ready and time.time() - t0 > gpu_wait:
                print(f'>> không xin được GPU {gpu} sau {gpu_wait // 60} phút', flush=True)
                p.kill()
                return 'no_gpu'
    rc = p.wait()
    if not ready:
        return 'no_gpu'
    return 'ok' if rc == 0 else 'failed'


def fetch(session: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    z = out / 'v6_state.zip'
    try:
        colab('download', '-s', session, REMOTE_STATE, z)
    except RuntimeError:
        # job died before packaging (lost connection, kernel crash): zip whatever state/ the VM still has
        print('!! chưa có v6_state.zip — thử nén state/ còn trên VM', flush=True)
        salvage = BUILD / 'salvage.py'
        salvage.write_text('\n'.join([
            'import os, shutil',
            "if os.path.isdir('/content/work/state'):",
            f"    shutil.make_archive({REMOTE_STATE[:-4]!r}, 'zip', '/content/work', 'state')",
            f"print('salvage', os.path.exists({REMOTE_STATE!r}))", '']), encoding='utf-8')
        try:
            colab('exec', '-s', session, '-f', salvage, '--timeout', '600')
            colab('download', '-s', session, REMOTE_STATE, z)
        except RuntimeError:
            print('!! không tải được v6_state.zip (VM đã mất?)')
    if z.exists():
        zipfile.ZipFile(z).extractall(out)   # -> out/state/{run_*,results_*,report_*.md,sft,...}
    (RUNS / 'LATEST').write_text(str(out))
    return out


def fallback_kaggle(a):
    args = [sys.executable, str(ROOT / 'kaggle' / 'kaggle_cycle.py'), '-m', f'[colab->kaggle] {a.message}']
    if a.smoke:
        args += ['--biz', *SMOKE['business_ids'], '--val-shops', *SMOKE['val_shops'],
                 '--max', str(SMOKE['max_q_per_shop_eval']),
                 '--step', *[f'{k}={int(v)}' for k, v in SMOKE['run'].items()]]
    if a.quick:
        args.append('--quick')
    if a.biz:
        args += ['--biz', *a.biz]
    if a.max is not None:
        args += ['--max', str(a.max)]
    if a.val_shops:
        args += ['--val-shops', *a.val_shops]
    if a.step:
        args += ['--step', *a.step]
    if a.pick:
        args += ['--pick', a.pick]
    if a.hf_model:
        args += ['--hf-model', a.hf_model]
    if a.sql_baseline:
        args.append('--sql-baseline')
    print('>> chuyển sang Kaggle:', ' '.join(args[1:]), flush=True)
    sys.exit(subprocess.call(args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['build', 'fetch'], help='build: chỉ tạo script+bundle; fetch: tải state từ -s')
    ap.add_argument('-s', '--session', help='tên session Colab (mặc định dm-<giờ>)')
    ap.add_argument('--smoke', action='store_true', help='biz_101, 5 câu, chỉ baseline (không LoRA/XLM-R)')
    ap.add_argument('--biz', nargs='*', help='BUSINESS_IDS (cũng giới hạn data được upload)')
    ap.add_argument('--max', type=int, help='MAX_Q_PER_SHOP_EVAL')
    ap.add_argument('--val-shops', nargs='*', help='VAL_SHOPS cố định')
    ap.add_argument('--pick', choices=['first', 'last'], help='EVAL_PICK: câu đầu/cuối mỗi shop')
    ap.add_argument('--hf-model', help="HF_MODEL_ID, vd Qwen/Qwen3.5-9B")
    ap.add_argument('--sql-baseline', action='store_true', help='BASELINE_SQL: baseline chạy kèm SQL')
    ap.add_argument('--step', nargs='*', help='bật/tắt bước trong RUN, vd lora_train=0')
    ap.add_argument('--quick', action='store_true', help='như kaggle_cycle --quick')
    ap.add_argument('--gpu', default='T4')
    ap.add_argument('--gpu-wait', type=int, default=300, help='giây chờ GPU trước khi chuyển sang Kaggle')
    ap.add_argument('--no-fallback', action='store_true', help='không chuyển sang Kaggle khi không có GPU')
    ap.add_argument('--keep-vm', action='store_true', help='không colab stop sau khi tải (để debug)')
    ap.add_argument('--public', metavar='DIR', help='thư mục bộ test không đáp án (questions.jsonl + data/) → '
                    'state/run_public/submission.jsonl; KHÔNG BAO GIỜ chuyển sang Kaggle')
    ap.add_argument('--public-shops', nargs='*', help='chỉ các shop này của bộ test')
    ap.add_argument('--public-done', nargs='*', help='file submission đã có: bỏ các câu đã trả lời (chạy nối phiên)')
    ap.add_argument('--fp16', action='store_true', help='QUANTIZE_4BIT=False (như Docker image)')
    ap.add_argument('--env', nargs='*', default=[], metavar='KEY=VAL',
                    help='biến môi trường cho lần chạy, vd DATAMATE_README_CONVENTIONS_FIRST=1 (chạy A/B cùng code)')
    ap.add_argument('-m', '--message', default='auto')
    a = ap.parse_args()

    cfg = json.loads((kc.KDIR / 'config.json').read_text(encoding='utf-8'))
    if a.smoke:
        cfg.update({k: v for k, v in SMOKE.items() if k != 'run'})
        cfg['run'] = {**cfg.get('run', {}), **SMOKE['run']}
    if a.quick:
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
    if a.step:
        cfg['run'] = {**cfg.get('run', {}), **kc.parse_steps(a.step)}
    cfg['run'] = {**cfg.get('run', {}), 'package': True}   # v6_state.zip is how results come back
    if a.fp16:
        cfg['quantize_4bit'] = False
    if a.env:
        cfg['_env'] = dict(kv.split('=', 1) for kv in a.env)
    if a.public:
        cfg['run']['public'] = True
        cfg['_public'] = {'root': a.public, 'shops': a.public_shops, 'done': a.public_done}
        a.no_fallback = True                   # không đẩy gì lên Kaggle (kernel khác đang chạy ở đó)

    stamp = time.strftime('%Y%m%d-%H%M')
    session = a.session or f'dm-{stamp}'
    out = RUNS / stamp
    if a.only == 'fetch':
        if not a.session:
            sys.exit('--only fetch cần -s <session>')
        out = fetch(session, out)
        subprocess.call([sys.executable, str(ROOT / 'kaggle' / 'analyze_run.py'), str(out)])
        return

    script, bundle = build_script(cfg), build_bundle(cfg)
    (BUILD / 'message.txt').write_text(a.message, encoding='utf-8')
    if a.only == 'build':
        print('script:', script, '| bundle:', bundle)
        return

    out.mkdir(parents=True, exist_ok=True)
    (out / 'colab_config.json').write_text(json.dumps({'message': a.message, 'session': session, **cfg},
                                                      ensure_ascii=False, indent=1), encoding='utf-8')
    status = 'no_gpu'
    try:
        status = run_colab(script, bundle, session, out / f'{session}.log', a.gpu, a.gpu_wait)
        if status != 'no_gpu':
            fetch(session, out)
    except KeyboardInterrupt:
        print('>> dừng bởi người dùng')
        raise
    finally:
        if not a.keep_vm or status == 'no_gpu':
            colab('stop', '-s', session, check=False)
    if status == 'no_gpu':
        shutil.rmtree(out, ignore_errors=True)
        if a.no_fallback:
            sys.exit('Không có GPU Colab, --no-fallback nên dừng')
        fallback_kaggle(a)
    print('Colab', 'xong' if status == 'ok' else f'LỖI — xem {out / (session + ".log")}')
    subprocess.call([sys.executable, str(ROOT / 'kaggle' / 'analyze_run.py'), str(out)])


if __name__ == '__main__':
    main()
