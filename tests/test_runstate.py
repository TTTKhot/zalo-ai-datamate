"""Safe resume: torn jsonl lines, signatures, predict --resume never mixes runs (no GPU)."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datamate.llm as llm                                                          # noqa: E402
from datamate.runstate import (atomic_write_text, compare_signature, fingerprint,  # noqa: E402
                               read_jsonl_tolerant, write_signature)

TRAIN = Path(os.environ.get('DATAMATE_TRAIN', Path(__file__).resolve().parents[1] / 'data' / 'train'))


def test_tolerant_jsonl_drops_torn_line(tmp_path):
    f = tmp_path / 's.jsonl'
    f.write_text('{"id": 1}\n{"id": 2}\n{"id": 3, "ans', encoding='utf-8')
    rows, bad = read_jsonl_tolerant(f)
    assert [r['id'] for r in rows] == [1, 2] and bad == 1
    assert read_jsonl_tolerant(tmp_path / 'missing.jsonl') == ([], 0)


def test_atomic_write_and_fingerprint(tmp_path):
    d = tmp_path / 'adapter'
    d.mkdir()
    atomic_write_text(d / 'a.json', '{"x": 1}')
    assert not list(d.glob('*.tmp'))
    fp = fingerprint(d)
    (d / 'checkpoint').mkdir()
    (d / 'checkpoint' / 'state.pt').write_bytes(b'resume state')     # checkpoints do not change the adapter id
    assert fingerprint(d) == fp
    atomic_write_text(d / 'a.json', '{"x": 2}')
    assert fingerprint(d) != fp
    assert fingerprint('') == '' and fingerprint(tmp_path / 'none') == ''


def test_signature_compare(tmp_path):
    m = tmp_path / 'run.meta.json'
    assert compare_signature(m, {'a': 1}) == ('new', [])
    write_signature(m, {'a': 1, 'b': 2})
    assert compare_signature(m, {'a': 1, 'b': 2}) == ('same', [])
    assert compare_signature(m, {'a': 1, 'b': 3}) == ('changed', ['b'])


def _fake(messages):
    return 'not json'                  # every intent fails -> abstain; enough to exercise the resume logic


@pytest.mark.skipif(not (TRAIN / 'questions.jsonl').exists(), reason='needs DATAMATE_TRAIN')
def test_predict_resume(tmp_path, monkeypatch):
    from datamate import predict
    monkeypatch.setattr(llm, 'QwenBackend', lambda *a, **k: llm.FnBackend(_fake))
    qs = [json.loads(l) for l in (TRAIN / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    shops = sorted({q['business_id'] for q in qs})[:2]
    pick = [q for b in shops for q in [x for x in qs if x['business_id'] == b][:2]]
    qf = tmp_path / 'q.jsonl'
    qf.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in pick), encoding='utf-8')
    out, logs = tmp_path / 'run' / 'submission.jsonl', tmp_path / 'run' / 'logs'
    argv = ['--data-root', str(TRAIN), '--questions', str(qf), '--model', 'fake', '--out', str(out),
            '--log-dir', str(logs), '--no-llm-mapper', '--resume']
    predict.main(argv)
    ids = [q['id'] for q in pick]
    assert [json.loads(l)['id'] for l in out.read_text(encoding='utf-8').splitlines()] == ids

    # session killed mid-write: last line torn -> that question is redone, the rest reused
    text = out.read_text(encoding='utf-8')
    out.write_text(text[:-15], encoding='utf-8')
    predict.main(argv)
    assert sorted(json.loads(l)['id'] for l in out.read_text(encoding='utf-8').splitlines()) == sorted(ids)

    # code/adapter changed (simulated by an old signature): old logs leave the scored dir, everything reruns
    meta = out.with_name('submission.meta.json')
    m = json.loads(meta.read_text(encoding='utf-8'))
    m['signature']['code'] = 'old'
    meta.write_text(json.dumps(m), encoding='utf-8')
    predict.main(argv)
    stale = tmp_path / 'run' / 'logs_stale_0'
    assert stale.is_dir() and len(list(stale.rglob('*.json'))) == len(ids)
    assert len([f for f in logs.rglob('*.json') if f.name != 'shop_report.json']) == len(ids)
