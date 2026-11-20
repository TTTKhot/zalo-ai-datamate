"""One-time setup, run by setup.bat. Safe to run again: it only fixes what is missing."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / 'kaggle' / 'config.json'
TOKEN = Path.home() / '.kaggle' / 'access_token'


def ok(msg):
    print('  [OK]', msg)


def run(*args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding='utf-8', errors='replace')


cfg = json.loads(CFG.read_text(encoding='utf-8'))

print('\n1) Token Kaggle')
if not TOKEN.exists() or not TOKEN.read_text().strip():
    tok = input('   Dán token KGAT_... rồi Enter: ').strip()
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(tok)
ok(f'token ở {TOKEN}')

print('\n2) Tên tài khoản Kaggle')
if not cfg.get('kaggle_username') or cfg['kaggle_username'].startswith('YOUR_'):
    cfg['kaggle_username'] = input('   Tên tài khoản (phần sau kaggle.com/ ở trang cá nhân): ').strip()
    CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
ok(cfg['kaggle_username'])

print('\n3) Kiểm tra kết nối Kaggle')
r = run('kaggle', 'datasets', 'list', '--mine')
if r.returncode:
    print(r.stdout + r.stderr)
    sys.exit('   Lỗi kết nối: token sai/hết hạn? Xoá file token ở trên rồi chạy lại setup.bat.')
mine = r.stdout
print('   ' + '\n   '.join(mine.splitlines()[:8]))
slug = cfg['code_dataset']
if f"/{slug}" not in mine:
    guess = [l.split()[0].split('/')[-1] for l in mine.splitlines()[2:] if 'datamate' in l.lower()]
    if guess:
        cfg['code_dataset'] = guess[0]
        CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
        ok(f'dataset code: {guess[0]}')
    else:
        print(f'   !! không thấy dataset "{slug}" — lần chạy đầu sẽ tự tạo mới')
else:
    ok(f'dataset code: {slug}')

print('\n4) Dữ liệu train trên máy')
train = ROOT / 'data' / 'train'
if not (train / 'questions.jsonl').exists():
    dl = ROOT / 'data' / '_download'
    print(f"   Tải {cfg['train_dataset']} từ Kaggle (vài phút)...")
    r = run('kaggle', 'datasets', 'download', cfg['train_dataset'], '-p', dl, '--unzip')
    hits = [p.parent for p in dl.rglob('questions.jsonl') if (p.parent / 'data').is_dir()]
    if not hits:
        print(r.stdout[-800:] + r.stderr[-800:])
        sys.exit('   Không tải được. Tải tay dataset train trên Kaggle, chép thư mục "train" vào data\\ rồi chạy lại.')
    if train.exists():
        shutil.rmtree(train)
    shutil.move(str(hits[0]), str(train))
    shutil.rmtree(dl, ignore_errors=True)
ok(train)

print('\n5) Test code trên máy (khoảng 1–2 phút)')
r = run(sys.executable, '-m', 'pytest', '-q', str(ROOT / 'tests'))
print('   ' + (r.stdout.strip().splitlines() or ['?'])[-1])
if r.returncode:
    print(r.stdout[-1500:])
    sys.exit('   Test lỗi — mở app Claude tab Code và dán đoạn trên.')
print('\nXONG. Mở app Claude -> tab Code -> chọn thư mục này.')
