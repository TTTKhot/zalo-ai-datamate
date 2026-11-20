"""Safe resume helpers: atomic writes, content fingerprints, run signatures, tolerant jsonl reading.

A long run on Kaggle can die mid-write or be resumed in a later session with different code / adapter /
calibration. These helpers make both cases loud instead of silent:
  * atomic_write_text  -> a killed process never leaves a half-written file under the real name;
  * read_jsonl_tolerant -> a torn last line of submission.jsonl is dropped, not a crash;
  * fingerprint / code_fingerprint -> what produced a result; compared before reusing it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
# offline tools that never change a prediction (editing them must not invalidate saved runs)
OFFLINE_MODULES = {'train_lora.py', 'sft_data.py', 'report.py', 'score_run.py', 'eval_grouped.py', 'splits.py'}
BIG = 64 << 20


def atomic_write_text(path, text: str, encoding='utf-8'):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def _file_digest(h, f: Path):
    size = f.stat().st_size
    h.update(f'{size}\0'.encode())
    with f.open('rb') as fh:
        if size <= BIG:
            h.update(fh.read())
        else:                                   # large weights: size + head + tail is enough to spot a swap
            h.update(fh.read(1 << 20))
            fh.seek(-(1 << 20), os.SEEK_END)
            h.update(fh.read())


def fingerprint(path) -> str:
    """sha256 (16 hex) of a file or of every file under a directory ('' when missing)."""
    if not path:
        return ''
    p = Path(path)
    if not p.exists():
        return ''
    h = hashlib.sha256()
    files = [p] if p.is_file() else sorted(f for f in p.rglob('*') if f.is_file()
                                          and not f.relative_to(p).parts[0].startswith('checkpoint')
                                          and f.suffix not in ('.tmp', '.pyc'))
    for f in files:
        h.update(str(f.relative_to(p) if p.is_dir() else f.name).replace('\\', '/').encode() + b'\0')
        _file_digest(h, f)
    return h.hexdigest()[:16]


def code_fingerprint() -> str:
    """Prediction-relevant source of the datamate package."""
    h = hashlib.sha256()
    for f in sorted(PKG.glob('*.py')):
        if f.name not in OFFLINE_MODULES:
            h.update(f.name.encode() + b'\0' + f.read_bytes().replace(b'\r\n', b'\n'))
    return h.hexdigest()[:16]


def read_jsonl_tolerant(path):
    """(records, n_bad): lines that do not parse (a torn last write) are skipped."""
    p = Path(path)
    if not p.exists():
        return [], 0
    good, bad = [], 0
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            good.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    return good, bad


def compare_signature(meta_path, sig: dict):
    """'new' (no meta), 'same' or 'changed' + list of changed keys."""
    p = Path(meta_path)
    if not p.exists():
        return 'new', []
    try:
        old = json.loads(p.read_text(encoding='utf-8')).get('signature', {})
    except (json.JSONDecodeError, OSError):
        return 'changed', ['<unreadable meta>']
    diff = sorted(k for k in set(old) | set(sig) if old.get(k) != sig.get(k))
    return ('same' if not diff else 'changed'), diff


def write_signature(meta_path, sig: dict, **extra):
    atomic_write_text(meta_path, json.dumps({'signature': sig, **extra}, ensure_ascii=False, indent=1))
