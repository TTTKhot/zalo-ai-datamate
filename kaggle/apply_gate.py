"""Make the 'with rulebook gate' version of an existing submission without another GPU run.

python kaggle/apply_gate.py <submission.jsonl> <split dir with questions.jsonl + rulebook.md> <out.jsonl>

Every question caught by datamate.rulebook.Gate (rule of the split's rulebook that is new / uncovered / modified
versus the train rulebook) becomes abstain, exactly what predict.py does when the gate is on. Prints counts only.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datamate.normalize import norm          # noqa: E402
from datamate.rulebook import Gate           # noqa: E402


def main():
    sub_path, split, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    gate = Gate.from_file(split / 'rulebook.md')
    qs = {q['id']: q for q in map(json.loads, (split / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines()) if q}
    rows = [json.loads(l) for l in sub_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    changed = Counter()
    for r in rows:
        q = qs.get(r['id'])
        if q and gate.check(norm(q['question'])):
            changed[r['type']] += 1
            r.clear()
            r.update(id=q['id'], type='abstain')
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'{len(rows)} dòng; chuyển thành abstain: {sum(changed.values())} (loại trước đó: {dict(changed)}) -> {out}')


if __name__ == '__main__':
    main()
