"""Question text normalisation shared by the LLM prompt and tests.

Decodes telex typing ("soos" -> "so"), tone-key typos ("thangs" -> "thang") and
common chat abbreviations (dthu, hqua, bn, sp...) into accent-free text. The result
is given to the LLM as a hint next to the original question; it is general
Vietnamese chat vocabulary, never tied to a question or a shop.
"""
from __future__ import annotations

import re

from .values import plain

ABBR = {'dthu': 'doanh thu', 'dt': 'doanh thu', 'hnay': 'hom nay', 'hqua': 'hom qua', 'bn': 'bao nhieu',
        'bnhieu': 'bao nhieu', 'bnhiu': 'bao nhieu', 'nhiu': 'nhieu', 'bao nhiu': 'bao nhieu', 'dc': 'duoc',
        'sp': 'san pham', 'trc': 'truoc', 'th': 'thang', 'thg': 'thang', 'vs': 'voi', 'ko': 'khong',
        'revenue': 'doanh thu', 'total': 'tong cong', 'nhieeu': 'nhieu', 'z': '', 'ta': '', 'ha': ''}
TELEX = [('uwow', 'uo'), ('aa', 'a'), ('aw', 'a'), ('ee', 'e'), ('oo', 'o'), ('ow', 'o'), ('uw', 'u'), ('dd', 'd')]


TONE_TYPO = {'huy', 'nam', 'thang', 'ngay', 'bang', 'nhom', 'hang', 'cua', 'la', 'nao', 'nhap', 'tien',
             'khach', 'ban', 'don', 'gia', 'sang', 'nguoi', 'giup', 'phan', 'trong', 'mat', 'thi', 'ca', 'no',
             'quy', 'tuan'}


def norm(text: str, vocab: set | None = None) -> str:
    vocab = vocab or set()
    words = []
    for w in re.findall(r"[\w%≥≤/,\-:()']+(?:\.\d+)*", str(text).casefold()):
        w = w.rstrip('.,:)(').lstrip('(')
        p = plain(w)
        if p in vocab:
            words.append(p)
            continue
        if re.fullmatch(r'[a-z]+[sfrxj]', p) and p[:-1] in TONE_TYPO:
            words.append(p[:-1])
            continue
        if p in ('ees', 'eef', 'eer'):
            words.append('e')
            continue
        if p in _COUNT_FORMS and w in _COUNT_FORMS[p]:     # a number word as written ("năm"/"nam", not "nằm", "bà")
            words.append('#' + p)
            continue
        if re.fullmatch(r'[a-z]+', p) and re.search(r'aa|aw|ee|oo|ow|uw|dd', p) and len(p) > 3:
            core = p[:-1] if p[-1] in 'sfrxj' else p
            for a, b in TELEX:
                core = core.replace(a, b)
            p = core
        words.append(p)
    text = ' ' + ' '.join(words) + ' '
    for a, b in sorted(ABBR.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf'(?<=\s){re.escape(a)}(?=\s)', b, text)
    return re.sub(r'\s+', ' ', month_forms(date_forms(count_words(text)))).strip()


# A count written as a word right before a counted noun: "năm khách mua nhiều nhất" (top 5), "ít nhất năm đơn",
# "bảy ngày kể từ". Left out: "một" (also "per": "giá một gói"), "sáu" (plain "sau" = "after": "sau ngày 5/3"),
# and "năm tháng/tuần" ("năm" = year).
# Only the number written with its own accents or without accents counts ("bà", "nằm", "tâm" are other words);
# norm() marks those words with "#", count_words() turns them into digits or drops the mark.
_COUNT_WORD = {'hai': 2, 'ba': 3, 'bon': 4, 'nam': 5, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
_COUNT_FORMS = {'hai': {'hai'}, 'ba': {'ba'}, 'bon': {'bốn', 'bon'}, 'nam': {'năm', 'nam'}, 'bay': {'bảy', 'bẩy', 'bay'},
                'tam': {'tám', 'tam'}, 'chin': {'chín', 'chin'}, 'muoi': {'mười', 'muoi'}}
_COUNTED = r'(?:khach(?: hang)?|don(?: hang)?|hoa don|ngay|thang|tuan|mat hang|san pham|mon|loai|nguoi|lan|ly|nha cung cap)'
_COUNT_RX = re.compile(rf'#(hai|ba|bon|nam|bay|tam|chin|muoi) (?={_COUNTED}(?![a-z0-9]))')


def count_words(text: str) -> str:
    def sub(mt):
        word = mt.group(1)
        if word == 'nam' and re.match(r'\s*(?:thang|tuan)(?![a-z0-9])', text[mt.end(1):]):
            return mt.group(0)
        return f'{_COUNT_WORD[word]} '
    return _COUNT_RX.sub(sub, text).replace('#', '')


# Full dates written with "-" or "." or a 2-digit year: 24-03-2026, 24.03.2026, 24/03/26 -> 24/03/2026.
_DATE_SEP = re.compile(r'(?<![\w/.,-])(\d{1,2})[.-](\d{1,2})[.-](20\d{2})(?![\w/.-])')
_DATE_YY = re.compile(r'(?<![\w/.,-])(\d{1,2})/(\d{1,2})/(\d{2})(?![\w/.-])')
# "ngày 21 tháng 7 năm 2025" / "mùng 1 tháng 7 năm 2025" -> "ngay 21/7/2025"
_DATE_WORDS = re.compile(r'(?<![a-z0-9])(ngay|mung|mong) (\d{1,2}) thang (\d{1,2}) nam (20\d{2})(?!\d)')
# Quarters: Q1/2026, Q1 2026, Q1-26, quý I/2026, quý IV năm 2025 -> "quy 1/2026", "quy 4 nam 2025"
_QUARTER_Q = re.compile(r'(?<![a-z0-9])q\s?([1-4])\s*(?:[/-]\s*(20\d{2}|\d{2})|\s(20\d{2}))(?![\w/.-])')
_QUARTER_ROMAN = re.compile(r'(?<![a-z0-9])quy (iv|iii|ii|i)(?![a-z0-9])')
_ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}


def _valid_day(d, m) -> bool:
    return 1 <= int(d) <= 31 and 1 <= int(m) <= 12


def date_forms(text: str) -> str:
    """Closed-class ways of writing a full date or a quarter -> the forms the date tagger reads (dd/mm/yyyy,
    "quy q/yyyy"). General Vietnamese shorthand, like month_forms; never tied to a question or a shop."""
    text = _DATE_WORDS.sub(lambda mt: f'{mt.group(1)} {mt.group(2)}/{mt.group(3)}/{mt.group(4)}'
                           if _valid_day(mt.group(2), mt.group(3)) else mt.group(0), text)
    text = _DATE_SEP.sub(lambda mt: f'{mt.group(1)}/{mt.group(2)}/{mt.group(3)}'
                         if _valid_day(mt.group(1), mt.group(2)) else mt.group(0), text)
    text = _DATE_YY.sub(lambda mt: f'{mt.group(1)}/{mt.group(2)}/20{mt.group(3)}'
                        if _valid_day(mt.group(1), mt.group(2)) else mt.group(0), text)
    def quarter(mt):
        y = mt.group(2) or mt.group(3)
        return f'quy {mt.group(1)}/{y if len(y) == 4 else "20" + y}'
    text = _QUARTER_Q.sub(quarter, text)
    return _QUARTER_ROMAN.sub(lambda mt: f'quy {_ROMAN[mt.group(1)]}', text)


_MONTH_ABBR = re.compile(r'(?<![\w/.-])(?:t|th|thg|thang)\.?\s?(\d{1,2})\s*[/-]\s*(20\d{2}|\d{2})\b(?!\s*[/-]\s*\d)')
_MONTH_BARE = re.compile(r'(?<![\w/.-])(\d{1,2})\s*[/-]\s*(20\d{2}|\d{2})\b(?!\s*[/-]\s*\d)')
# "từ 8/25 tới 10/25" is a range of months: "tu / den / toi" do not block. A day/month after them ("từ 1/1 đến 5/8")
# is already kept by _month_year (a 2-digit year <= 12 is never read as a year).
_NOT_A_MONTH_BEFORE = re.compile(r'(?<![a-z0-9])(?:quy|q|ngay|mung|mong|thang|nam|top|gia|size|so|ma|lo|ty le|ti le)\s*$')


def _month_year(m, y):
    """(month, 4-digit year) or None. A 2-digit year must not be readable as a month ("5/8" stays a day/month)."""
    m, y = int(m), int(y)
    if not 1 <= m <= 12:
        return None
    if y < 100:
        if y <= 12:
            return None
        y += 2000
    return m, y


def month_forms(text: str) -> str:
    """Every way of writing "month m of year y" -> "thang m/yyyy": T5/2026, Th3/26, thg 5-2026, tháng 2/26, and the
    bare 5/2026, 7-2025, 8/26. General Vietnamese shorthand; a closed class, so it is parsed here, not guessed by the LLM.
    Full dates (dd/mm/yyyy), quarters ("quý 3/2026") and other numbers before a slash are left alone."""
    def abbr(mt):
        my = _month_year(mt.group(1), mt.group(2))
        return f'thang {my[0]}/{my[1]}' if my else mt.group(0)

    def bare(mt):
        my = _month_year(mt.group(1), mt.group(2))
        if my is None or _NOT_A_MONTH_BEFORE.search(text[:mt.start()]):
            return mt.group(0)
        return f'thang {my[0]}/{my[1]}'

    text = _MONTH_ABBR.sub(abbr, text)
    return _MONTH_BARE.sub(bare, text)
