"""Step 4 of v6 (optional): neural question normaliser (ViT5 / any seq2seq), used as a HINT only.

The rule normaliser (normalize.py) still feeds the date tagger and the cue rules. The neural
output is only shown to the LLM as "(normalized: ...)", and only if it passes the guard:

  protect  numbers / dates and shop names found in the question are replaced by placeholders
           ZZ0ZZ, ZZ1ZZ ... before generation;
  restore  every placeholder must come back exactly once, then the original text is put back;
  verify   the multiset of numbers is unchanged and the length ratio is sane; else -> None.

So a number or a product name can never be changed by the model.

Training data needs no labels: clean questions (with diacritics) are corrupted the way shop
owners type (accents dropped, telex keys, chat abbreviations) and the model learns to undo it.

python -m datamate.neural_norm make-pairs --questions DATA/train/questions.jsonl [more.jsonl] --out norm_pairs.jsonl
python -m datamate.neural_norm train --pairs norm_pairs.jsonl --model VietAI/vit5-base --out models/vit5_norm
python -m datamate.neural_norm demo --model models/vit5_norm "dthu thangs 3/2026 bn"
"""
from __future__ import annotations

import argparse
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

NUM = re.compile(r'\d+(?:[.,/:-]\d+)*%?')
PH = 'ZZ{}ZZ'
PH_RE = re.compile(r'ZZ(\d+)ZZ')
VI_MARKS = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')


def fold(ch: str) -> str:
    """Accent-free lower-case of ONE character (length preserving)."""
    if ch in 'đĐ':
        return 'd'
    base = unicodedata.normalize('NFD', ch)[0]
    return base.lower()


def _spans_of_names(text: str, names):
    """(start, end) of shop names written in text, accent- and case-insensitive."""
    folded = ''.join(fold(c) for c in text)
    spans = []
    for n in sorted({n for n in names if n and len(n) >= 4}, key=len, reverse=True):
        key = ''.join(fold(c) for c in unicodedata.normalize('NFC', n))
        start = 0
        while True:
            i = folded.find(key, start)
            if i < 0:
                break
            j = i + len(key)
            ok_left = i == 0 or not folded[i - 1].isalnum()
            ok_right = j == len(folded) or not folded[j].isalnum()
            if ok_left and ok_right and not any(a < j and i < b for a, b in spans):
                spans.append((i, j))
            start = j
    return spans


def protect(text: str, names=()):
    text = unicodedata.normalize('NFC', str(text))
    spans = _spans_of_names(text, names)
    for m in NUM.finditer(text):
        if not any(a < m.end() and m.start() < b for a, b in spans):
            spans.append((m.start(), m.end()))
    spans.sort()
    out, keep, last = [], [], 0
    for i, (a, b) in enumerate(spans):
        out.append(text[last:a])
        out.append(f' {PH.format(i)} ')
        keep.append(text[a:b])
        last = b
    out.append(text[last:])
    return re.sub(r'\s+', ' ', ''.join(out)).strip(), keep


def restore(text: str, keep):
    found = PH_RE.findall(text or '')
    if sorted(int(x) for x in found) != list(range(len(keep))):
        return None
    return re.sub(r'\s+', ' ', PH_RE.sub(lambda m: keep[int(m.group(1))], text)).strip()


def guard(original: str, candidate: str | None):
    if not candidate:
        return None
    if Counter(NUM.findall(original)) != Counter(NUM.findall(candidate)):
        return None
    r = len(candidate) / max(len(original), 1)
    if not 0.6 <= r <= 2.2:
        return None
    return candidate


class GuardedNormalizer:
    """callable(question, names_dict) -> normalised hint or None (never changes numbers / names)."""

    def __init__(self, model_dir, device=None, max_len=128, num_beams=2):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.torch = torch
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_dir, local_files_only=True).to(self.device).eval()
        self.max_len, self.num_beams = max_len, num_beams
        self.cache = {}

    def generate(self, text):
        enc = self.tok([text], return_tensors='pt', truncation=True, max_length=self.max_len).to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=self.max_len, num_beams=self.num_beams)
        return self.tok.decode(out[0], skip_special_tokens=True)

    def __call__(self, question, names=None):
        pool = []
        for k in ('products', 'customers', 'groups'):
            pool += list((names or {}).get(k, []))
        key = (question, len(pool))
        if key in self.cache:
            return self.cache[key]
        masked, keep = protect(question, pool)
        out = guard(question, restore(self.generate(masked), keep))
        self.cache[key] = out
        return out


# ------------------------------------------------------------------ synthetic noise
TONE = {'́': 's', '̀': 'f', '̉': 'r', '̃': 'x', '̣': 'j'}
SHAPE = {'̂': None, '̆': 'w', '̛': 'w'}           # circumflex doubles the vowel
ABBREV = [('doanh thu', ['dthu', 'dt', 'doanh thu']), ('hôm qua', ['hqua', 'hom qua']), ('hôm nay', ['hnay']),
          ('bao nhiêu', ['bn', 'bnhiu', 'bao nhiu', 'bao nhieu']), ('được', ['dc', 'đc', 'duoc']),
          ('không', ['ko', 'k', 'khong']), ('tháng', ['th', 'thg', 'thang']), ('sản phẩm', ['sp']),
          ('trước', ['trc']), ('với', ['vs']), ('nhiêu', ['nhiu'])]


def telex_word(word: str) -> str:
    m = re.match(r'^(.*?)([^\w]*)$', word)
    word, tail = m.group(1), m.group(2)
    out, tone = [], ''
    for ch in unicodedata.normalize('NFC', word):
        if ch in 'đĐ':
            out.append('dd' if ch == 'đ' else 'DD')
            continue
        parts = unicodedata.normalize('NFD', ch)
        base, marks = parts[0], parts[1:]
        piece = base
        for m in marks:
            if m in TONE:
                tone = TONE[m]
            elif m == '̂':
                piece = base + base
            elif m in SHAPE:
                piece = base + SHAPE[m]
        out.append(piece)
    return ''.join(out) + tone + tail


def strip_word(word: str) -> str:
    return ''.join(fold(c).upper() if c.isupper() else fold(c) for c in unicodedata.normalize('NFC', word))


def corrupt(text: str, rng: random.Random) -> str:
    t = text
    for full, shorts in ABBREV:
        if full in t.lower() and rng.random() < 0.5:
            t = re.sub(re.escape(full), rng.choice(shorts), t, flags=re.I)
    words = t.split(' ')
    mode = rng.random()
    out = []
    for w in words:
        if NUM.fullmatch(w) or not any(c in VI_MARKS for c in w.lower()):
            out.append(w)
            continue
        r = rng.random()
        if mode < 0.4:                       # mostly accent-free typing
            out.append(strip_word(w) if r < 0.9 else w)
        elif mode < 0.7:                     # telex keys left in a few words
            out.append(telex_word(w) if r < 0.25 else (strip_word(w) if r < 0.6 else w))
        else:                                # light noise
            out.append(strip_word(w) if r < 0.3 else w)
    t = ' '.join(out)
    if rng.random() < 0.5:
        t = t.lower()
    if rng.random() < 0.3:
        t = t.rstrip('?.!')
    return t


def is_clean(q: str) -> bool:
    words = [w for w in re.findall(r'[^\W\d_]+', q.lower())]
    if len(words) < 3:
        return False
    marked = sum(any(c in VI_MARKS for c in w) for w in words)
    return marked / len(words) >= 0.45 and not re.search(r'\b(dthu|hqua|bn|dc|ko)\b', q.lower())


def make_pairs(question_files, out, per_question=3, seed=0):
    rng = random.Random(seed)
    clean = []
    for f in question_files:
        for l in Path(f).read_text(encoding='utf-8-sig').splitlines():
            if l.strip():
                q = json.loads(l)['question']
                if is_clean(q):
                    clean.append(q)
    clean = sorted(set(clean))
    rows = []
    for q in clean:
        masked, keep = protect(q)
        seen = set()
        for _ in range(per_question):
            noisy = corrupt(q, rng)
            if noisy == q or noisy in seen:
                continue
            seen.add(noisy)
            nm, nkeep = protect(noisy)
            if nkeep != keep:
                continue
            rows.append({'source': nm, 'target': masked})
        rows.append({'source': masked, 'target': masked})       # identity: leave clean text alone
    rng.shuffle(rows)
    Path(out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'clean questions {len(clean)} -> pairs {len(rows)}')
    return rows


def train(pairs, model_name, out_dir, epochs=3, lr=3e-4, batch=16, max_len=128, val_frac=0.05, seed=0):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    rng = random.Random(seed)
    rows = [json.loads(l) for l in Path(pairs).read_text(encoding='utf-8').splitlines() if l.strip()]
    rng.shuffle(rows)
    n_val = max(1, int(len(rows) * val_frac))
    val, tr = rows[:n_val], rows[n_val:]
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    for ep in range(epochs):
        rng.shuffle(tr)
        model.train()
        total = 0.0
        for i in range(0, len(tr), batch):
            part = tr[i:i + batch]
            enc = tok([r['source'] for r in part], return_tensors='pt', padding=True, truncation=True,
                      max_length=max_len).to(dev)
            lab = tok([r['target'] for r in part], return_tensors='pt', padding=True, truncation=True,
                      max_length=max_len).input_ids.to(dev)
            lab[lab == tok.pad_token_id] = -100
            loss = model(**enc, labels=lab).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
            total += loss.item()
        model.eval()
        exact = 0
        for r in val[:200]:
            enc = tok([r['source']], return_tensors='pt').to(dev)
            with torch.no_grad():
                pred = tok.decode(model.generate(**enc, max_new_tokens=max_len)[0], skip_special_tokens=True)
            exact += pred.strip() == r['target'].strip()
        print({'epoch': ep + 1, 'loss': round(total / max(1, len(tr) // batch), 4),
               'val_exact': round(exact / min(len(val), 200), 4)}, flush=True)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make-pairs')
    m.add_argument('--questions', nargs='+', required=True)
    m.add_argument('--out', required=True)
    m.add_argument('--per-question', type=int, default=3)
    t = sub.add_parser('train')
    t.add_argument('--pairs', required=True)
    t.add_argument('--model', default='VietAI/vit5-base')
    t.add_argument('--out', required=True)
    t.add_argument('--epochs', type=int, default=3)
    d = sub.add_parser('demo')
    d.add_argument('--model', required=True)
    d.add_argument('text', nargs='+')
    args = ap.parse_args(argv)
    if args.cmd == 'make-pairs':
        make_pairs(args.questions, args.out, args.per_question)
    elif args.cmd == 'train':
        train(args.pairs, args.model, args.out, args.epochs)
    else:
        g = GuardedNormalizer(args.model)
        for t in args.text:
            print(t, '->', g(t))


if __name__ == '__main__':
    main()
