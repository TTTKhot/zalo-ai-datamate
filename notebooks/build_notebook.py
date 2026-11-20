"""Generates notebooks/datamate_v6_kaggle.ipynb (python notebooks/build_notebook.py)."""
import json
from pathlib import Path

cells = []


def md(text):
    cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': text.strip('\n')})


def code(text):
    cells.append({'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': text.strip('\n')})


md('''
# DataMate v6 — LoRA ý định đã kiểm chứng + đường SQL + XLM-R trả lời được + calibration

**Input cần có** (Add Input): `datamate code` (dataset chứa `datamate_v6.zip` đã giải nén), `train_data`
(có `data/`, `questions.jsonl`, `answers.jsonl`, `calendar.csv`), tuỳ chọn model Qwen3.5-4B, tuỳ chọn
`v6_state` (output của lần chạy trước để chạy tiếp) và log Qwen cũ `run_outputs` (làm hạt giống SFT).
**Settings:** GPU T4 x2 (hoặc P100), Internet On (cài thư viện, tải XLM-R / ViT5 nếu chưa Add Input).

Mọi số "trước/sau" đều đo trên **shop giữ kín** (`val`): LoRA và XLM-R không thấy shop đó khi train,
ngưỡng bỏ trống học trên các shop *khác* (leave-one-shop-out). Thời gian ước tính (T4, 4-bit):
baseline v5 ~1 h cho ~700 câu val, train LoRA 2–3 h, chạy LoRA + SQL ~1.5 h, XLM-R ~10 phút.
Có thể chạy từng phần qua `RUN` rồi Save Version; lần sau Add Input output đó (`v6_state`) để chạy tiếp.
''')

code('''
# ==== 0. CẤU HÌNH — chỉ sửa ở đây ====
BUSINESS_IDS = []               # [] = mọi shop có đáp án
VAL_FRAC = 0.2                  # tỉ lệ shop giữ kín (chia theo hash tên shop, phân tầng theo loại dữ liệu)
VAL_SHOPS = None                # hoặc danh sách cố định, vd ['biz_105', 'biz_112', ...]
MAX_Q_PER_SHOP_EVAL = None      # vd 40 để chạy nhanh phần đánh giá
EVAL_PICK = 'first'             # 'first' | 'last': lấy MAX_Q câu đầu hay cuối mỗi shop (thứ tự questions.jsonl)
BASELINE_SQL = False            # True: bước baseline chạy thêm đường SQL (không LoRA) → results_v5 + results_v5_sql
QUANTIZE_4BIT = True
USE_LLM_MAPPER = True
PUBLIC_SHOPS = []               # [] = mọi shop của bộ test; hoặc danh sách shop (chạy thử một phần bộ test)
PARALLEL_GPUS = True            # máy "GPU T4 x2": chia shop val cho 2 tiến trình predict, mỗi tiến trình 1 GPU
RUN = dict(scripted=True, sft=True, baseline=True, lora_train=True, lora_eval=True,
           xlmr=True, vit5=False, sqlvote=False, package=True,
           public=False, public_sql=False,   # public: chạy bộ test không đáp án (Add Input) → public_submission.jsonl
           public_lora=False)   # public_lora: dùng adapter có sẵn trong Add Input (thư mục intent_lora/) cho bộ test
SQLVOTE = dict(k=4, max_tokens=500, time_budget=7200, limit_per_shop=0, shops='')  # shops: 'biz_101,biz_105' ('' = mọi shop val)   # đường tham khảo sqlvote/ (docs/sqlvote_goi_y.md)
LORA = dict(epochs=2, r=16, alpha=32, lr=2e-4, grad_accum=8, max_len=3072, limit=0, max_hours=6, augment=2)
HF_MODEL_ID = 'Qwen/Qwen3.5-4B'
XLMR_MODEL = 'FacebookAI/xlm-roberta-base'
VIT5_MODEL = 'VietAI/vit5-base'
''')

md('## 1. Đường dẫn input, chép code, khôi phục trạng thái lần trước')
code('''
import os, sys, json, glob, shutil, subprocess, time
from pathlib import Path
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
WORK, INPUT = Path('/kaggle/working'), Path('/kaggle/input')

def find_one(pattern, what):
    hits = sorted(INPUT.rglob(pattern))
    if not hits:
        raise FileNotFoundError(f'Không thấy {what} ({pattern}) trong /kaggle/input — kiểm tra Add Input')
    return hits[0]

code_src = find_one('datamate/predict.py', 'code datamate').parents[1]
CODE = WORK / 'dm'
shutil.rmtree(CODE, ignore_errors=True)
shutil.copytree(code_src, CODE)
os.chdir(CODE); sys.path.insert(0, str(CODE))
assert (CODE / 'datamate' / 'sft_data.py').exists(), 'Dataset code đang là bản CŨ — New Version với datamate_v6.zip'
_roots = [p.parent for p in sorted(INPUT.rglob('questions.jsonl')) if (p.parent / 'data').is_dir()]
TRAIN_ROOT = next(r for r in _roots if (r / 'answers.jsonl').exists())            # bộ train: có đáp án
PUBLIC_ROOT = next((r for r in _roots if not (r / 'answers.jsonl').exists()), None)   # bộ test: không có đáp án
ANSWERS = TRAIN_ROOT / 'answers.jsonl'
CACHE = WORK / 'cache'; CACHE.mkdir(exist_ok=True)
STATE = WORK / 'state'; STATE.mkdir(exist_ok=True)       # mọi thứ cần giữ giữa các phiên nằm ở đây

prev = [p for p in INPUT.rglob('state') if p.is_dir() and (p / 'sft').exists()]
if prev and not (STATE / 'sft').exists():
    shutil.copytree(prev[0], STATE, dirs_exist_ok=True)
    print('khôi phục trạng thái từ', prev[0])
QWEN_LOGS = next((str(p) for p in INPUT.rglob('run_llm/logs') if p.is_dir()), None)
from datamate.runstate import fingerprint
MANIFEST = STATE / 'manifest.json'      # chữ ký: cấu hình/dữ liệu đã sinh ra từng phần của state

def guard(name, cfg, *paths):
    """Phần `name` của state (paths) chỉ được dùng lại khi cfg trùng lúc tạo; lệch → dời sang WORK/stale để làm lại."""
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    old = man.get(name)
    if old is None or old == cfg or not any(p.exists() for p in paths):
        if old is None and any(p.exists() for p in paths):
            print(f'⚠ {name}: state cũ không có chữ ký — dùng lại, tự kiểm tra cấu hình có khớp không')
        return True
    diff = sorted(k for k in set(cfg) | set(old) if cfg.get(k) != old.get(k))
    dest = WORK / 'stale' / time.strftime('%H%M%S')
    dest.mkdir(parents=True, exist_ok=True)
    for p in paths:
        if p.exists():
            shutil.move(str(p), str(dest / p.name))
    print(f'⚠ {name}: cấu hình đổi {diff} → dời {[p.name for p in paths]} sang {dest}, làm lại')
    return False

def sign(name, cfg):
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    man[name] = cfg
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
print('CODE', CODE, '| TRAIN_ROOT', TRAIN_ROOT, '| log Qwen cũ:', QWEN_LOGS)

def sh(*args, stream=False):
    cmd = [sys.executable, *args]
    if stream:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as p:
            for line in p.stdout:
                if 'Warning' not in line and 'warn(' not in line:
                    print(line, end='')
        return p.returncode
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-6000:], r.stderr[-3000:] if r.returncode else '')
    return r.returncode
''')

md('''
## 2. Trần của thư viện (không GPU)
Parser kịch bản chỉ để đo phần đọc dữ liệu + luật + metric, và tạo cache shop cho các bước sau.
''')
code('''
questions = [json.loads(l) for l in (TRAIN_ROOT / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
gold_ids = {json.loads(l)['id'] for l in ANSWERS.read_text(encoding='utf-8').splitlines() if l.strip()}
SHOPS = sorted({q['business_id'] for q in questions if q['id'] in gold_ids and (TRAIN_ROOT / 'data' / q['business_id']).is_dir()})
if BUSINESS_IDS:
    SHOPS = [s for s in SHOPS if s in BUSINESS_IDS]
print(len(SHOPS), 'shop')
if RUN['scripted']:
    sh('tests/run_shops.py', '--train-root', str(TRAIN_ROOT), '--answers', str(ANSWERS),
       '--out', str(STATE / 'results_scripted'), '--cache', str(CACHE), *SHOPS)
''')

md('''
## 3. Bước 1a — dữ liệu SFT: chỉ giữ JSON ý định chạy ra đúng đáp án
Hạt giống: parser kịch bản (chỉ dùng lúc tạo nhãn) + log Qwen cũ nếu có; nếu sai thì thử các biến thể
cách 1–2 bước trong từ vựng ý định. Chia train/val **theo shop**.
''')
code('''
SFT = STATE / 'sft'
SFT_CFG = {'val_frac': VAL_FRAC, 'val_shops': VAL_SHOPS, 'shops': SHOPS, 'augment': LORA.get('augment', 0)}
# đổi shop val mà vẫn dùng SFT cũ = shop val lọt vào train LoRA → điểm val ảo; adapter/XLM-R/run phụ thuộc theo
if not guard('sft', SFT_CFG, SFT):
    for p in [*[STATE / d for d in ('intent_lora', 'xlmr_ans', 'ans_data', 'questions_val.jsonl')],
              *sorted(STATE.glob('run_*')), *sorted(STATE.glob('results_*'))]:
        if p.exists():
            (WORK / 'stale').mkdir(exist_ok=True); shutil.move(str(p), str(WORK / 'stale' / p.name))
if RUN['sft'] and not (SFT / 'train.jsonl').exists():
    args = ['-m', 'datamate.sft_data', '--train-root', str(TRAIN_ROOT), '--answers', str(ANSWERS), '--out', str(SFT),
            '--cache', str(CACHE), '--val-frac', str(VAL_FRAC), '--businesses', *SHOPS]
    if QWEN_LOGS: args += ['--qwen-logs', QWEN_LOGS]
    if VAL_SHOPS: args += ['--val-shops', *VAL_SHOPS]
    if LORA.get('augment'): args += ['--augment', str(LORA['augment'])]   # datamate/augment.py
    sh(*args, stream=True)
import pandas as pd
if (SFT / 'train.jsonl').exists():
    sign('sft', SFT_CFG)
if (SFT / 'report.json').exists():
    rep = json.loads((SFT / 'report.json').read_text())
    VAL = rep['split']['val']; TRAIN = rep['split']['train']
    print('độ phủ nhãn', rep['coverage'], '| theo nguồn', rep['by_source'], '| theo khoảng cách', rep['by_distance'])
    display(pd.DataFrame(rep['per_shop']).T.fillna(0).astype(int))
elif VAL_SHOPS:                      # sft tắt: chỉ đánh giá trên danh sách shop cố định (không train LoRA)
    VAL = [s for s in SHOPS if s in VAL_SHOPS]; TRAIN = [s for s in SHOPS if s not in VAL]
else:
    raise RuntimeError('chưa có sft/report.json: bật RUN sft hoặc đặt VAL_SHOPS')
print('VAL shops (giữ kín):', VAL)
''')

md('## 4. Môi trường GPU, thư viện và model')
code('''
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--disable-pip-version-check',
                'duckdb>=1.4,<2', 'sqlglot==30.30.0', 'python-calamine', 'openpyxl', 'accelerate', 'peft>=0.14',
                'sentencepiece', *(['bitsandbytes'] if QUANTIZE_4BIT else [])], check=True)
# torchao cũ có sẵn trên Kaggle (0.10) làm peft dừng khi gắn LoRA lên Qwen fp16 ("only versions above 0.16.0");
# datamate không dùng torchao, image Docker không cài → gỡ cho giống image.
subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', '-q', 'torchao'], capture_output=True)
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--disable-pip-version-check', 'flash-linear-attention'],
                   capture_output=True, text=True)
print('flash-linear-attention:', 'ok' if r.returncode == 0 else 'không cài được, chạy chế độ chậm')
# causal_conv1d: kernel CUDA cho lớp conv của Qwen3.5 (thiếu → fallback PyTorch, chậm 2-3 lần).
# setup.py tự tải wheel dựng sẵn khớp torch/CUDA; giới hạn thời gian để không kẹt nếu phải biên dịch.
try:
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--disable-pip-version-check',
                        '--no-build-isolation', 'causal-conv1d>=1.4'], capture_output=True, text=True, timeout=900)
    ok = r.returncode == 0 and subprocess.run([sys.executable, '-c', 'import causal_conv1d'],
                                              capture_output=True).returncode == 0
    print('causal_conv1d:', 'ok' if ok else 'không cài được, chạy chế độ chậm\\n' + r.stderr[-800:])
except subprocess.TimeoutExpired:
    print('causal_conv1d: quá 15 phút (phải biên dịch) → bỏ qua, chạy chế độ chậm')
import torch
assert torch.cuda.is_available(), 'Chưa bật GPU: Settings → Accelerator → GPU'
print('GPU:', torch.cuda.get_device_name(0), '| VRAM GB:', round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))
from huggingface_hub import snapshot_download

def _arch(cfg):
    c = cfg.get('text_config') or cfg
    return tuple(c.get(k) for k in ('hidden_size', 'num_hidden_layers', 'intermediate_size'))

def same_model(local_dir, repo):
    """Model in /kaggle/input has the shape of `repo` (a 4B copy must not stand in for 9B)."""
    from huggingface_hub import hf_hub_download
    try:
        ref = json.loads(Path(hf_hub_download(repo, 'config.json')).read_text())
    except Exception as exc:                  # no network: trust the local copy
        print('không kiểm tra được config của', repo, '-', exc)
        return True
    return _arch(json.loads((local_dir / 'config.json').read_text())) == _arch(ref)

def local_or_download(keyword, repo, dest, patterns=None):
    cands = [p.parent for p in INPUT.rglob('config.json') if keyword in str(p).lower()
             and (list(p.parent.glob('*.safetensors*')) or list(p.parent.glob('*.bin')))]
    for c in cands:
        if same_model(c, repo):
            return c
        print('bỏ qua', c, '— khác kiến trúc', repo)
    # /tmp, not WORK: /kaggle/working is capped at 20 GB and saved as output (Qwen3.5-9B alone is ~19 GB)
    return Path(snapshot_download(repo, local_dir=f'/tmp/dm_models/{dest}', allow_patterns=patterns))

MODEL_DIR = local_or_download('qwen', HF_MODEL_ID, 'qwen', ['*.json', '*.safetensors', '*.txt', '*.model', '*.jinja'])
print('MODEL_DIR =', MODEL_DIR)
check = f"from transformers import AutoConfig; AutoConfig.from_pretrained(r'{MODEL_DIR}'); import transformers; print(transformers.__version__)"
r = subprocess.run([sys.executable, '-c', check], capture_output=True, text=True)
if r.returncode:
    print('transformers hiện tại không đọc được Qwen3.5 → nâng cấp')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'git+https://github.com/huggingface/transformers.git@main'], check=True)
    r = subprocess.run([sys.executable, '-c', check], capture_output=True, text=True)
TRANSFORMERS_VERSION = r.stdout.strip()
print('transformers', TRANSFORMERS_VERSION or r.stderr[-1500:])
''')

md('''
### Hàm dùng chung: chạy pipeline trên shop giữ kín, chấm điểm, in bảng
`report` dựng ngưỡng bỏ trống bằng leave-one-shop-out trong các shop val.
''')
code('''
def val_questions(cap=MAX_Q_PER_SHOP_EVAL):
    per, out = {}, []
    for q in (reversed(questions) if EVAL_PICK == 'last' else questions):
        b = q['business_id']
        if b in VAL and q['id'] in gold_ids and (cap is None or per.get(b, 0) < cap):
            out.append(q); per[b] = per.get(b, 0) + 1
    if EVAL_PICK == 'last':
        out.reverse()
    f = STATE / 'questions_val.jsonl'
    f.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\\n' for q in out), encoding='utf-8')
    return f, len(out)

def n_gpus():
    r = subprocess.run([sys.executable, '-c', 'import torch; print(torch.cuda.device_count())'], capture_output=True, text=True)
    return int(r.stdout.strip() or 0) if r.returncode == 0 else 0
NGPU = max(1, n_gpus()) if PARALLEL_GPUS else 1
print('số GPU chạy predict song song:', NGPU)

def sh_parallel(jobs):
    """jobs = [(args, gpu)]: mỗi tiến trình chỉ thấy 1 GPU (CUDA_VISIBLE_DEVICES đặt TRƯỚC khi tiến trình con import torch)."""
    import threading
    procs, threads = [], []
    for args, gpu in jobs:
        env = {**os.environ, 'CUDA_VISIBLE_DEVICES': str(gpu)}
        p = subprocess.Popen([sys.executable, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        def pump(p=p, tag=f'[gpu{gpu}] '):
            for line in p.stdout:
                if 'Warning' not in line and 'warn(' not in line:
                    print(tag + line, end='')
        t = threading.Thread(target=pump); t.start(); procs.append(p); threads.append(t)
    for t in threads: t.join()
    return [p.wait() for p in procs]

def split_shops(qf, k):
    """Chia shop cho k GPU, cân theo số câu (tham lam, cố định → resume giữa các phiên vẫn khớp)."""
    cnt = {}
    for l in qf.read_text(encoding='utf-8').splitlines():
        if l.strip():
            b = json.loads(l)['business_id']; cnt[b] = cnt.get(b, 0) + 1
    groups = [[] for _ in range(k)]; load = [0] * k
    for b in sorted(cnt, key=lambda b: (-cnt[b], b)):
        i = load.index(min(load)); groups[i].append(b); load[i] += cnt[b]
    return [g for g in groups if g]

def run_val(name, *extra):
    qf, n = val_questions()
    return run_on(name, TRAIN_ROOT, qf, f'{n} câu trên {len(VAL)} shop giữ kín', *extra)

def run_on(name, root, qf, what, *extra):
    """Chạy datamate.predict trên bộ dữ liệu `root` với file câu hỏi `qf` (train hoặc public test)."""
    run = STATE / f'run_{name}'
    base = ['-u', '-m', 'datamate.predict', '--data-root', str(root), '--questions', str(qf), '--model', str(MODEL_DIR),
            '--log-dir', str(run / 'logs'), '--resume', *extra]
    if QUANTIZE_4BIT: base.append('--quantize-4bit')
    if not USE_LLM_MAPPER: base.append('--no-llm-mapper')
    t0 = time.time(); print(f'{name}: {what}, {NGPU} GPU')
    groups = split_shops(qf, NGPU) if NGPU > 1 else []
    if len(groups) > 1:
        parts = [run / f'submission.gpu{i}.jsonl' for i in range(len(groups))]
        codes = sh_parallel([(base + ['--out', str(part), '--businesses', *g], i)
                             for i, (part, g) in enumerate(zip(parts, groups))])
        print('mã thoát từng GPU:', codes)
        order = [json.loads(l)['id'] for l in qf.read_text(encoding='utf-8').splitlines() if l.strip()]
        lines = {}
        for part in parts:
            for l in (part.read_text(encoding='utf-8').splitlines() if part.exists() else []):
                try: lines[json.loads(l)['id']] = l
                except json.JSONDecodeError: pass
        (run / 'submission.jsonl').write_text(''.join(lines[i] + '\\n' for i in order if i in lines), encoding='utf-8')
    else:
        sh(*base, '--out', str(run / 'submission.jsonl'), stream=True)
    print(f'{name}: {(time.time() - t0) / 60:.1f} phút')
    return run

def score(run, name, *flags):
    sh('-m', 'datamate.score_run', '--logs', str(run / 'logs'), '--answers', str(ANSWERS), '--out', str(STATE / f'results_{name}'), *flags)
    return STATE / f'results_{name}'

def report(title, **runs):
    print('###', title)
    out = STATE / f'report_{title.split()[0].lower()}.md'
    sh('-m', 'datamate.report', '--runs', *[f'{k}={v}' for k, v in runs.items()], '--shops', *VAL,
       *(['--sft', str(SFT / 'all.jsonl')] if (SFT / 'all.jsonl').exists() else []), '--out', str(out))
''')

md('''
## 4b. File nộp cho bộ test không đáp án (public test)
Chỉ chạy suy luận: không train, không học ngưỡng, không ghi gì từ bộ test vào `sft/` hay calibration.
Chạy TRƯỚC các bước khác để có file sớm; kết quả ở `/kaggle/working/public_submission.jsonl`.
''')
code('''
if RUN.get('public'):
    assert PUBLIC_ROOT is not None, 'RUN public bật nhưng không thấy bộ test (questions.jsonl + data/, không có answers.jsonl) trong Add Input'
    qf_pub = PUBLIC_ROOT / 'questions.jsonl'
    if PUBLIC_SHOPS:                      # chỉ một số shop: ghi file câu hỏi con, predict đọc file đó
        _keep = [l for l in qf_pub.read_text(encoding='utf-8-sig').splitlines()
                 if l.strip() and json.loads(l)['business_id'] in set(PUBLIC_SHOPS)]
        qf_pub = STATE / 'questions_public.jsonl'
        qf_pub.write_text(''.join(l + '\\n' for l in _keep), encoding='utf-8')
    n_pub = sum(1 for l in qf_pub.read_text(encoding='utf-8-sig').splitlines() if l.strip())
    pub_extra = []
    if RUN.get('public_lora'):            # adapter đã train (dataset riêng, vd thunhngl/datamate-lora-run7), không train lại
        # Kaggle có thể làm phẳng thư mục của dataset → tìm theo file, bỏ checkpoint; adapter của ta có datamate_loader.json
        _hits = [p.parent for p in sorted(INPUT.rglob('adapter_model.safetensors'))
                 if 'checkpoint' not in str(p) and (p.parent / 'datamate_loader.json').exists()]
        print('adapter tìm thấy:', [str(h) for h in _hits])
        assert _hits, 'public_lora bật nhưng không thấy adapter (adapter_model.safetensors + datamate_loader.json) trong Add Input'
        pub_adapter = _hits[0]
        print('public dùng adapter', pub_adapter, json.loads((pub_adapter / 'train_log.json').read_text()).get('evals', [])[-1:])
        pub_extra = ['--adapter', str(pub_adapter)]
    run_pub = run_on('public', PUBLIC_ROOT, qf_pub, f'{n_pub} câu của bộ test {PUBLIC_ROOT.name}',
                     '--no-rule-gate',     # bản gốc không cổng; bản có cổng tạo sau bằng kaggle/apply_gate.py từ CÙNG lần chạy
                     *pub_extra, *(['--sql'] if RUN.get('public_sql') else []))
    sub = run_pub / 'submission.jsonl'
    rows = [json.loads(l) for l in sub.read_text(encoding='utf-8').splitlines() if l.strip()]
    kinds = {}
    for r in rows:
        kinds[r.get('type')] = kinds.get(r.get('type'), 0) + 1
    print(f'public: {len(rows)}/{n_pub} dòng | theo type: {kinds}')
    shutil.copy(sub, WORK / 'public_submission.jsonl')
''')

md('''
## 5. TRƯỚC — v5 (prompt đầy đủ + few-shot, không LoRA) trên shop giữ kín
''')
code('''
if RUN['baseline']:
    if BASELINE_SQL:
        run_v5 = run_val('v5_sql', '--sql')
        RES_V5 = score(run_v5, 'v5', '--strip-sql')
        RES_V5_SQL = score(run_v5, 'v5_sql')
        report('Baseline v5', v5=RES_V5, v5_sql=RES_V5_SQL)
    else:
        run_v5 = run_val('v5')
        RES_V5 = score(run_v5, 'v5')
        report('Baseline v5', v5=RES_V5)
''')

md('''
## 5b. Đường tham khảo sqlvote (docs/sqlvote_goi_y.md)
Cùng tập câu v6 vừa chấm (`state/questions_val.jsonl`): làm sạch bảng thô vào DuckDB → prompt có nguyên rulebook →
K bản nháp SQL → bỏ phiếu. Tiến trình con riêng (nạp lại Qwen) để không giữ VRAM cùng lúc với bước v6.
Đối chiếu ở máy local: `python -m sqlvote.compare ... --run v6=state/run_<tên> --run sqlvote=state/sqlvote`.
''')
code('''
if RUN.get('sqlvote'):
    import gc, torch
    gc.collect(); torch.cuda.empty_cache()
    qf = STATE / 'questions_val.jsonl'                    # đúng tập câu v6 vừa được chấm
    assert qf.exists(), 'chưa có state/questions_val.jsonl — chạy bước baseline/lora_eval trước'
    sh('-u', '-m', 'sqlvote.run', 'predict', '--split', str(TRAIN_ROOT), '--questions', str(qf),
       '--answers', str(ANSWERS), '--out', str(STATE / 'sqlvote'), '--cache', '/tmp/sqlvote_cache',
       '--hf-model', str(MODEL_DIR), *(['--quantize-4bit'] if QUANTIZE_4BIT else []),
       '--k', str(SQLVOTE['k']), '--max-tokens', str(SQLVOTE['max_tokens']),
       '--time-budget', str(SQLVOTE['time_budget']), '--save-bank', str(STATE / 'sqlvote_bank.jsonl'),
       '--limit-per-shop', str(SQLVOTE.get('limit_per_shop', 0)),
       *(['--shops', SQLVOTE['shops']] if SQLVOTE.get('shops') else []), stream=True)
    sh('-m', 'sqlvote.run', 'calib', '--logs', str(STATE / 'sqlvote' / 'logs'), stream=True)
''')

md('''
## 6. Bước 1b — QLoRA trên các shop train (4-bit, T4)
Loss chỉ tính trên JSON đích; đánh giá exact-match ý định trên shop val sau mỗi epoch.
''')
code('''
ADAPTER = STATE / 'intent_lora'
LORA_CFG = {**{k: v for k, v in LORA.items() if k != 'max_hours'}, 'sft': fingerprint(SFT / 'train.jsonl'), 'model': HF_MODEL_ID}
guard('lora', LORA_CFG, ADAPTER)
def lora_unfinished():               # chưa có adapter, hoặc lần trước dừng vì hết giờ → chạy tiếp từ checkpoint
    f = ADAPTER / 'train_log.json'
    return not f.exists() or json.loads(f.read_text()).get('complete') is False
if RUN['lora_train'] and lora_unfinished():
    sh('-m', 'datamate.train_lora', '--model', str(MODEL_DIR), '--train', str(SFT / 'train.jsonl'), '--val', str(SFT / 'val.jsonl'),
       '--out', str(ADAPTER), '--epochs', str(LORA['epochs']), '--r', str(LORA['r']), '--alpha', str(LORA['alpha']),
       '--lr', str(LORA['lr']), '--grad-accum', str(LORA['grad_accum']), '--max-len', str(LORA['max_len']),
       '--limit', str(LORA['limit']), '--max-hours', str(LORA['max_hours']),
       *(['--noise-val', str(SFT / 'val_noise.jsonl')] if (SFT / 'val_noise.jsonl').exists() else []), stream=True)
if (ADAPTER / 'train_log.json').exists():
    log = json.loads((ADAPTER / 'train_log.json').read_text())
    sign('lora', LORA_CFG)
    print('đánh giá val:', log['evals'][-3:], '| phút:', log.get('minutes'), '| xong:', log.get('complete', True),
          f"| bước {log.get('step')}/{log.get('total_steps')}")
else:
    print('chưa có adapter LoRA (lora_train tắt)')
''')

md('''
## 7. SAU Bước 1 và Bước 2 — LoRA + đường SQL, **một** lần chạy GPU
`score_run --strip-sql` dựng lại kết quả "chỉ LoRA" từ cùng log, nên bảng có cả: v5 → +LoRA → +SQL (khớp hai đường).
''')
code('''
if RUN['lora_eval']:
    run_lora = run_val('lora_sql', '--adapter', str(ADAPTER), '--sql')
    RES_LORA = score(run_lora, 'lora', '--strip-sql')
    RES_LORA_SQL = score(run_lora, 'lora_sql')
    RES_V5 = STATE / 'results_v5'
    report('Step1+2 LoRA và SQL', **({'v5': RES_V5} if RES_V5.exists() else {}), lora=RES_LORA, lora_sql=RES_LORA_SQL)
''')

md('''
## 8. Bước 3 — XLM-R: trả lời được hay không (câu hỏi + khái niệm shop có)
Train trên shop train, gắn `p_answerable` vào kết quả shop val, so calibration có/không đặc trưng này
và có/không "cứu" câu bỏ trống thành `unanswerable`.
''')
code('''
XLMR = STATE / 'xlmr_ans'
XLMR_CFG = {'split': fingerprint(SFT / 'split.json'), 'model': XLMR_MODEL}
if RUN['xlmr']:
    guard('xlmr', XLMR_CFG, XLMR)
    ANS_DATA = STATE / 'ans_data'
    if not (ANS_DATA / 'pairs.jsonl').exists():
        sh('-m', 'datamate.answerability', 'build', '--train-root', str(TRAIN_ROOT), '--answers', str(ANSWERS),
           '--out', str(ANS_DATA), '--cache', str(CACHE))
    if not (XLMR / 'config.json').exists():
        base = local_or_download('xlm-roberta', XLMR_MODEL, 'xlmr_base', ['*.json', '*.safetensors', '*.model', '*.txt'])
        sh('-m', 'datamate.answerability', 'train', '--data', str(ANS_DATA), '--model', str(base), '--out', str(XLMR),
           '--split', str(SFT / 'split.json'), stream=True)
    if (XLMR / 'config.json').exists(): sign('xlmr', XLMR_CFG)
    RES_ANS = STATE / 'results_lora_sql_ans'
    shutil.rmtree(RES_ANS, ignore_errors=True); shutil.copytree(STATE / 'results_lora_sql', RES_ANS)
    sh('-m', 'datamate.answerability', 'predict', '--model', str(XLMR), '--results', str(RES_ANS), '--data', str(ANS_DATA))
    report('Step3 XLM-R', lora_sql=STATE / 'results_lora_sql', lora_sql_ans=RES_ANS)
''')

md('''
## 9. Bước 4 (tuỳ chọn) — ViT5 chuẩn hoá câu hỏi, chỉ làm gợi ý
Nhãn tự sinh: câu sạch → làm nhiễu (bỏ dấu, phím telex, viết tắt). Số và tên hàng bị khoá bằng placeholder,
đầu ra mất/đổi số là bị loại. Bật bằng `RUN['vit5'] = True`.
''')
code('''
VIT5 = STATE / 'vit5_norm'
if RUN['vit5']:
    pairs = STATE / 'norm_pairs.jsonl'
    sh('-m', 'datamate.neural_norm', 'make-pairs', '--questions', str(TRAIN_ROOT / 'questions.jsonl'), '--out', str(pairs))
    if not (VIT5 / 'config.json').exists():
        base = local_or_download('vit5', VIT5_MODEL, 'vit5_base', ['*.json', '*.safetensors', '*.bin', '*.model'])
        sh('-m', 'datamate.neural_norm', 'train', '--pairs', str(pairs), '--model', str(base), '--out', str(VIT5), stream=True)
    run_hint = run_val('lora_sql_hint', '--adapter', str(ADAPTER), '--sql', '--hint-model', str(VIT5))
    RES_HINT = score(run_hint, 'lora_sql_hint')
    if XLMR.exists():
        sh('-m', 'datamate.answerability', 'predict', '--model', str(XLMR), '--results', str(RES_HINT), '--data', str(STATE / 'ans_data'))
    report('Step4 ViT5', lora_sql=STATE / 'results_lora_sql_ans', lora_sql_hint=RES_HINT)
''')

md('''
## 10. Calibration cuối + phân tích lỗi
Ngưỡng nộp bài học trên toàn bộ shop val (các shop mà LoRA/XLM-R không thấy khi train), với mọi đặc trưng có trong lần chạy tốt nhất.
''')
code('''
_cands = [p for p in [STATE / 'results_lora_sql_hint', STATE / 'results_lora_sql_ans', STATE / 'results_lora_sql', STATE / 'results_v5_sql', STATE / 'results_v5'] if p.exists()]
if not _cands:       # lần chạy chỉ có bộ test (không bước nào trên shop val): không học lại ngưỡng, vẫn đóng gói log
    print('không có results_* trên shop val -> bỏ qua calibration và phân tích lỗi')
else:
    best = max(_cands, key=lambda p: ['results_v5', 'results_v5_sql', 'results_lora_sql', 'results_lora_sql_ans', 'results_lora_sql_hint'].index(p.name))
    print('calibration từ', best.name)
    sh('-m', 'datamate.calibration', '--results', str(best), '--out', str(CODE / 'calibration.json'))
    shutil.copy(CODE / 'calibration.json', STATE / 'calibration.json')
    rows = []
    for f in sorted(best.glob('biz_*.json')):
        if f.name.endswith('.meta.json'): continue
        for r in json.loads(f.read_text(encoding='utf-8')):
            rows.append({'biz': f.stem, 'metric': (r.get('intent') or {}).get('metric'), 'verdict': r['verdict'],
                         'agree': r.get('agree'), 'p_ans': r.get('p_answerable'), 'question': r.get('question'),
                         'answer': r.get('answer'), 'gold': r.get('gold'), 'reason': r.get('reason')})
    df = pd.DataFrame(rows)
    display(df.pivot_table(index='metric', columns='verdict', values='question', aggfunc='count', fill_value=0))
    if 'agree' in df: display(pd.crosstab(df.agree.fillna('-'), df.verdict))
    pd.set_option('display.max_colwidth', 90)
    display(df[df.verdict != 'correct'].head(40))
    for f in sorted(STATE.glob('report_*.md')):
        print(f.read_text().split('```json')[0])
''')

md('''
## 11. Đóng gói
- `datamate_submit/` (+ zip): code, `calibration.json`, `models/intent_lora`, `models/xlmr_ans`, (`models/vit5_norm`),
  Dockerfile, predict.sh, README. **Chép thêm** `models/Qwen3.5-4B` (base model) vào đó trước khi `docker build`.
- `v6_state.zip`: toàn bộ `state/` (SFT, kết quả, adapter, báo cáo) — Add Input để chạy tiếp / gửi lại phân tích.
''')
code('''
if RUN['package']:
    SUB = WORK / 'datamate_submit'
    shutil.rmtree(SUB, ignore_errors=True)
    shutil.copytree(CODE, SUB, ignore=shutil.ignore_patterns('__pycache__', 'cache'))
    (SUB / 'models').mkdir(exist_ok=True)
    for src, dst in [(ADAPTER, 'intent_lora'), (XLMR, 'xlmr_ans'), (VIT5, 'vit5_norm')]:
        if src.exists():
            shutil.copytree(src, SUB / 'models' / dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('checkpoint*'))
    (SUB / 'TRANSFORMERS_VERSION').write_text(TRANSFORMERS_VERSION + '\\n')
    shutil.make_archive(str(WORK / 'datamate_submit'), 'zip', SUB)
    shutil.make_archive(str(WORK / 'v6_state'), 'zip', WORK, 'state')
    for f in ('datamate_submit.zip', 'v6_state.zip'):
        p = WORK / f
        print(f, f'{p.stat().st_size / 1e6:.1f} MB' if p.exists() else 'thiếu')
''')

nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                   'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}
out = Path(__file__).with_name('datamate_v6_kaggle.ipynb')
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print('wrote', out, len(cells), 'cells')
