"""python -m pytest -q sqlvote/tests
Unit tests need no data. The end-to-end test runs when DATAMATE_TRAIN points to the training split."""
import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from sqlvote.backends import FnBackend
from sqlvote.bank import Bank
from sqlvote.clean import parse_date, parse_number, type_column
from sqlvote.dates import date_facts
from sqlvote.engine import check_sql, parse_reply, to_answer, vote
from sqlvote.run import Config, calibration, predict
from sqlvote.scorer import is_correct, score


@pytest.mark.parametrize('text, value, unit', [
    ('55.000đ', 55000, None), ('25k', 25000, None), ('2,825tr', 2825000, None), ('1,500.0000', 1500, None),
    ('-53.500đ', -53500, None), ('22,000', 22000, None), ('12,4%', 12.4, None), ('1tr2', 1200000, None),
    ('18.6', 18.6, None), ('1 hộp', 1, 'hộp'), ('1 xe 4m3', 1, 'xe 4m3'), ('2 m3', 2, 'm3'), ('25kđ', 25000, None),
])
def test_parse_number(text, value, unit):
    got = parse_number(text)
    assert got is not None and got[0] == pytest.approx(value) and got[1] == unit


@pytest.mark.parametrize('text', ['abc', '123 Nguyễn Trãi, Quận 1', '', 'ORD000123', '01/02/2025'])
def test_parse_number_rejects(text):
    assert parse_number(text) is None


def test_parse_date():
    assert parse_date('01/02/2025') == dt.datetime(2025, 2, 1)
    assert parse_date('2025-02-01 06:15:00') == dt.datetime(2025, 2, 1, 6, 15)
    assert parse_date('10 thg 6 2025') == dt.datetime(2025, 6, 10)
    assert parse_date('1/4', 2025) == dt.datetime(2025, 4, 1)
    assert parse_date('1/4') is None and parse_date('31/02/2025') is None


def test_type_column_mixed_dates_and_money():
    values, kind, _ = type_column(pd.Series(['01/02/2025', 45689, '2025-02-03 00:00:00', '10 thg 2 2025', None],
                                            dtype=object), 'Ngày giao dịch')
    assert kind == 'DATE' and values[1] == dt.datetime(2025, 2, 1) and values[4] is None
    values, kind, units = type_column(pd.Series(['55.000đ', '25k', 41000, '2,825tr'], dtype=object), 'Trị giá')
    assert kind == 'BIGINT' and values == [55000, 25000, 41000, 2825000] and units is None
    values, kind, units = type_column(pd.Series(['1 hộp', 2, '10 viên'], dtype=object), 'Số lượng')
    assert kind == 'BIGINT' and values == [1, 2, 10] and units == ['hộp', None, 'viên']
    _, kind, _ = type_column(pd.Series(['0903123456', '0912000111'], dtype=object), 'Số điện thoại')
    assert kind == 'TEXT'


def test_parse_reply_and_check_sql():
    r = parse_reply('<think>x</think>NOTE: doanh thu theo §1.\nPERIOD: 2025-06-01..2025-06-30\nTYPE: number\nSQL:\n'
                    '```sql\nSELECT 1;\n```')
    assert r['type'] == 'number' and r['sql'] == 'SELECT 1' and r['period'][1] == dt.date(2025, 6, 30)
    assert parse_reply('TYPE: unanswerable\nREASON: không có giá vốn')['reason'] == 'không có giá vốn'
    assert check_sql('SELECT 1') is None
    assert check_sql("SELECT * FROM read_csv('x.csv')") and check_sql('DROP TABLE t') and check_sql('')


def test_to_answer_shapes():
    assert to_answer(['x'], [[4820000.0]], 'number') == ('ok', 4820000)
    assert to_answer(['x'], [[200555.6]], 'number') == ('ok', 200556)          # money: half up to đồng
    assert to_answer(['x'], [[12.4049]], 'percent') == ('ok', 12.4)
    assert to_answer(['x'], [[dt.date(2026, 8, 15)]], 'date') == ('ok', '2026-08-15')
    assert to_answer(['x'], [['2025-09']], 'date') == ('ok', '2025-09')
    assert to_answer(['x'], [['a'], ['b']], 'list') == ('ok', ['a', 'b'])
    assert to_answer(['a', 'b'], [[1.0, 2.0]], 'list') == ('ok', [1, 2])
    assert to_answer(['x'], [[None]], 'number')[0] == 'empty'
    assert to_answer(['x'], [[1], [2]], 'number')[0] == 'shape'
    assert to_answer(['kh', 'no'], [['Chị Lan', 3200000.0]], 'table')[1]['rows'] == [['Chị Lan', 3200000]]


def _s(typ, answer):
    return {'status': 'ok', 'type': typ, 'answer': answer}


def test_vote():
    bad = {'status': 'error'}
    v = vote([_s('number', 5), _s('number', 5.0), _s('percent', 5), _s('number', 7)])
    assert v['decision'] == 'answer' and v['answer'] == 5 and v['type'] == 'number' and v['confidence'] == 0.75
    assert vote([_s('number', 5), bad, bad, bad])['decision'] == 'abstain'          # failed drafts lower confidence
    assert vote([_s('number', 0)] * 4)['decision'] == 'abstain'                     # zero is abstained by default
    assert vote([_s('number', 0)] * 4, zero_threshold=0.5)['decision'] == 'answer'
    assert vote([_s('string', 'Sting dâu 330ml'), _s('string', 'sting  dâu-330ML')])['confidence'] == 1.0
    assert vote([_s('string', 'Sting dâu'), _s('string', 'Sting dầu')])['confidence'] == 0.5   # accents matter
    un = {'status': 'unanswerable', 'reason': 'x'}
    assert vote([un, un, _s('number', 3)])['decision'] == 'unanswerable'
    assert vote([_s('number', 1), _s('number', 2)])['answer'] == 1                  # tie -> earliest (greedy) draft


def test_scorer():
    gold = {'id': 'q', 'type': 'string', 'answer': 'Xi măng Hà Tiên PCB40 bao 50kg', 'alias': ['SP0001']}
    assert is_correct({'type': 'string', 'answer': 'sp0001'}, gold)
    assert not is_correct({'type': 'list', 'answer': ['SP0001']}, gold)
    gold = {'id': 'q', 'type': 'list', 'answer': ['A', 'B'], 'alias': [['X1'], ['X2']]}
    assert is_correct({'type': 'list', 'answer': ['x1', 'B']}, gold)
    assert not is_correct({'type': 'list', 'answer': ['B', 'A']}, gold)
    gold = {'id': 'q', 'type': 'table', 'answer': {'columns': ['kh', 'no'], 'rows': [['An', 5], ['Bình', 3]]},
            'alias': [['KH1'], ['KH2']]}
    assert is_correct({'type': 'table', 'answer': {'columns': ['a', 'b'], 'rows': [['Bình', 3], ['KH1', 5]]}}, gold)
    gold = {'id': 'q', 'type': 'number', 'answer': 4820000, 'alias': []}
    assert not is_correct({'type': 'number', 'answer': '4820000'}, gold)
    assert not is_correct({'type': 'percent', 'answer': 4820000}, gold)
    assert score([{'id': 'q', 'type': 'abstain'}], [gold])['pa'] == 0.0


def test_bank_and_dates():
    bank = Bank([{'id': '1', 'shop': 'a', 'question': 'tỉ lệ huỷ đơn tháng 6/2025 là bao nhiêu %'},
                 {'id': '2', 'shop': 'b', 'question': 'top 3 mặt hàng bán chạy nhất tuần này'},
                 {'id': '3', 'shop': 'c', 'question': 'doanh thu hôm nay'}])
    assert bank.retrieve('thang 11/2026 ti le huy don la bnhiu %', k=1)[0]['id'] == '1'
    assert bank.retrieve('tỉ lệ huỷ đơn', k=3, exclude_shops=('a',))[-1]['id'] != '1'
    facts = date_facts('2026-06-24', {'lunar': {(2025, 12, 23): dt.date(2026, 2, 10), (2026, 1, 1): dt.date(2026, 2, 17),
                                                (2026, 1, 10): dt.date(2026, 2, 26)}})
    assert 'thứ Hai 2026-06-22' in facts and '2026-06-15 → 2026-06-21' in facts and '2026-05-01 → 2026-05-24' in facts
    assert 'Tết 2026: 23 tháng Chạp = 2026-02-10' in facts and '2026-01-24 → 2026-02-09' in facts


def test_compare(tmp_path):
    from sqlvote.compare import compare, load_run
    golds = {'q1': {'id': 'q1', 'type': 'number', 'answer': 10},
             'q2': {'id': 'q2', 'type': 'string', 'answer': 'Bia Tiger lon', 'alias': ['SP0002']},
             'q3': {'id': 'q3', 'type': 'unanswerable', 'answer': None},
             'q4': {'id': 'q4', 'type': 'number', 'answer': 7}}
    a = {'q1': {'id': 'q1', 'type': 'number', 'answer': 10}, 'q2': {'id': 'q2', 'type': 'abstain'},
         'q3': {'id': 'q3', 'type': 'number', 'answer': 0}, 'q4': {'id': 'q4', 'type': 'number', 'answer': 8}}
    b = {'q1': {'id': 'q1', 'type': 'number', 'answer': 10.0}, 'q2': {'id': 'q2', 'type': 'string', 'answer': 'sp0002'},
         'q3': {'id': 'q3', 'type': 'unanswerable'}, 'q4': {'id': 'q4', 'type': 'number', 'answer': 9}}
    report, stats = compare({'v6': a, 'sqlvote': b}, golds)
    assert stats['summary']['v6']['pa'] == pytest.approx(-0.25)          # 1 right, 2 wrong, 1 abstain
    assert stats['summary']['sqlvote']['pa'] == pytest.approx(0.5)       # 3 right, 1 wrong
    combos = list(stats['combos'].values())
    assert combos[0]['correct'] == 2 and combos[0]['wrong'] == 2          # v6, fall back to sqlvote on q2
    assert combos[2]['correct'] == 1 and combos[2]['wrong'] == 0          # only q1 agrees (10 == 10.0)
    assert 'sqlvote đúng, v6 sai' in report
    # a v6 results_<name>/ folder and a submission.jsonl load to the same lines
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results' / 'biz_1.json').write_text(json.dumps([
        {'id': 'q1', 'status': 'answered', 'answer': 10, 'type': 'number'},
        {'id': 'q3', 'status': 'unanswerable', 'reason': 'x'}, {'id': 'q2', 'status': 'abstain'}]), encoding='utf-8')
    (tmp_path / 'results' / 'biz_1.meta.json').write_text('{}', encoding='utf-8')
    loaded = load_run(tmp_path / 'results')
    assert loaded['q1']['answer'] == 10 and loaded['q3']['type'] == 'unanswerable' and loaded['q2']['type'] == 'abstain'


TRAIN = os.environ.get('DATAMATE_TRAIN')


@pytest.mark.skipif(not TRAIN or not Path(TRAIN, 'questions.jsonl').exists(), reason='DATAMATE_TRAIN not set')
def test_predict_loop(tmp_path):
    """predict() on a real shop with scripted replies: logs, submission, bank, calibration, resume."""
    from sqlvote.smoke_test import CASES
    cases = CASES['biz_105']
    by_text = {}
    for line in Path(TRAIN, 'questions.jsonl').read_text(encoding='utf-8').splitlines():
        q = json.loads(line)
        if q['id'] in cases:
            by_text[q['question']] = cases[q['id']]

    def fn(messages):
        question = messages[-1]['content'].rsplit('Câu hỏi: ', 1)[-1]
        return by_text.get(question, 'tôi không biết')

    backend = FnBackend(fn)
    args = dict(cfg=Config(k=4, workers=2), answers=Path(TRAIN, 'answers.jsonl'), shops={'biz_105'},
                save_bank=tmp_path / 'bank.jsonl', log=lambda *_: None)
    result = predict(TRAIN, tmp_path, backend, **args)
    s = result['score']
    assert s['correct'] == len(cases) and s['wrong'] == 0 and s['abstain'] == s['n'] - len(cases)
    assert len((tmp_path / 'bank.jsonl').read_text(encoding='utf-8').splitlines()) == len(cases)
    assert 'bản nháp greedy đúng' in calibration(tmp_path / 'logs')
    calls = backend.calls
    predict(TRAIN, tmp_path, backend, **args)                 # everything is resumed from the logs
    assert backend.calls == calls
