"""Small text helpers shared by every module (no business meaning)."""
from __future__ import annotations

import re
import unicodedata


def nfc(value) -> str:
    return unicodedata.normalize('NFC', str(value))


def plain(value) -> str:
    """Lower-case, accent-free, single-spaced text: 'Trị  giá' -> 'tri gia'."""
    text = unicodedata.normalize('NFD', str(value).replace('đ', 'd').replace('Đ', 'D'))
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', text).strip().lower()


def slug(value) -> str:
    """ASCII identifier: 'Mã hóa đơn' -> 'ma_hoa_don'."""
    out = re.sub(r'[^a-z0-9]+', '_', plain(value)).strip('_')
    if out and out[0].isdigit():
        out = 'c_' + out
    return out


def norm_key(value) -> str:
    """Scorer-style string key: case, whitespace and punctuation are ignored, accents are kept."""
    text = unicodedata.normalize('NFC', str(value)).casefold()
    return re.sub(r'[\s\W_]+', '', text)


def tokens(value) -> list[str]:
    return re.findall(r'[a-z0-9]+', plain(value))
