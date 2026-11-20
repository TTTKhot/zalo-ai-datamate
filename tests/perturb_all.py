"""Robustness of the agent to how a QUESTION is written: one tool, every meaning-preserving rewrite family.

Only the 24 non-held-out train shops: shops of kaggle/config.json `val_shops` are refused. Never reads public/test.
No logic is tied to a question id or a business_id; every rewrite reads only the question text, its as_of_date and
the shop's product/customer names (so names are never damaged).

Sub-commands
  stats            how many questions each family applies to (cheap, no answering)
  run              scripted measurement (tests/scripted_intent.py + datamate.pipeline.answer), per family:
                   kept / lost / gained / still_not / diff, with the LAYER of every lost/diff question
  chatgpt-export   prompt + stratified question sample in chunks to paste into ChatGPT (open-ended families)
  chatgpt-import   check ChatGPT's JSONL (numbers, names kept) -> variants.jsonl / rejected.jsonl / review_sample.md
  gpu-export       folder shaped like the public test set (questions.jsonl + data/ + calendar + rulebook, NO answers)
                   holding the originals and their variants, for `colab_cycle.py --public DIR` / Kaggle `--public`
  gpu-score        score a submission of that folder against answers.jsonl, by family

  python tests/perturb_all.py stats --train-root data/train <biz...>
  python tests/perturb_all.py run --train-root data/train [--families F|group ...] [--per-shop N] [--seed 0]
         [--cache .cache/perturb_shops] [--out-dir runs/perturb/<stamp>] [--chatgpt variants.jsonl] [--examples N] <biz...>
  python tests/perturb_all.py chatgpt-export --train-root data/train --per-shop 5 --chunk 40 --out-dir runs/perturb/chatgpt <biz...>
  python tests/perturb_all.py chatgpt-import --train-root data/train --in runs/perturb/chatgpt/out --out runs/perturb/chatgpt/variants.jsonl
  python tests/perturb_all.py gpu-export --train-root data/train --families ... --per-shop N [--chatgpt v.jsonl] --out-dir runs/perturb/gpu <biz...>
  python tests/perturb_all.py gpu-score --train-root data/train --manifest runs/perturb/gpu/manifest.json --submission <file|dir>

Families (group: names). `--families` takes family names or group names. Each rewrite returns None when it does not
apply or cannot be made with certainty; a variant equal to the question counts as "does not apply".
  month     month_t T5/2026, month_th2 Th5/26, month_thg thg 5/2026, month_bare4 5/2026, month_bare2 5/26,
            month_dash tháng 5-2026, month_tdot T.5/2026, month_pad 05/2026, month_thgns Thg5/2026
            (the 9 forms of tests/perturb_questions.py, renamed lower-case so ids stay distinct on a case-insensitive
            file system: `Thg` and `thg` would collide as log file names on Windows)
  date      dd/mm/yyyy -> date_pad (toggle the leading zeros 24/3 <-> 24/03), date_yy 24/03/26, date_dash 24-03-2026,
            date_dot 24.03.2026, date_words "ngày 24 tháng 3 năm 2026"
  relative  see RELATIVE below
  quarter   quarter_q Q1/2026, quarter_roman quý I/2026, quarter_nam quý 1 năm 2026, quarter_qspace Q1 2026
  money     an amount WITH a money unit (41.000đ, 130.000 đồng): money_k 41k, money_nghin 41 nghìn, money_ngan 41 ngàn,
            money_dong 41000 đồng, money_vnd 41.000 VNĐ, money_comma 41,000đ; amounts >= 1 triệu: money_tr 1tr2,
            money_trieu 1,2 triệu, money_trdot 1.2tr (only amounts that these forms write exactly)
  percent   pct_word  "%" -> "phần trăm" (10% -> 10 phần trăm, bao nhiêu % -> bao nhiêu phần trăm);
            pct_symbol "phần trăm" -> "%"; pct_may "bao nhiêu %/phần trăm", "nhiêu %" -> "mấy phần trăm"
  numword   a count 1..10 before a counted noun (3 khách, 7 ngày, 2 mặt hàng) -> words (ba khách, bảy ngày);
            never after ngày/tháng/quý/năm/top/size/mã/lô, never a date or money, never inside a product/customer name,
            "5 tháng" is left (năm tháng reads as "years")
  case      case_upper, case_lower
  punct     punct_noq (drop "?" and ", "), punct_space (double spaces, trailing space)
  augment   aug_no_accent, aug_abbrev, aug_telex, aug_filler, aug_typo, aug_reorder = datamate/augment.py apply()
            (names = shop products + customers, as sft_data does), rng seeded by crc32(seed, id, family)
  chat      chat_mix = abbrev, then strip all accents, then typo (how owners type in chat)
  chatgpt   gpt_<family> imported with --chatgpt (paraphrase, synonym, colloquial, english_mix, verbose, terse)

RELATIVE: only rewrites the rulebook (data/train/rulebook.md §2 "Thời gian", read through datamate/periods.resolve)
gives the SAME date range for the question's as_of_date. Questions with a comparison word (so với, tăng, giảm, chênh,
hơn, kém, thay đổi, tăng trưởng, cùng kỳ) or with any other time expression are left alone, because "tháng này/tháng
trước" inside a comparison changes the base period (§2 "Tháng này ... So với tháng trước thì lấy cùng số ngày").
  rel_last_month   "tháng M/Y" -> "tháng trước" when M/Y is the month before as_of (periods.resolve last_month =
                   the whole previous month, like §2 "Tuần trước, tuần rồi: cả tuần liền trước"; §2 does not spell out
                   "tháng trước" — the analogy is the only assumption)
  rel_this_month   "tháng M/Y" -> "tháng này" ONLY when as_of is the last day of M/Y (§2 "Tháng này: từ ngày 1 đến hết
                   hôm nay" = §2 "Tháng M/Y: cả tháng" only on the last day)
  rel_month_noyear "tháng M/Y" -> "tháng M" when §2 "Tháng M không ghi năm: của năm nay nếu không sau hôm nay; sau hôm nay
                   thì của năm trước" gives year Y (every month-year of the question must satisfy it)
  rel_month_yword  "tháng M/Y" -> "tháng M năm nay" (Y = year of as_of) / "tháng M năm ngoái" (Y = year before)
  rel_last_year    standalone "năm Y" -> "năm ngoái" when Y = year before as_of (a whole past year; not in §2, plain
                   Vietnamese); NOT "năm Y" -> "năm nay": "năm nay" is read as từ đầu năm (§2: 01/01 .. hết hôm nay),
                   equal to the whole year only on 31/12, and the train set has no such as_of
  rel_syn_rule     synonyms §2 names itself: "tuần trước" <-> "tuần rồi", "từ đầu năm" -> "từ đầu năm tới nay"
  rel_syn_chat     chat synonyms of the same expression: tháng trước -> tháng vừa rồi, tuần trước -> tuần vừa rồi,
                   trước -> trc in "tháng/tuần trước", hôm qua -> bữa qua, hôm nay -> bữa nay,
                   "N ngày gần nhất" -> "N ngày gần đây"
  Dropped as not certain to keep the meaning: "tháng trước nữa" (two months back: not in §2, datamate has no period
  type for it), a date without its year (§ "Ngày không ghi năm" is about data rows, not questions), "năm Y" -> "năm nay",
  "N ngày qua" (may or may not include today), "tháng này" for a month that is not finished at as_of.

LAYER of a lost / diff question (`run`). The submission does not use scripted_intent (it is a test stand-in for Qwen);
reading a question is split between datamate (real, ships in Docker) and the stand-in:
  real, in datamate:  datamate.normalize.norm (accents, telex, abbreviations, month forms) and datamate.timex.periods_of
                      (the date tagger; the production path overrides the LLM's periods with it, pipeline.
                      reconcile_periods), datamate.slots.apply_cues (vocabulary cues on the normalised text)
  stand-in only:      metric / filter / params choice of tests/scripted_intent.py (Qwen does this on GPU)
  Decision, in order (the first that fires wins):
    datamate         the tagger's periods of norm(original) and norm(variant), resolved to date ranges with
                     periods.resolve at as_of, are both non-empty and differ, or the variant gets periods the original
                     did not have; or apply_cues on the ORIGINAL scripted intent gives a different intent with
                     norm(variant) than with norm(original) (a real cue rule reads the variant differently)
    timex_miss       the tagger found the period in the original but nothing in the variant: the production path then
                     keeps the LLM's own periods, so Qwen may still be right — needs GPU to know (scripted reads periods
                     from the same tagger, so it is always wrong here)
    intent_scripted  the tagger agrees but scripted_intent built a different intent (periods compared as resolved
                     ranges): may be only the test tool; needs GPU to know
    datamate         same intent, different answer (should not happen: answering reads only the intent)
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import pickle
import random
import re
import shutil
import sys
import time
import zlib
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from datamate import augment as AUG                               # noqa: E402
from datamate.normalize import norm                               # noqa: E402
from datamate.periods import Calendar, resolve                    # noqa: E402
from datamate.pipeline import answer, load_shop                   # noqa: E402
from datamate.scoring import is_correct, to_submission            # noqa: E402
from datamate.slots import apply_cues                             # noqa: E402
from datamate.timex import periods_of                             # noqa: E402
from datamate.values import plain                                 # noqa: E402
from perturb_questions import FAMILIES as MONTH_FORMS, MONTH_YEAR  # noqa: E402
from scripted_intent import scripted_intent                       # noqa: E402

PROMPT_DOC = ROOT / 'docs' / 'chatgpt_perturb_prompt.md'
GPT_FAMILIES = ('paraphrase', 'synonym', 'colloquial', 'english_mix', 'verbose', 'terse')
GPU_HOURS_PER_Q = 1.5 / 300          # Kaggle 2xT4, 4B, no LoRA (CLAUDE.md)
SAFE_ID = re.compile(r'^[A-Za-z0-9_\-]+$')


# ---------------------------------------------------------------------------------------------------- helpers
def held_out() -> set:
    return set(json.loads((ROOT / 'kaggle' / 'config.json').read_text(encoding='utf-8')).get('val_shops') or [])


def check_shops(biz):
    bad = [b for b in biz if b in held_out()]
    if bad:
        sys.exit(f'refusing held-out shops {bad} (kaggle/config.json val_shops)')


def read_jsonl(path: Path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8-sig').splitlines() if l.strip()]


def load_questions(root: Path, biz):
    keep = set(biz)
    return [q for q in read_jsonl(root / 'questions.jsonl') if q['business_id'] in keep]


def load_gold(root: Path):
    return {r['id']: r for r in read_jsonl(root / 'answers.jsonl')}


def _code_stamp() -> str:
    """Hash of datamate/*.py: a cached shop is reused only while the ingest code is unchanged."""
    h = hashlib.sha1()
    for p in sorted((ROOT / 'datamate').glob('*.py')):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:10]


def get_shop(root: Path, biz: str, cache_dir: str):
    cache = Path(cache_dir) / f'{biz}_{_code_stamp()}.pkl' if cache_dir else None
    if cache and cache.exists():
        return pickle.loads(cache.read_bytes())
    shop = load_shop(root / 'data' / biz, biz)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        for old in cache.parent.glob(f'{biz}_*.pkl'):
            old.unlink()
        cache.write_bytes(pickle.dumps(shop))
    return shop


def shop_name_list(names: dict) -> list:
    return [n for n in list(names.get('products', [])) + list(names.get('customers', [])) if isinstance(n, str)]


def rng_for(seed, qid, family) -> random.Random:
    return random.Random(zlib.crc32(f'{seed}|{qid}|{family}'.encode('utf-8')))


def name_spans(text: str, names) -> list:
    """(start, end) of every product / customer name written (case-insensitively) in the question."""
    spans, low = [], _plain_same_len(text)
    for n in names:
        if n and len(n) >= 3:
            for m in re.finditer(re.escape(_plain_same_len(n)), low):
                spans.append((m.start(), m.end()))
    return spans


def _plain_same_len(s: str) -> str:
    """Lower-case, accent-free, one character per character (positions match the original text)."""
    return ''.join((AUG.strip_accents(ch) or ch)[:1].lower() for ch in s)


def _inside(span, spans):
    return any(s < span[1] and span[0] < e for s, e in spans)


def _has_accents(q: str) -> bool:
    """The question is written with Vietnamese diacritics (inserted words follow the same style)."""
    return AUG.strip_accents(q) != q


def _acc(q, accented, bare):
    return accented if _has_accents(q) else bare


# ---------------------------------------------------------------------------------------------------- families
# month ---------------------------------------------------------------------------------------------
MONTH_KEYS = {'month_t': 'T', 'month_th2': 'Th2', 'month_thg': 'thg', 'month_bare4': 'bare4', 'month_bare2': 'bare2',
              'month_dash': 'dash', 'month_tdot': 'Tdot', 'month_pad': 'pad', 'month_thgns': 'Thg'}


def _month(key):
    fn = MONTH_FORMS[MONTH_KEYS[key]]

    def f(q, ctx):
        new, n = MONTH_YEAR.subn(lambda mt: fn(int(mt.group(1)), int(mt.group(2))), q)
        return new if n else None
    return f


# date ----------------------------------------------------------------------------------------------
DATE_RX = re.compile(r'(?<![\w/.\-])(?:(ngày|ngay)\s+)?(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])', re.IGNORECASE)


def _valid_date(d, m, y):
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False


def _date(kind):
    def f(q, ctx):
        n = 0

        def sub(mt):
            nonlocal n
            word, ds, ms, ys = mt.group(1), mt.group(2), mt.group(3), mt.group(4)
            d, m, y = int(ds), int(ms), int(ys)
            if not _valid_date(d, m, y):
                return mt.group(0)
            pre = f'{word} ' if word else ''
            if kind == 'pad':
                padded = len(ds) == 2 and len(ms) == 2
                body = f'{d}/{m}/{y}' if padded and (ds[0] == '0' or ms[0] == '0') else f'{d:02d}/{m:02d}/{y}'
                if body == f'{ds}/{ms}/{ys}':
                    return mt.group(0)
            elif kind == 'yy':
                body = f'{ds}/{ms}/{y % 100:02d}'
            elif kind == 'dash':
                body = f'{ds}-{ms}-{ys}'
            elif kind == 'dot':
                body = f'{ds}.{ms}.{ys}'
            elif kind == 'words':
                n += 1
                acc = _has_accents(q)
                w = (word or ('ngày' if acc else 'ngay'))
                if not word and mt.start() == 0:
                    w = w.capitalize()
                return f'{w} {d} {"tháng" if acc else "thang"} {m} {"năm" if acc else "nam"} {y}'
            n += 1
            return pre + body
        new = DATE_RX.sub(sub, q)
        return new if n else None
    return f


# quarter -------------------------------------------------------------------------------------------
QUARTER_RX = re.compile(r'(?<!\w)(quý|quy)\s+([1-4])\s*(/|-|\s(?:năm|nam)\s)\s*(\d{4})(?!\d)', re.IGNORECASE)
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV'}


def _quarter(kind):
    def f(q, ctx):
        n = 0

        def sub(mt):
            nonlocal n
            qq, y, sep = int(mt.group(2)), mt.group(4), mt.group(3).strip().lower()
            word = mt.group(1)
            if kind == 'q':
                out = f'Q{qq}/{y}'
            elif kind == 'qspace':
                out = f'Q{qq} {y}'
            elif kind == 'roman':
                out = f'{word} {ROMAN[qq]}/{y}'
            else:                                   # nam
                if sep in ('năm', 'nam'):
                    return mt.group(0)
                out = f'{word} {qq} {"năm" if word.lower() == "quý" else "nam"} {y}'
            n += 1
            return out
        new = QUARTER_RX.sub(sub, q)
        return new if n else None
    return f


# money ---------------------------------------------------------------------------------------------
MONEY_RX = re.compile(r'(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d{4,})\s*(đồng|dong|vnđ|vnd|đ)(?!\w)', re.IGNORECASE)


def _fmt_dots(v: int) -> str:
    return f'{v:,}'.replace(',', '.')


def _tr_parts(v: int, max_dec: int):
    """1_200_000 -> ('1', '2'); None when v < 1e6 or needs more than max_dec decimals."""
    if v < 1_000_000:
        return None
    whole, rest = divmod(v, 1_000_000)
    if rest == 0:
        return str(whole), ''
    dec = f'{rest:06d}'.rstrip('0')
    if len(dec) > max_dec:
        return None
    return str(whole), dec


def _money(kind):
    def f(q, ctx):
        spans = ctx['spans']
        n = 0

        def sub(mt):
            nonlocal n
            if _inside(mt.span(), spans):
                return mt.group(0)
            v = int(mt.group(1).replace('.', ''))
            out = None
            if kind in ('k', 'nghin', 'ngan') and v % 100 == 0:
                k = str(v // 1000) if v % 1000 == 0 else f'{v // 1000},{(v % 1000) // 100}'    # 27.500 -> 27,5
                out = {'k': f'{k}k', 'nghin': f'{k} nghìn', 'ngan': f'{k} ngàn'}[kind]
            elif kind == 'dong':
                out = f'{v} đồng'
            elif kind == 'vnd':
                out = f'{_fmt_dots(v)} VNĐ'
            elif kind == 'comma' and v >= 1000:
                out = f'{v:,}đ'
            elif kind == 'tr':
                p = _tr_parts(v, 1)
                out = p and f'{p[0]}tr{p[1]}'
            elif kind == 'trieu':
                p = _tr_parts(v, 3)
                out = p and (f'{p[0]},{p[1]} triệu' if p[1] else f'{p[0]} triệu')
            elif kind == 'trdot':
                p = _tr_parts(v, 1)
                out = p and (f'{p[0]}.{p[1]}tr' if p[1] else f'{p[0]}tr')
            if not out or out == mt.group(0):
                return mt.group(0)
            n += 1
            return out
        new = MONEY_RX.sub(sub, q)
        return new if n else None
    return f


# percent -------------------------------------------------------------------------------------------
HOWMANY = r'(?:bao nhiêu|bao nhieu|bnhiu|bnhieu|bao nhiu|nhiêu|nhieu|bn)'


def pct_word(q, ctx):
    """Only a "%" outside product names ("Povidine 10%" is a name and stays)."""
    w = _acc(q, 'phần trăm', 'phan tram')
    spans = ctx['spans']
    rx = re.compile(rf'({HOWMANY}|\d)\s*%', re.IGNORECASE)
    new = rx.sub(lambda mt: mt.group(0) if _inside(mt.span(), spans) else f'{mt.group(1)} {w}', q)
    return new if new != q else None


def pct_symbol(q, ctx):
    new = re.sub(r'\s*(?<!\w)(phần trăm|phan tram)(?!\w)', '%', q, flags=re.IGNORECASE)
    new = re.sub(rf'({HOWMANY})%', r'\1 %', new, flags=re.IGNORECASE)
    return new if new != q else None


def pct_may(q, ctx):
    new = re.sub(rf'(?<!\w){HOWMANY}\s*(?:%|phần trăm|phan tram)', _acc(q, 'mấy phần trăm', 'may phan tram'), q,
                 flags=re.IGNORECASE)
    return new if new != q else None


# numword -------------------------------------------------------------------------------------------
NUMWORDS = {1: 'một', 2: 'hai', 3: 'ba', 4: 'bốn', 5: 'năm', 6: 'sáu', 7: 'bảy', 8: 'tám', 9: 'chín', 10: 'mười'}
COUNT_NOUN = r'(?:khách hàng|khách|khach|mặt hàng|mat hang|sản phẩm|san pham|món|mon|ngày|ngay|đơn|don|tuần|tuan|' \
             r'tháng|thang|lần|lan|nhà cung cấp|loại|loai)'
NUM_RX = re.compile(rf'(?<![\w/.,\-])(10|[1-9])\s+({COUNT_NOUN})(?!\w)', re.IGNORECASE)
NOT_AFTER = re.compile(r'(?<!\w)(?:ngày|ngay|tháng|thang|quý|quy|năm|nam|top|size|mã|ma|lô|lo|số|so|thứ|thu|q|t)\s*$',
                       re.IGNORECASE)


def numword(q, ctx):
    spans = ctx['spans']
    n = 0

    def sub(mt):
        nonlocal n
        num, noun = int(mt.group(1)), mt.group(2)
        if _inside(mt.span(), spans) or NOT_AFTER.search(q[:mt.start()]):
            return mt.group(0)
        after = q[mt.end():]
        if plain(noun) in ('thang', 'ngay', 'tuan') and re.match(r'\s*[\d/]', after):
            return mt.group(0)                         # "3 tháng 5" is a date
        if num == 5 and plain(noun) == 'thang':
            return mt.group(0)                         # "năm tháng" reads as "years"
        n += 1
        word = NUMWORDS[num]
        if mt.start() == 0:
            word = word[:1].upper() + word[1:]
        return f'{word} {noun}'
    new = NUM_RX.sub(sub, q)
    return new if n else None


# case / punct --------------------------------------------------------------------------------------
def case_upper(q, ctx):
    return q.upper()


def case_lower(q, ctx):
    return q.lower()


def punct_noq(q, ctx):
    new = re.sub(r'\s*\?+\s*$', '', q)
    new = re.sub(r',\s+', ' ', new)
    return new if new != q else None


def punct_space(q, ctx):
    return re.sub(r' ', '  ', q.strip()) + ' '


# augment / chat ------------------------------------------------------------------------------------
def _aug(fam):
    def f(q, ctx):
        return AUG.apply(q, fam, rng_for(ctx['seed'], ctx['id'], fam), ctx['names'])
    return f


def chat_mix(q, ctx):
    rng = rng_for(ctx['seed'], ctx['id'], 'chat_mix')
    t = AUG.apply(q, 'abbrev', rng, ctx['names'])
    t = AUG.strip_accents(t)
    return AUG.apply(t, 'typo', rng, ctx['names'])


# relative ------------------------------------------------------------------------------------------
COMPARE_RX = re.compile(r'(?<!\w)(?:so với|so voi|so vs|so sánh|so sanh|tăng|tang|giảm|giam|chênh|chenh|hơn|hon|kém|kem|'
                        r'thay đổi|thay doi|tăng trưởng|tang truong|cùng kỳ|cung ky|liên tiếp|lien tiep|liên tục|lien tuc)'
                        r'(?!\w)', re.IGNORECASE)
OTHER_TIME_RX = re.compile(r'(?<!\w)(?:tuần|tuan|hôm|hom|bữa|bua|quý|quy|tết|tet|đầu năm|dau nam|năm nay|nam nay|'
                           r'gần nhất|gan nhat|gần đây|gan day|đến hết|den het|tính đến|tinh den|từ ngày|tu ngay|'
                           r'cuối ngày|cuoi ngay|ngày qua|ngay qua)(?!\w)|\d{1,2}/\d{1,2}/\d{4}', re.IGNORECASE)
YEAR_RX = re.compile(r'(?<!\w)(năm|nam)\s+(20\d{2})(?!\d)', re.IGNORECASE)


def _as_of(ctx):
    return date.fromisoformat(str(ctx['as_of'])[:10])


def _simple_month_question(q):
    """Exactly the month-year expressions and nothing else that names a time, no comparison."""
    if COMPARE_RX.search(q):
        return None
    rest = MONTH_YEAR.sub(' ', q)
    if OTHER_TIME_RX.search(rest) or YEAR_RX.search(rest) or re.search(r'(?<!\w)(?:tháng|thang)(?!\w)', rest, re.I):
        return None
    return list(MONTH_YEAR.finditer(q))


def _word(mt, accented, plain_word):
    w = accented if 'á' in mt.group(0).lower() else plain_word
    return w[:1].upper() + w[1:] if mt.group(0)[:1].isupper() else w


def rel_last_month(q, ctx):
    ms = _simple_month_question(q)
    if not ms or len(ms) != 1:
        return None
    today = _as_of(ctx)
    prev = (today.replace(day=1) - timedelta(days=1))
    m, y = int(ms[0].group(1)), int(ms[0].group(2))
    if (m, y) != (prev.month, prev.year):
        return None
    mt = ms[0]
    return q[:mt.start()] + _word(mt, 'tháng trước', 'thang truoc') + q[mt.end():]


def rel_this_month(q, ctx):
    ms = _simple_month_question(q)
    if not ms or len(ms) != 1:
        return None
    today = _as_of(ctx)
    m, y = int(ms[0].group(1)), int(ms[0].group(2))
    if (m, y) != (today.month, today.year) or (today + timedelta(days=1)).day != 1:
        return None
    mt = ms[0]
    return q[:mt.start()] + _word(mt, 'tháng này', 'thang nay') + q[mt.end():]


def rel_month_noyear(q, ctx):
    ms = list(MONTH_YEAR.finditer(q))
    if not ms or YEAR_RX.search(MONTH_YEAR.sub(' ', q)):
        return None
    today = _as_of(ctx)
    for mt in ms:
        m, y = int(mt.group(1)), int(mt.group(2))
        if resolve({'type': 'month', 'month': m}, today).start.year != y:
            return None
    return MONTH_YEAR.sub(lambda mt: f'{_word(mt, "tháng", "thang")} {int(mt.group(1))}', q)


def rel_month_yword(q, ctx):
    ms = list(MONTH_YEAR.finditer(q))
    if not ms:
        return None
    ty = _as_of(ctx).year
    out = []
    for mt in ms:
        m, y = int(mt.group(1)), int(mt.group(2))
        if y not in (ty, ty - 1):
            return None
        acc = 'á' in mt.group(0).lower()
        yw = ('năm nay' if acc else 'nam nay') if y == ty else ('năm ngoái' if acc else 'nam ngoai')
        out.append(f'{_word(mt, "tháng", "thang")} {m} {yw}')
    it = iter(out)
    return MONTH_YEAR.sub(lambda mt: next(it), q)


def rel_last_year(q, ctx):
    if COMPARE_RX.search(q) or MONTH_YEAR.search(q) or QUARTER_RX.search(q) or DATE_RX.search(q):
        return None
    ys = list(YEAR_RX.finditer(q))
    if len(ys) != 1 or OTHER_TIME_RX.search(q) or re.search(r'(?<!\w)(?:tháng|thang)(?!\w)', q, re.I):
        return None
    mt = ys[0]
    if int(mt.group(2)) != _as_of(ctx).year - 1:
        return None
    word = 'năm ngoái' if mt.group(1).lower() == 'năm' else 'nam ngoai'
    return q[:mt.start()] + word + q[mt.end():]


def _swap(q, pairs):
    """Replace each (pattern, replacement) at most where it matches; pairs are applied left to right, no re-matching."""
    pat = re.compile('|'.join(f'(?P<g{i}>{p})' for i, (p, _) in enumerate(pairs)), re.IGNORECASE)

    def sub(mt):
        for i, (_, rep) in enumerate(pairs):
            if mt.group(f'g{i}') is not None:
                out = rep(mt) if callable(rep) else rep
                return out[:1].upper() + out[1:] if mt.group(0)[:1].isupper() else out
        return mt.group(0)
    new = pat.sub(sub, q)
    return new if new != q else None


def rel_syn_rule(q, ctx):
    return _swap(q, [(r'(?<!\w)tuần trước(?!\w)', 'tuần rồi'), (r'(?<!\w)tuần rồi(?!\w)', 'tuần trước'),
                     (r'(?<!\w)tuan truoc(?!\w)', 'tuan roi'), (r'(?<!\w)tuan roi(?!\w)', 'tuan truoc'),
                     (r'(?<!\w)từ đầu năm(?!\w)(?!\s+(?:tới|đến|den|toi)\s)', 'từ đầu năm tới nay'),
                     (r'(?<!\w)tu dau nam(?!\w)(?!\s+(?:tới|đến|den|toi)\s)', 'tu dau nam toi nay')])


def rel_syn_chat(q, ctx):
    return _swap(q, [(r'(?<!\w)tháng trước(?!\w)', 'tháng vừa rồi'), (r'(?<!\w)tuần trước(?!\w)', 'tuần trc'),
                     (r'(?<!\w)thang truoc(?!\w)', 'thang trc'), (r'(?<!\w)tuan truoc(?!\w)', 'tuan vua roi'),
                     (r'(?<!ngày )(?<!ngay )(?<!\w)hôm qua(?!\w)', 'bữa qua'),
                     (r'(?<!ngày )(?<!ngay )(?<!\w)hôm nay(?!\w)', 'bữa nay'),
                     (r'(?<!ngày )(?<!ngay )(?<!\w)hom qua(?!\w)', 'bua qua'),
                     (r'(?<!ngày )(?<!ngay )(?<!\w)hom nay(?!\w)', 'bua nay'),
                     (r'(?<!\w)(\d+) ngày gần nhất(?!\w)', lambda mt: f'{mt.group(0).split()[0]} ngày gần đây'),
                     (r'(?<!\w)(\d+) ngay gan nhat(?!\w)', lambda mt: f'{mt.group(0).split()[0]} ngay gan day')])


# registry ------------------------------------------------------------------------------------------
FAMILIES: dict = {}          # name -> (group, fn(question, ctx) -> str | None)


def _reg(group, name, fn):
    FAMILIES[name] = (group, fn)


for _k in MONTH_KEYS:
    _reg('month', _k, _month(_k))
for _k in ('pad', 'yy', 'dash', 'dot', 'words'):
    _reg('date', f'date_{_k}', _date(_k))
for _k, _f in (('rel_last_month', rel_last_month), ('rel_this_month', rel_this_month),
               ('rel_month_noyear', rel_month_noyear), ('rel_month_yword', rel_month_yword),
               ('rel_last_year', rel_last_year), ('rel_syn_rule', rel_syn_rule), ('rel_syn_chat', rel_syn_chat)):
    _reg('relative', _k, _f)
for _k in ('q', 'roman', 'nam', 'qspace'):
    _reg('quarter', f'quarter_{_k}', _quarter(_k))
for _k in ('k', 'nghin', 'ngan', 'dong', 'vnd', 'comma', 'tr', 'trieu', 'trdot'):
    _reg('money', f'money_{_k}', _money(_k))
for _k, _f in (('pct_word', pct_word), ('pct_symbol', pct_symbol), ('pct_may', pct_may)):
    _reg('percent', _k, _f)
_reg('numword', 'numword', numword)
_reg('case', 'case_upper', case_upper)
_reg('case', 'case_lower', case_lower)
_reg('punct', 'punct_noq', punct_noq)
_reg('punct', 'punct_space', punct_space)
for _k in AUG.TRAIN_FAMILIES + AUG.HELDOUT_FAMILIES:
    _reg('augment', f'aug_{_k}', _aug(_k))
_reg('chat', 'chat_mix', chat_mix)
GROUPS = sorted({g for g, _ in FAMILIES.values()}, key=lambda g: list(FAMILIES.values()).index(
    next(v for v in FAMILIES.values() if v[0] == g)))
GPU_DEFAULT = ['month_t', 'month_bare2', 'date_dash', 'rel_last_month', 'rel_month_noyear', 'rel_syn_chat', 'quarter_q',
               'money_k', 'pct_word', 'numword', 'case_upper', 'aug_no_accent', 'aug_abbrev', 'aug_typo',
               'aug_reorder', 'chat_mix']


def family_group(fam):
    return FAMILIES[fam][0] if fam in FAMILIES else 'chatgpt'


def expand_families(items):
    if not items:
        return list(FAMILIES)
    out = []
    for it in items:
        if it in FAMILIES:
            out.append(it)
        elif it in GROUPS:
            out += [f for f, (g, _) in FAMILIES.items() if g == it]
        else:
            sys.exit(f'unknown family/group {it!r}; groups: {GROUPS}; families: {list(FAMILIES)}')
    return list(dict.fromkeys(out))


def make_variant(rec, fam, names, seed):
    """Variant text or None (does not apply / equal to the question / failed)."""
    q = rec['question']
    ctx = {'id': rec['id'], 'as_of': rec.get('as_of_date'), 'names': names, 'seed': seed,
           'spans': name_spans(q, names)}
    try:
        text = FAMILIES[fam][1](q, ctx)
    except Exception as exc:                                  # a rewrite bug must not stop the measurement
        print(f'  ! {fam} failed on {rec["id"]}: {type(exc).__name__}: {exc}', file=sys.stderr)
        return None
    if not text or text.strip() == q.strip() and fam != 'punct_space':
        return None
    return text


def load_chatgpt(paths, qids=None):
    """{orig id: [(gpt_family, text), ...]} from variants.jsonl files."""
    out = defaultdict(list)
    for p in paths or []:
        for r in read_jsonl(Path(p)):
            if qids is None or r['id'] in qids:
                out[r['id']].append((f"gpt_{r['family']}", r['variant']))
    return out


# ---------------------------------------------------------------------------------------------------- stats
def cmd_stats(args):
    root = Path(args.train_root)
    check_shops(args.biz)
    fams = expand_families(args.families)
    qs = load_questions(root, args.biz)
    cnt, by_shop = Counter(), defaultdict(Counter)
    for biz in args.biz:
        names = shop_name_list(get_shop(root, biz, args.cache).names) if args.names else []
        for rec in (q for q in qs if q['business_id'] == biz):
            for fam in fams:
                if make_variant(rec, fam, names, args.seed):
                    cnt[fam] += 1
                    by_shop[fam][biz] += 1
    print(f'{len(qs)} câu, {len(args.biz)} shop')
    print(f'{"họ":18s} {"nhóm":9s} {"áp được":>8s}  shop có')
    for fam in fams:
        print(f'{fam:18s} {family_group(fam):9s} {cnt[fam]:8d}  {len(by_shop[fam]):3d}')
    print(f'tổng biến thể: {sum(cnt.values())}')


# ---------------------------------------------------------------------------------------------------- run
def verdict(sub, g):
    if sub['type'] == 'abstain':
        return 'abstain'
    return 'correct' if g and is_correct(sub, g) else 'wrong'


def _resolved(periods, as_of):
    out = []
    for p in periods or []:
        try:
            r = resolve(p, as_of)
            out.append((r.start.isoformat(), r.end.isoformat()))
        except Exception:
            out.append(('?', json.dumps(p, sort_keys=True, default=str)))
    return out


def _canon_intent(it, as_of):
    if not isinstance(it, dict):
        return json.dumps(it, default=str)
    c = copy.deepcopy(it)
    c['periods'] = _resolved(c.get('periods'), as_of)
    return json.dumps(c, sort_keys=True, ensure_ascii=False, default=str)


def _vocab(names):
    return {t for n in names.get('products', []) + names.get('customers', []) for t in re.findall(r'[a-z0-9]+', plain(n))}


def layer_of(rec, variant, base_intent, new_intent, names):
    """(layer, detail) — see the module docstring."""
    as_of = rec.get('as_of_date')
    vocab = _vocab(names)
    n0, n1 = norm(rec['question'], vocab), norm(variant, vocab)
    t0, t1 = _resolved(periods_of(n0, as_of), as_of), _resolved(periods_of(n1, as_of), as_of)
    if t0 and t1 and t0 != t1:
        return 'datamate', f'date tagger {t0} -> {t1}'
    if not t0 and t1:
        return 'datamate', f'date tagger invents {t1}'
    if isinstance(base_intent, dict):
        a, b = copy.deepcopy(base_intent), copy.deepcopy(base_intent)
        try:
            ca, cb = apply_cues(a, n0), apply_cues(b, n1)
            if _canon_intent(a, as_of) != _canon_intent(b, as_of):
                return 'datamate', f'cue rules {ca} -> {cb}'
        except Exception as exc:
            return 'datamate', f'apply_cues failed: {exc}'
    if t0 and not t1:
        return 'timex_miss', f'date tagger finds nothing (original {t0})'
    if _canon_intent(base_intent, as_of) != _canon_intent(new_intent, as_of):
        return 'intent_scripted', _intent_delta(base_intent, new_intent, as_of)
    return 'datamate', 'same intent, other answer'


def _intent_delta(a, b, as_of):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return f'{a!r} -> {b!r}'
    keys = sorted(set(a) | set(b))
    parts = []
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if k == 'periods':
            va, vb = _resolved(va, as_of), _resolved(vb, as_of)
        if json.dumps(va, sort_keys=True, default=str) != json.dumps(vb, sort_keys=True, default=str):
            parts.append(f'{k}: {json.dumps(va, ensure_ascii=False, default=str)} -> '
                         f'{json.dumps(vb, ensure_ascii=False, default=str)}')
    return '; '.join(parts)[:400]


def _answer_once(shop, rec, cal):
    out = answer(shop, rec, scripted_intent, cal)
    return to_submission(out), copy.deepcopy(out.get('intent'))


def _same(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) == \
        json.dumps(b, sort_keys=True, ensure_ascii=False, default=str)


def select(qs, fams, names, seed, per_shop, gpt=None):
    """{qid: [(family, text), ...]}: every applicable family, or up to per_shop questions per family (seeded)."""
    cand = defaultdict(list)                       # fam -> [(rec, text)]
    for rec in qs:
        for fam in fams:
            text = make_variant(rec, fam, names, seed)
            if text:
                cand[fam].append((rec, text))
        for fam, text in (gpt or {}).get(rec['id'], []):
            cand[fam].append((rec, text))
    plan = defaultdict(list)
    for fam, items in cand.items():
        if per_shop and len(items) > per_shop and not fam.startswith('gpt_'):
            items = random.Random(zlib.crc32(f'{seed}|{fam}'.encode())).sample(items, per_shop)
        for rec, text in items:
            plan[rec['id']].append((fam, text))
    possible = {f: len(v) for f, v in cand.items()}
    possible['_questions'] = len({rec['id'] for v in cand.values() for rec, _ in v})   # originals answered once
    return plan, possible


def _pct(a, b):
    return f'{100.0 * a / b:.1f}%' if b else '—'


def family_table(total, fams, layers=True):
    head = '| họ | nhóm | biến thể | giữ/gốc đúng | mất | thêm | đáp án khác |'
    if layers:
        head += ' mất: datamate | mất: timex_miss | mất: intent_scripted |'
    lines = [head, '|' + '---|' * (head.count('|') - 1)]
    for fam in fams:
        k, l = total[(fam, 'kept')], total[(fam, 'lost')]
        n = sum(total[(fam, x)] for x in ('kept', 'lost', 'gained', 'still_not'))
        if not n:
            continue
        row = f"| {fam} | {family_group(fam)} | {n} | {k}/{k + l} ({_pct(k, k + l)}) | {l} | {total[(fam, 'gained')]} | " \
              f"{total[(fam, 'diff')]} |"
        if layers:
            row += ' ' + ' | '.join(str(total[(fam, 'lost', x)]) for x in ('datamate', 'timex_miss', 'intent_scripted')) + ' |'
        lines.append(row)
    return lines


def print_table(total, fams, layers=True):
    print(f"\n{'họ':18s} {'nhóm':9s} {'n':>5s} {'giữ/gốc đúng':>18s} {'mất':>5s} {'thêm':>5s} {'khác':>5s}"
          + ('   mất theo tầng dm/tx/sc' if layers else ''))
    for fam in fams:
        k, l = total[(fam, 'kept')], total[(fam, 'lost')]
        n = sum(total[(fam, x)] for x in ('kept', 'lost', 'gained', 'still_not'))
        if not n:
            continue
        line = f"{fam:18s} {family_group(fam):9s} {n:5d} {f'{k}/{k + l} ({_pct(k, k + l)})':>18s} {l:5d} " \
               f"{total[(fam, 'gained')]:5d} {total[(fam, 'diff')]:5d}"
        if layers:
            line += '   ' + '/'.join(str(total[(fam, 'lost', x)]) for x in ('datamate', 'timex_miss', 'intent_scripted'))
        print(line)


def write_report(out_dir: Path, title, total, by_shop, fams, broken, meta_lines, layers=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'# {title}', '', *meta_lines, '', '## Theo họ', '', *family_table(total, fams, layers), '']
    groups = defaultdict(Counter)
    for fam in fams:
        g = family_group(fam)
        for x in ('kept', 'lost', 'gained', 'diff'):
            groups[g][x] += total[(fam, x)]
    lines += ['## Theo nhóm', '', '| nhóm | giữ/gốc đúng | mất | thêm | đáp án khác |', '|---|---|---|---|---|']
    for g, c in groups.items():
        if c['kept'] + c['lost'] + c['gained'] + c['diff']:
            lines.append(f"| {g} | {c['kept']}/{c['kept'] + c['lost']} ({_pct(c['kept'], c['kept'] + c['lost'])}) | "
                         f"{c['lost']} | {c['gained']} | {c['diff']} |")
    lines += ['', '## Shop × họ (chỉ ô có mất: mất/gốc đúng)', '']
    shops = sorted(by_shop)
    lost_fams = [f for f in fams if any(by_shop[b][(f, 'lost')] for b in shops)]
    if lost_fams:
        lines += ['| shop | ' + ' | '.join(lost_fams) + ' |', '|---|' + '---|' * len(lost_fams)]
        for b in shops:
            if any(by_shop[b][(f, 'lost')] for f in lost_fams):
                cells = [f"{by_shop[b][(f, 'lost')]}/{by_shop[b][(f, 'kept')] + by_shop[b][(f, 'lost')]}"
                         if by_shop[b][(f, 'lost')] else '' for f in lost_fams]
                lines.append(f'| {b} | ' + ' | '.join(cells) + ' |')
    else:
        lines.append('(không ô nào mất)')
    lines += ['', '## Ví dụ mất (tối đa 8 mỗi họ)', '']
    for fam in fams:
        ex = [b for b in broken if b['family'] == fam and b['kind'] == 'lost'][:8]
        if not ex:
            continue
        lines += [f'### {fam}', '']
        for b in ex:
            lay = f" — tầng **{b['layer']}**: {b.get('layer_detail', '')}" if b.get('layer') else ''
            lines += [f"- `{b['id']}` ({b['biz']}){lay}",
                      f"  - gốc: {b['question']}", f"  - biến thể: {b['variant']}",
                      f"  - đáp án gốc: `{json.dumps(b['base_answer'], ensure_ascii=False, default=str)[:200]}`",
                      f"  - đáp án mới ({b['new_verdict']}): "
                      f"`{json.dumps(b['new_answer'], ensure_ascii=False, default=str)[:200]}`"]
        lines.append('')
    (out_dir / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    (out_dir / 'broken.json').write_text(json.dumps(broken, ensure_ascii=False, indent=1, default=str), encoding='utf-8')


def cmd_run(args):
    root = Path(args.train_root)
    check_shops(args.biz)
    fams = expand_families(args.families)
    qs = load_questions(root, args.biz)
    gpt = load_chatgpt(args.chatgpt, {q['id'] for q in qs})
    gpt_fams = sorted({f for v in gpt.values() for f, _ in v})
    if args.examples:
        for biz in args.biz:
            names = shop_name_list(get_shop(root, biz, args.cache).names)
            for fam in fams:
                shown = 0
                for rec in (q for q in qs if q['business_id'] == biz):
                    text = make_variant(rec, fam, names, args.seed)
                    if text and shown < args.examples:
                        print(f'[{fam}] {rec["question"]}\n{" " * (len(fam) + 3)}{text}')
                        shown += 1
        return
    gold = load_gold(root)
    cal = Calendar(root / 'calendar.csv')
    stamp = time.strftime('%Y%m%d_%H%M%S')
    out_dir = Path(args.out_dir or ROOT / 'runs' / 'perturb' / stamp)
    total, by_shop, broken = Counter(), defaultdict(Counter), []
    started, n_runs, n_possible = time.time(), 0, 0
    for biz in args.biz:
        t_shop = time.time()
        shop = get_shop(root, biz, args.cache)
        names = shop_name_list(shop.names)
        bq = [q for q in qs if q['business_id'] == biz]
        plan, possible = select(bq, fams, names, args.seed, args.per_shop, gpt)
        n_possible += sum(v for k, v in possible.items() if k != '_questions') + possible['_questions']
        for rec in bq:
            todo = plan.get(rec['id'])
            if not todo:
                continue
            g = gold.get(rec['id'])
            base, base_it = _answer_once(shop, rec, cal)
            n_runs += 1
            v0 = verdict(base, g)
            for fam, text in todo:
                sub, new_it = _answer_once(shop, dict(rec, question=text), cal)
                n_runs += 1
                v1 = verdict(sub, g)
                same = _same(sub, base)
                key = 'kept' if v0 == 'correct' and v1 == 'correct' else \
                    'lost' if v0 == 'correct' else 'gained' if v1 == 'correct' else 'still_not'
                item = None
                if key in ('lost', 'gained') or not same:
                    lay, detail = layer_of(rec, text, base_it, new_it, shop.names)
                    item = {'biz': biz, 'family': fam, 'group': family_group(fam), 'id': rec['id'], 'kind': key,
                            'same_answer': same, 'layer': lay, 'layer_detail': detail, 'question': rec['question'],
                            'variant': text, 'as_of_date': rec.get('as_of_date'), 'base_verdict': v0,
                            'new_verdict': v1, 'base_answer': base, 'new_answer': sub}
                    broken.append(item)
                for c in (total, by_shop[biz]):
                    c[(fam, key)] += 1
                    c[(fam, 'diff')] += not same
                    if key == 'lost':
                        c[(fam, 'lost', item['layer'])] += 1
        lost = sum(by_shop[biz][(f, 'lost')] for f in fams + gpt_fams)
        kept = sum(by_shop[biz][(f, 'kept')] for f in fams + gpt_fams)
        print(f'{biz}: {len(plan)}/{len(bq)} câu, giữ {kept}, mất {lost}  ({time.time() - t_shop:.0f}s)', flush=True)
    elapsed = time.time() - started
    all_fams = fams + gpt_fams
    print_table(total, all_fams)
    rate = n_runs / max(elapsed, 1e-9)
    meta = [f'- shop: {", ".join(args.biz)}', f'- họ: {len(all_fams)}; --per-shop {args.per_shop or "tất cả"}; seed {args.seed}',
            f'- {n_runs} lần trả lời trong {elapsed:.0f}s ({rate:.1f}/s)',
            '- tầng: datamate = bộ đọc ngày/chuẩn hoá/cue thật đọc sai; timex_miss = bộ đọc ngày không thấy kỳ (Qwen '
            'có thể vẫn đúng); intent_scripted = chỉ công cụ test scripted đổi ý định (cần GPU để biết). '
            'Xem docstring tests/perturb_all.py.']
    if args.per_shop:
        est = n_possible / max(rate, 1e-9)
        msg = f'ước lượng chạy đủ (không --per-shop) cho các shop này: ~{est / 60:.0f} phút ({n_possible} lần trả lời)'
        print(msg)
        meta.append(f'- {msg}')
    write_report(out_dir, 'Kiểm tra độ bền câu hỏi (scripted)', total, by_shop, all_fams, broken, meta)
    print(f'\n{elapsed:.0f}s; báo cáo: {out_dir / "report.md"}')


# ---------------------------------------------------------------------------------------------------- chatgpt
CATEGORIES = [
    ('quarter', lambda q: QUARTER_RX.search(q)),
    ('date', lambda q: DATE_RX.search(q)),
    ('month', lambda q: MONTH_YEAR.search(q)),
    ('relative', lambda q: re.search(r'(?<!\w)(?:này|nay|trước|truoc|rồi|roi|vừa|vua|gần nhất|gan nhat|hôm|hom|'
                                     r'đầu năm|dau nam)(?!\w)', q, re.I)),
    ('top', lambda q: re.search(r'(?<!\w)(?:top|nhiều nhất|nhieu nhat|chạy nhất|chay nhat|cao nhất|cao nhat)(?!\w)', q, re.I)),
    ('percent', lambda q: re.search(r'%|phần trăm|phan tram|tỉ lệ|tỷ lệ|ti le|ty le', q, re.I)),
]


def category(q, names):
    for name, test in CATEGORIES:
        if test(q):
            return name
    if name_spans(q, names):
        return 'name'
    return 'other'


def prompt_text():
    doc = PROMPT_DOC.read_text(encoding='utf-8')
    m = re.search(r'<!-- PROMPT START -->\s*(.*?)\s*<!-- PROMPT END -->', doc, re.S)
    return m.group(1) if m else doc


def cmd_chatgpt_export(args):
    root = Path(args.train_root)
    check_shops(args.biz)
    qs = load_questions(root, args.biz)
    picked = []
    for biz in args.biz:
        names = shop_name_list(get_shop(root, biz, args.cache).names)
        rng = random.Random(zlib.crc32(f'{args.seed}|chatgpt|{biz}'.encode()))
        buckets = defaultdict(list)
        for rec in (q for q in qs if q['business_id'] == biz):
            buckets[category(rec['question'], names)].append(rec)
        for b in buckets.values():
            rng.shuffle(b)
        order = [c for c, _ in CATEGORIES] + ['name', 'other']
        chosen = []
        while len(chosen) < args.per_shop and any(buckets[c] for c in order):
            for c in order:
                if buckets[c] and len(chosen) < args.per_shop:
                    chosen.append(buckets[c].pop())
        picked += chosen
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prompt = prompt_text()
    n_chunks = 0
    for i in range(0, len(picked), args.chunk):
        rows = [json.dumps({'id': r['id'], 'as_of_date': r.get('as_of_date'), 'question': r['question']},
                           ensure_ascii=False) for r in picked[i:i + args.chunk]]
        n_chunks += 1
        (out / f'chunk_{n_chunks:02d}.txt').write_text(prompt + '\n\n' + '\n'.join(rows) + '\n', encoding='utf-8')
    (out / 'picked.json').write_text(json.dumps([r['id'] for r in picked], indent=0), encoding='utf-8')
    print(f'{len(picked)} câu → {n_chunks} file chunk_XX.txt ở {out}')
    print(f'Dán từng file vào ChatGPT, lưu mỗi câu trả lời thành {out}/out/chunk_XX.jsonl, rồi chạy chatgpt-import.')


def _numbers(text):
    t = re.sub(r'(?<!\d)(\d{1,3})((?:\.\d{3})+)(?!\d)', lambda m: m.group(1) + m.group(2).replace('.', ''), text)
    return {str(int(x)) for x in re.findall(r'\d+', t)}


def _parse_lines(text):
    rows, junk = [], 0
    for line in text.splitlines():
        line = line.strip().rstrip(',')
        if not line or line.startswith('```'):
            continue
        m = re.search(r'\{.*\}', line)
        if not m:
            junk += 1
            continue
        try:
            rows.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            junk += 1
    return rows, junk


def cmd_chatgpt_import(args):
    root = Path(args.train_root)
    hold = held_out()
    allq = {q['id']: q for q in read_jsonl(root / 'questions.jsonl')}
    files = []
    for p in args.inputs:
        p = Path(p)
        files += sorted(p.glob('*.jsonl')) + sorted(p.glob('*.txt')) if p.is_dir() else [Path(x) for x in glob.glob(str(p))]
    names_cache = {}
    ok, rejected, junk = [], [], 0
    seen = set()
    for f in files:
        rows, j = _parse_lines(f.read_text(encoding='utf-8-sig'))
        junk += j
        for r in rows:
            reason = None
            qid, fam, var = r.get('id'), r.get('family'), r.get('variant')
            rec = allq.get(qid)
            if not isinstance(var, str) or not var.strip():
                reason = 'variant rỗng'
            elif rec is None:
                reason = 'id không có trong questions.jsonl'
            elif rec['business_id'] in hold:
                reason = 'shop giữ kín'
            elif fam not in GPT_FAMILIES:
                reason = f'family lạ {fam!r}'
            if not reason:
                biz = rec['business_id']
                if biz not in names_cache:
                    names_cache[biz] = shop_name_list(get_shop(root, biz, args.cache).names)
                n0, n1 = _numbers(rec['question']), _numbers(var)
                if n0 - n1:
                    reason = f'mất số {sorted(n0 - n1)}'
                elif n1 - n0:
                    reason = f'thêm số {sorted(n1 - n0)}'
                else:
                    pv = ' ' + ' '.join(re.findall(r'[a-z0-9]+', plain(var))) + ' '
                    for n in names_cache[biz]:
                        pn = ' '.join(re.findall(r'[a-z0-9]+', plain(n)))
                        if len(pn) >= 4 and f' {pn} ' in ' ' + ' '.join(re.findall(r'[a-z0-9]+', plain(rec['question']))) + ' ' \
                                and f' {pn} ' not in pv:
                            reason = f'mất tên {n!r}'
                            break
                if not reason and plain(var) == plain(rec['question']):
                    reason = 'giống câu gốc'
                if not reason and (qid, fam) in seen:
                    reason = 'trùng (id, family)'
            row = {'id': qid, 'family': fam, 'variant': var}
            if reason:
                rejected.append(dict(row, reason=reason))
            else:
                seen.add((qid, fam))
                ok.append(dict(row, business_id=rec['business_id'], question=rec['question']))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ok), encoding='utf-8')
    (out.parent / 'rejected.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rejected),
                                               encoding='utf-8')
    rng = random.Random(args.seed)
    lines = ['# Soát tay biến thể ChatGPT (8 câu ngẫu nhiên mỗi họ)', '',
             'Kiểm: cùng nghĩa, cùng kỳ, cùng điều kiện, tên giữ nguyên. Sai → xoá dòng đó trong variants.jsonl.', '']
    for fam in GPT_FAMILIES:
        rows = [r for r in ok if r['family'] == fam]
        if not rows:
            continue
        lines += [f'## {fam} ({len(rows)})', '']
        for r in rng.sample(rows, min(8, len(rows))):
            lines += [f"- `{r['id']}`", f"  - gốc: {r['question']}", f"  - mới: {r['variant']}"]
        lines.append('')
    (out.parent / 'review_sample.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'{len(files)} file, {len(ok)} đạt, {len(rejected)} loại, {junk} dòng rác bỏ qua')
    print(f'{"họ":12s} {"đạt":>5s} {"loại":>5s}')
    for fam in sorted(set(GPT_FAMILIES) | {r['family'] for r in rejected if isinstance(r.get('family'), str)}):
        print(f'{fam:12s} {sum(r["family"] == fam for r in ok):5d} {sum(r["family"] == fam for r in rejected):5d}')
    reasons = Counter(' '.join(r['reason'].split()[:2]) if r['reason'].startswith(('mất', 'thêm')) else r['reason']
                      for r in rejected)
    if reasons:
        print('lý do loại:', dict(reasons))
    print(f'→ {out}, {out.parent / "rejected.jsonl"}, {out.parent / "review_sample.md"}')


# ---------------------------------------------------------------------------------------------------- gpu
def cmd_gpu_export(args):
    root = Path(args.train_root)
    check_shops(args.biz)
    fams = expand_families(args.families or GPU_DEFAULT)
    qs = load_questions(root, args.biz)
    gpt = load_chatgpt(args.chatgpt, {q['id'] for q in qs})
    out = Path(args.out_dir)
    pub = out / 'public'
    if pub.exists():
        shutil.rmtree(pub)
    (pub / 'data').mkdir(parents=True)
    rows, manifest, per_fam = [], {}, Counter()
    for biz in args.biz:
        names = shop_name_list(get_shop(root, biz, args.cache).names)
        bq = [q for q in qs if q['business_id'] == biz]
        plan, _ = select(bq, fams, names, args.seed, args.per_shop, gpt)
        for rec in bq:
            todo = plan.get(rec['id'])
            if not todo:
                continue
            base = {k: rec[k] for k in ('id', 'business_id', 'question', 'as_of_date') if k in rec}
            rows.append(base)
            manifest[rec['id']] = {'orig': rec['id'], 'family': None, 'group': None, 'business_id': biz}
            for fam, text in todo:
                vid = f"{rec['id']}__{fam}"
                assert SAFE_ID.match(vid), vid
                rows.append(dict(base, id=vid, question=text))
                manifest[vid] = {'orig': rec['id'], 'family': fam, 'group': family_group(fam), 'business_id': biz,
                                 'question': text}
                per_fam[fam] += 1
        shutil.copytree(root / 'data' / biz, pub / 'data' / biz)
    low = Counter(r['id'].lower() for r in rows)
    assert all(v == 1 for v in low.values()), 'ids collide on a case-insensitive file system'
    (pub / 'questions.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                                         encoding='utf-8')
    for name in ('calendar.csv', 'rulebook.md'):
        shutil.copy(root / name, pub / name)
    (out / 'manifest.json').write_text(json.dumps({'train_root': str(root), 'shops': args.biz, 'families': fams,
                                                   'items': manifest}, ensure_ascii=False, indent=1), encoding='utf-8')
    n_orig = sum(1 for v in manifest.values() if v['family'] is None)
    print(f'{len(rows)} câu ({n_orig} gốc + {len(rows) - n_orig} biến thể), {len(args.biz)} shop → {pub}')
    for fam, c in per_fam.items():
        print(f'  {fam:18s} {c}')
    print(f'ước lượng GPU: ~{len(rows) * GPU_HOURS_PER_Q:.1f} giờ trên Kaggle 2×T4 (300 câu ≈ 1,5 giờ, không LoRA)')
    print('Lưu ý: LoRA đã train trên câu của chính các shop train này → điểm GPU là ước lượng lạc quan về "đúng", '
          'nhưng phần "mất khi viết lại" vẫn có ý nghĩa.')
    print(f'Colab: python colab/colab_cycle.py --public {pub} ...   |   Kaggle: tải {pub} lên một dataset riêng tư rồi '
          f'kaggle_cycle.py --public <owner>/<dataset>')
    print(f'Chấm: python tests/perturb_all.py gpu-score --train-root {root} --manifest {out / "manifest.json"} '
          f'--submission <public_submission.jsonl hoặc thư mục run>')


def _load_submission(path: Path):
    if path.is_dir():
        cands = [p for pat in ('**/public_submission.jsonl', '**/run_public/submission.jsonl', '**/submission.jsonl')
                 for p in sorted(path.glob(pat))]
        if not cands:
            sys.exit(f'không thấy submission.jsonl trong {path}')
        path = cands[0]
        print(f'submission: {path}')
    return {r['id']: r for r in read_jsonl(path)}


def cmd_gpu_score(args):
    root = Path(args.train_root)
    man = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    items = man['items']
    check_shops(sorted({v['business_id'] for v in items.values()}))
    gold = load_gold(root)
    sub = _load_submission(Path(args.submission))
    missing = [k for k in items if k not in sub]
    if missing:
        print(f'! {len(missing)}/{len(items)} id không có trong submission (tính là bỏ trống), vd {missing[:3]}')
    absent = {'type': 'abstain'}
    total, by_shop, broken = Counter(), defaultdict(Counter), []
    fams = []
    base_right = Counter()
    for vid, it in items.items():
        if it['family'] is None:
            v = verdict(sub.get(vid, absent), gold.get(vid))
            base_right[v] += 1
            continue
        fam, orig, biz = it['family'], it['orig'], it['business_id']
        if fam not in fams:
            fams.append(fam)
        g = gold.get(orig)
        b = {k: v for k, v in sub.get(orig, absent).items() if k != 'id'}
        n = {k: v for k, v in sub.get(vid, absent).items() if k != 'id'}
        v0, v1 = verdict(b, g), verdict(n, g)
        same = _same(b, n)
        key = 'kept' if v0 == 'correct' and v1 == 'correct' else \
            'lost' if v0 == 'correct' else 'gained' if v1 == 'correct' else 'still_not'
        for c in (total, by_shop[biz]):
            c[(fam, key)] += 1
            c[(fam, 'diff')] += not same
        if key in ('lost', 'gained') or not same:
            broken.append({'biz': biz, 'family': fam, 'group': family_group(fam), 'id': orig, 'kind': key,
                           'same_answer': same, 'question': None, 'variant': it.get('question'), 'base_verdict': v0,
                           'new_verdict': v1, 'base_answer': b, 'new_answer': n})
    qtext = {q['id']: q['question'] for q in read_jsonl(root / 'questions.jsonl')}
    for b in broken:
        b['question'] = qtext.get(b['id'])
    order = [f for f in FAMILIES if f in fams] + [f for f in fams if f not in FAMILIES]
    print(f"câu gốc: {dict(base_right)}")
    print_table(total, order, layers=False)
    out_dir = Path(args.out_dir or Path(args.manifest).parent / 'score')
    meta = [f'- manifest: {args.manifest}', f'- submission: {args.submission}', f'- câu gốc: {dict(base_right)}',
            '- tầng không có (không có intent scripted); xem log từng câu của run GPU để biết tầng.']
    write_report(out_dir, 'Kiểm tra độ bền câu hỏi (GPU)', total, by_shop, order, broken, meta, layers=False)
    print(f'báo cáo: {out_dir / "report.md"}')


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='cmd', required=True)

    def common(p, biz=True, fams=True):
        p.add_argument('--train-root', required=True)
        p.add_argument('--cache', default=str(ROOT / '.cache' / 'perturb_shops'),
                       help="pickled shops, keyed by a hash of datamate/*.py ('' = no cache)")
        p.add_argument('--seed', type=int, default=0)
        if fams:
            p.add_argument('--families', default=None, type=lambda s: [x for x in re.split(r'[,\s]+', s) if x],
                           help='comma-separated family or group names, e.g. "month,date,aug_typo" (default: all)')
        if biz:
            p.add_argument('biz', nargs='+')

    p = sp.add_parser('stats')
    common(p)
    p.add_argument('--no-names', dest='names', action='store_false', help='skip loading shops (names not protected)')
    p.set_defaults(fn=cmd_stats)
    p = sp.add_parser('run')
    common(p)
    p.add_argument('--per-shop', type=int, default=0, help='up to N questions per shop per family (0 = all)')
    p.add_argument('--out-dir', default='')
    p.add_argument('--chatgpt', action='append', default=[], help='variants.jsonl from chatgpt-import (repeatable)')
    p.add_argument('--examples', type=int, default=0, help='print N variants per family per shop and exit')
    p.set_defaults(fn=cmd_run)
    p = sp.add_parser('chatgpt-export')
    common(p, fams=False)
    p.add_argument('--per-shop', type=int, default=5)
    p.add_argument('--chunk', type=int, default=40)
    p.add_argument('--out-dir', default=str(ROOT / 'runs' / 'perturb' / 'chatgpt'))
    p.set_defaults(fn=cmd_chatgpt_export)
    p = sp.add_parser('chatgpt-import')
    common(p, biz=False, fams=False)
    p.add_argument('--in', dest='inputs', nargs='+', required=True, help='files, globs or folders of ChatGPT output')
    p.add_argument('--out', default=str(ROOT / 'runs' / 'perturb' / 'chatgpt' / 'variants.jsonl'))
    p.set_defaults(fn=cmd_chatgpt_import)
    p = sp.add_parser('gpu-export')
    common(p)
    p.add_argument('--per-shop', type=int, default=3, help='up to N questions per shop per family')
    p.add_argument('--chatgpt', action='append', default=[])
    p.add_argument('--out-dir', default=str(ROOT / 'runs' / 'perturb' / 'gpu'))
    p.set_defaults(fn=cmd_gpu_export)
    p = sp.add_parser('gpu-score')
    common(p, biz=False, fams=False)
    p.add_argument('--manifest', required=True)
    p.add_argument('--submission', required=True)
    p.add_argument('--out-dir', default='')
    p.set_defaults(fn=cmd_gpu_score)
    args = ap.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
