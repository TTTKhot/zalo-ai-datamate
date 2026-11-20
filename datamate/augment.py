"""Surface-noise augmentation of answer-verified SFT questions (the intent label does not change).

Families model how Vietnamese shop owners type questions. TRAIN_FAMILIES are added to the LoRA train set;
HELDOUT_FAMILIES are never trained on and only measure whether the model generalises to a kind of noise
it has not seen (a test set may use abbreviations / typos we did not anticipate).

  no_accent  drop all or part of the diacritics            ("doanh thu tháng 5" -> "doanh thu thang 5")
  abbrev     common chat abbreviations                     ("bao nhiêu" -> "bnhiu", "không" -> "ko")
  telex      unconverted Telex on some words               ("tiền" -> "tieenf", "nhất" -> "nhaats")
  filler     openers / particles                           ("ê ...", "... vậy", "cho mình hỏi ...")
  typo       (held out) dropped / doubled / swapped letters
  reorder    (held out) time phrase moved to the other end of the question

Digits, dates, money and words of product / customer names are protected: noise never changes the facts.
The abbreviation list is general chat Vietnamese, written independently of any question in the data.
"""
from __future__ import annotations

import random
import re
import unicodedata

TRAIN_FAMILIES = ('no_accent', 'abbrev', 'telex', 'filler')
HELDOUT_FAMILIES = ('typo', 'reorder')

ABBREV = {
    'doanh thu': ['dthu', 'dt', 'doanh thu'], 'bao nhiêu': ['bn', 'bnhiu', 'bao nhiu', 'bnh', 'nhiêu'],
    'không': ['ko', 'k', 'hông', 'hok', 'kh'], 'được': ['dc', 'đc', 'đk'], 'tháng': ['th', 'thg', 'tháng'],
    'hôm nay': ['hnay', 'hn', 'bữa nay'], 'hôm qua': ['hqua', 'bữa qua'], 'khách hàng': ['KH', 'khách'],
    'số lượng': ['SL', 'sl'], 'cửa hàng': ['CH', 'tiệm', 'quán', 'shop'], 'đơn hàng': ['đơn', 'đh', 'bill', 'order'],
    'phần trăm': ['%', 'ptram'], 'trung bình': ['tb', 'trbinh'], 'sản phẩm': ['sp'], 'mặt hàng': ['món', 'mh'],
    'nhiều': ['nhìu', 'nhiu'], 'với': ['vs', 'vói'], 'trước': ['trc', 'trước'], 'gì': ['j', 'gì'],
    'vậy': ['z', 'v', 'dị'], 'rồi': ['r', 'rùi'], 'tổng cộng': ['tổng', 'tổng cộng'], 'tuần': ['tuần', 'tuan'],
    'nhập hàng': ['nhập', 'nhập hàng'], 'chuyển khoản': ['ck', 'chuyển khoản'], 'tiền mặt': ['tm', 'tiền mặt'],
    'giúp': ['giùm', 'dùm', 'giúp'], 'mấy': ['mấy', 'nhiêu'], 'là': ['là', 'la'],
}
OPENERS = ['ê ', 'cho mình hỏi ', 'cho hỏi ', 'check giùm ', 'xem giúp ', 'e ơi ', 'ad ơi ', 'shop ơi ']
CLOSERS = [' vậy', ' z', ' nha', ' ạ', ' hả', ' đó', ' nhỉ', '?']
PERIOD_RX = re.compile(r'(?:trong |vào |của )?(?:tháng \d{1,2}(?:/| năm )\d{4}|quý \d(?:/| năm )\d{4}|'
                       r'ngày \d{1,2}/\d{1,2}/\d{4}|hôm nay|hôm qua|tuần (?:này|trước|rồi)|tháng (?:này|trước|rồi)|'
                       r'năm nay|năm (?:trước|ngoái)|\d+ ngày (?:gần nhất|qua))', re.I)
TONE = {'́': 's', '̀': 'f', '̉': 'r', '̃': 'x', '̣': 'j'}
SHAPE = {'â': 'aa', 'ê': 'ee', 'ô': 'oo', 'ă': 'aw', 'ơ': 'ow', 'ư': 'uw', 'đ': 'dd'}


def strip_accents(s: str) -> str:
    s = s.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(ch for ch in unicodedata.normalize('NFD', s) if not unicodedata.combining(ch))


def telex_word(w: str) -> str:
    """'tiền' -> 'tieenf' (shape marks inline, tone letter at the end)."""
    tone, out = '', []
    for ch in unicodedata.normalize('NFD', w):
        if ch in TONE:
            tone = TONE[ch]
        elif ch in ('̂', '̆', '̛'):     # circumflex / breve / horn on the previous letter
            base = out.pop() if out else ''
            out.append({'̂': {'a': 'aa', 'e': 'ee', 'o': 'oo'}, '̆': {'a': 'aw'},
                        '̛': {'o': 'ow', 'u': 'uw'}}[ch].get(base.lower(), base))
        else:
            out.append('dd' if ch == 'đ' else ch)
    return ''.join(out) + tone


def _protected(question: str, names) -> set:
    """Lower-case words that must stay as written: digits/money/dates and words of names found in the question."""
    keep = {w for w in re.findall(r'\S+', question.lower()) if re.search(r'\d', w)}
    ql = question.lower()
    for n in names:
        if n and len(n) >= 4 and n.lower() in ql:
            keep |= set(n.lower().split())
    return keep


def _words(q):
    return re.findall(r'\S+|\s+', q)


def apply(question: str, family: str, rng: random.Random, names=()) -> str:
    keep = _protected(question, names)
    q = question
    if family == 'no_accent':
        if rng.random() < 0.6:
            return strip_accents(q)
        return ''.join(strip_accents(t) if t.strip() and t.lower() not in keep and rng.random() < 0.5 else t
                       for t in _words(q))
    if family == 'abbrev':
        out, n = q, 0
        for full, alts in sorted(ABBREV.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf'(?<!\w){re.escape(full)}(?!\w)', out, re.I) and rng.random() < 0.7:
                out = re.sub(rf'(?<!\w){re.escape(full)}(?!\w)', rng.choice(alts), out, count=1, flags=re.I)
                n += 1
        return out if n else strip_accents(out)
    if family == 'telex':
        toks = _words(q)
        cand = [i for i, t in enumerate(toks) if t.strip() and t.lower() not in keep and strip_accents(t) != t]
        for i in rng.sample(cand, k=min(len(cand), rng.randint(1, 3))):
            toks[i] = telex_word(toks[i])
        return ''.join(toks)
    if family == 'filler':
        body = q.rstrip(' ?')
        if rng.random() < 0.6:
            body = rng.choice(OPENERS) + body[:1].lower() + body[1:]
        if rng.random() < 0.7:
            body += rng.choice(CLOSERS)
        return body
    if family == 'typo':
        toks = _words(q)
        cand = [i for i, t in enumerate(toks) if len(t.strip()) >= 4 and t.lower() not in keep]
        for i in rng.sample(cand, k=min(len(cand), rng.randint(1, 2))):
            w = toks[i]
            j = rng.randrange(1, len(w) - 1)
            op = rng.choice(('drop', 'double', 'swap'))
            toks[i] = w[:j] + w[j + 1:] if op == 'drop' else w[:j] + w[j] + w[j:] if op == 'double' \
                else w[:j] + w[j + 1] + w[j] + w[j + 2:]
        return ''.join(toks)
    if family == 'reorder':
        m = PERIOD_RX.search(q)
        if not m:
            return q
        rest = re.sub(r'\s+', ' ', q[:m.start()] + ' ' + q[m.end():]).strip(' ,')
        phrase = m.group(0).strip()
        if m.start() < len(q) / 2:
            return f'{rest[:1].lower() + rest[1:].rstrip(" ?")} {phrase[:1].lower() + phrase[1:]}?'
        return f'{phrase[:1].upper() + phrase[1:]}, {rest[:1].lower() + rest[1:]}'
    raise ValueError(family)


def variants(question: str, families, k: int, seed: int, names=()) -> list[tuple[str, str]]:
    """k distinct (family, text) variants different from the question."""
    rng = random.Random(seed)
    out, seen = [], {question}
    fams = list(families)
    for _ in range(k * 4):
        if len(out) >= k:
            break
        fam = rng.choice(fams)
        text = apply(question, fam, rng, names)
        if text not in seen:
            seen.add(text)
            out.append((fam, text))
    return out
