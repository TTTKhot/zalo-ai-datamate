"""Read the rulebook.md of the split being answered and compare it with the train rulebook (docs/plan.md, step B1).

The code implements the train rulebook by hand (metrics.py, rules.py, periods.py, slots.py). Another split may add
terms, industries or clauses, or drop rules. This module only uses the FORMAT of the rulebook (## N. sections,
### industry sub-sections, 2+ column markdown tables, bullets, **bold** defined terms, §N references), never the
content of a particular split.

  parse(path_or_text) -> list[Rule]       one rule = one table row (header / separator rows skipped) or one bullet
  snapshot(rules, covered) -> dict         train rulebook + which metric implements each rule (rulebook_base.json)
  compare(rules, base) -> list[dict]       status per runtime rule: same | supplemented | modified | new | uncovered,
                                           plus base rules that are gone (removed)

python -m datamate.rulebook snapshot data/train/rulebook.md     -> datamate/rulebook_base.json
python -m datamate.rulebook compare <rulebook.md>                -> counts per status (no rule text printed)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .values import plain

BASE_PATH = Path(__file__).with_name('rulebook_base.json')
STOP = {'la', 'va', 'cua', 'cac', 'mot', 'nhung', 'theo', 'trong', 'cho', 'khi', 'thi', 'co', 'duoc', 'the', 'nao',
        'x', 'y', 'n', 'd', 'm', 'q',
        # placeholders of a rule name: the question names a real period / product instead
        'ky', 'thang', 'ngay', 'nam', 'tuan', 'quy'}
STOP_PHRASES = re.compile(r'\b(?:bao nhieu|mat hang|san pham)\b')
DEFINES = re.compile(r'\*\*([^*]{2,60})\*\*\s*(?:=|:|\blà\b|\bbằng\b)')
SAME_AS = re.compile(r'((?:\*\*[^*]{2,60}\*\*\s*,?\s*(?:và|hoặc)?\s*)+)cùng nghĩa với')
BOLD = re.compile(r'\*\*([^*]{2,60})\*\*')
REF = re.compile(r'§\s*(\d+)')


@dataclass
class Rule:
    section_no: int | None
    section: str
    industry: str | None
    title: str
    body: str
    kind: str                                   # 'row' | 'bullet'
    refs: list = field(default_factory=list)
    triggers: list = field(default_factory=list)

    @property
    def key(self) -> str:
        name = self.title if self.kind == 'row' else ' '.join(norm_text(self.body).split()[:10])
        return f"{self.section_no}|{norm_text(self.industry or '')}|{norm_text(name)}"


def norm_text(text: str) -> str:
    text = re.sub(r'[*`_]', ' ', str(text or ''))
    return ' '.join(re.findall(r'[a-z0-9%]+', plain(text)))


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', line)]


def _phrase(text: str) -> str | None:
    text = re.sub(r'<[^>]*>|\([^)]*\)', ' ', text)
    words = [w for w in STOP_PHRASES.sub(' ', norm_text(text)).split() if w not in STOP]
    return ' '.join(words) if words else None


def triggers_of(title: str, body: str) -> list[str]:
    """Phrases a question would use for this rule: the rule name split on commas / slashes, and the bold terms the
    body defines (**X** = / là / : / bằng, "**X**, **Y** cùng nghĩa với")."""
    out = []
    for part in re.split(r',|/|;', title or ''):
        out.append(_phrase(part))
    for m in DEFINES.finditer(body or ''):
        out.append(_phrase(m.group(1)))
    for m in SAME_AS.finditer(body or ''):
        out += [_phrase(b) for b in BOLD.findall(m.group(1))]
    seen, res = set(), []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            res.append(p)
    return res


def parse(source) -> list[Rule]:
    """source: path to rulebook.md or its text."""
    if isinstance(source, Path) or (isinstance(source, str) and '\n' not in source and Path(source).exists()):
        text = Path(source).read_text(encoding='utf-8-sig')
    else:
        text = str(source)
    rules, sec_no, sec, industry = [], None, '', None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^##\s+(?:(\d+)\.\s*)?(.+?)\s*$', line)
        if m and not line.startswith('###'):
            sec_no = int(m.group(1)) if m.group(1) else None
            sec, industry = m.group(2).strip(), None
            i += 1
            continue
        m = re.match(r'^###\s+(.+?)\s*$', line)
        if m:
            industry = m.group(1).strip()
            i += 1
            continue
        if line.lstrip().startswith('|'):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                block.append(lines[i])
                i += 1
            sep = next((k for k, l in enumerate(block) if re.fullmatch(r'[\s|:\-]+', l)), None)
            body_rows = block[sep + 1:] if sep is not None else block
            for row in body_rows:
                cells = _cells(row)
                if len(cells) < 2 or not cells[0]:
                    continue
                title, body = cells[0], ' | '.join(c for c in cells[1:] if c)
                rules.append(Rule(sec_no, sec, industry, title, body, 'row',
                                  sorted({int(r) for r in REF.findall(body)}), triggers_of(title, body)))
            continue
        m = re.match(r'^\s*[-*]\s+(.+)$', line)
        if m and sec_no is not None:
            body = m.group(1).strip()
            rules.append(Rule(sec_no, sec, industry, '', body, 'bullet',
                              sorted({int(r) for r in REF.findall(body)}), triggers_of('', body)))
        i += 1
    return rules


def _clauses(body: str) -> list[str]:
    return [c for c in (norm_text(x) for x in re.split(r'[.;:]\s|\n|\|', body or '')) if c]


def _trigrams(s: str) -> set:
    s = f'  {s} '
    return {s[k:k + 3] for k in range(len(s) - 2)}


def _sim(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    return len(ta & tb) / max(1, len(ta | tb))


def snapshot(rules: list[Rule], covered: dict | None = None) -> dict:
    covered = covered or {}
    return {'rules': [dict(asdict(r), key=r.key, covered_by=covered.get(r.key, [])) for r in rules]}


def load_base(path: Path = BASE_PATH) -> dict | None:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def compare(rules: list[Rule], base: dict | None) -> tuple[list[dict], list[dict]]:
    """(status of every runtime rule, base rules that are gone). Without a base every rule is 'same'."""
    if not base:
        return [{'rule': r, 'status': 'same', 'base': None} for r in rules], []
    pool = {b['key']: b for b in base['rules']}
    used, out = set(), []
    for r in rules:
        b = pool.get(r.key) if r.key not in used else None
        if b is None:                                   # renamed a little: same section, similar name
            name = norm_text(r.title if r.kind == 'row' else r.body)
            cands = [(_sim(name, norm_text(x['title'] if x['kind'] == 'row' else x['body'])), k)
                     for k, x in pool.items() if k not in used and x['section_no'] == r.section_no and x['kind'] == r.kind]
            best = max(cands, default=(0, None))
            b = pool[best[1]] if best[0] >= 0.8 else None
        if b is None:
            out.append({'rule': r, 'status': 'new', 'base': None})
            continue
        used.add(b['key'])
        if not b.get('covered_by'):
            status = 'uncovered'
        elif norm_text(b['body']) == norm_text(r.body):
            status = 'same'
        else:
            new = norm_text(r.body)
            status = 'supplemented' if all(c in new for c in _clauses(b['body'])) else 'modified'
        out.append({'rule': r, 'status': status, 'base': b})
    removed = [b for k, b in pool.items() if k not in used]
    return out, removed


GATED = ('new', 'uncovered', 'modified')
NOT_ROUTED = (7, 8, 9)          # unanswerable / file conventions / answer format: not definitions a question uses


class Gate:
    """Catch questions that use a rule the metric library does not implement as written (docs/plan.md, step B3).

    A trigger phrase of a gated rule matches when the IDF-weighted share of its words present in the question is
    >= t_hi, and the phrase has >= 2 content words or a word that never appears in the train rulebook (a new term).
    With the train rulebook only the 'uncovered' rules can fire."""

    def __init__(self, status: list[dict], base: dict | None, t_hi: float = 0.8, only: set | None = None):
        import math
        docs = [set(norm_text(s['rule'].title + ' ' + s['rule'].body).split()) for s in status]
        n = len(docs) or 1
        df = {}
        for d in docs:
            for w in d:
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log((n + 1) / (c + 1)) + 1 for w, c in df.items()}
        self.train_words = set()
        for b in (base or {}).get('rules', []):
            self.train_words |= set(norm_text(b['title'] + ' ' + b['body']).split())
        self.t_hi = t_hi
        self.items = []
        for s in status:
            r = s['rule']
            if (only is None and s['status'] not in GATED) or (only is not None and r.key not in only):
                continue
            if r.section_no in NOT_ROUTED:
                continue
            for p in r.triggers:
                words = p.split()
                new_word = any(w not in self.train_words for w in words) if self.train_words else False
                if len(words) >= 2 or new_word:
                    self.items.append((p, words, s['status'], r))

    @classmethod
    def from_file(cls, path, base=None, **kw):
        base = load_base() if base is None else base
        status, _ = compare(parse(Path(path)), base)
        return cls(status, base, **kw)

    def check(self, q_norm: str) -> dict | None:
        """Best catching rule for an accent-free normalised question, or None."""
        q = set(norm_text(q_norm).split())
        best = None
        for phrase, words, status, rule in self.items:
            tot = sum(self.idf.get(w, 1.0) for w in words)
            got = sum(self.idf.get(w, 1.0) for w in words if w in q)
            score = got / tot if tot else 0.0
            if score >= self.t_hi and (best is None or score > best['score'] or
                                       (score == best['score'] and len(words) > len(best['phrase'].split()))):
                best = {'score': round(score, 3), 'phrase': phrase, 'status': status, 'rule': rule.title or rule.body[:60],
                        'key': rule.key}
        return best


def main(argv=None):
    argv = argv or sys.argv[1:]
    cmd, path = argv[0], Path(argv[1])
    rules = parse(path)
    if cmd == 'snapshot':
        from .rulebook_cover import COVERED
        snap = snapshot(rules, COVERED)
        BASE_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding='utf-8')
        n_cov = sum(bool(r['covered_by']) for r in snap['rules'])
        print(f'{len(rules)} rules -> {BASE_PATH.name} ({n_cov} covered by a metric / rule in code)')
    elif cmd == 'compare':
        status, removed = compare(rules, load_base())
        counts = {}
        for s in status:
            counts[s['status']] = counts.get(s['status'], 0) + 1
        print(f'{len(rules)} rules: {counts}; removed from base: {len(removed)}')
    elif cmd == 'list':                                # only for the train rulebook (filling rulebook_cover.py)
        for r in rules:
            print(r.key, '|', r.triggers)


if __name__ == '__main__':
    main()
