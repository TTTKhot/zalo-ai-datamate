"""Unit tests for the v6 components (no GPU, no train data needed)."""
import copy
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamate.calibration import Calibrator, _keys, ans_bin, features          # noqa: E402
from datamate.intent import canonical_intent, relevant_names                     # noqa: E402
from datamate.neural_norm import guard, protect, restore, telex_word             # noqa: E402
from datamate.scoring import is_correct                                           # noqa: E402
from datamate.sft_data import _money_numbers, neighbours                          # noqa: E402
from datamate.splits import kfold, shop_split                                     # noqa: E402
from datamate.sqlpath import answers_agree, extract_sql, result_value, run_sql, validate_sql  # noqa: E402

FRAMES = {'orders': pd.DataFrame({'order_id': ['A', 'B', 'C'], 'revenue': [100.0, 50.0, 25.0],
                                  'order_date': pd.to_datetime(['2026-01-01', '2026-01-02', '2026-02-01']),
                                  'counts_for_revenue': [True, True, False]})}


def test_canonical_intent_drops_empty_and_sorts():
    it = {'metric': 'revenue', 'compare': None, 'filters': {'product': '', 'group': 'bánh'}, 'params': {'strict': False},
          'periods': [{'type': 'month', 'month': 3, 'year': None}], 'answerable': True}
    assert canonical_intent(it) == {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 3}],
                                    'filters': {'group': 'bánh'}}
    assert canonical_intent({'metric': 'x', 'answerable': False})['answerable'] is False


def test_relevant_names_keeps_mentioned_product():
    pool = [f'Sản phẩm {i}' for i in range(50)] + ['Nếp cái hoa vàng']
    got = relevant_names('ban dc may kg nep cai hoa vang', {'products': pool, 'groups': ['a', 'b']})
    assert got['products'][0] == 'Nếp cái hoa vàng'
    assert got['groups'] == ['a', 'b']


@pytest.mark.parametrize('sql', ["SELECT * FROM read_csv('/etc/passwd')", 'DROP TABLE orders',
                                 'SELECT 1; SELECT 2', 'SELECT x FROM secrets', "COPY orders TO '/tmp/x.csv'",
                                 "ATTACH '/tmp/db' AS d", 'SELECT nope FROM orders'])
def test_validate_sql_rejects(sql):
    assert validate_sql(sql, FRAMES)


def test_sql_runs_and_agrees():
    sql = extract_sql("```sql\nSELECT SUM(revenue) AS r FROM orders WHERE counts_for_revenue "
                      "AND order_date >= DATE '2026-01-01' AND order_date < DATE '2026-02-01';\n```")
    assert validate_sql(sql, FRAMES) == []
    v = result_value(run_sql(sql, FRAMES))
    assert v == 150.0 and answers_agree(v, 150, 'number') and not answers_agree(v, 151, 'number')
    d = result_value(run_sql("SELECT order_date FROM orders ORDER BY revenue DESC LIMIT 1", FRAMES))
    assert answers_agree(d, '2026-01-01', 'date')


def test_sql_external_access_blocked():
    with pytest.raises(Exception):
        run_sql("SELECT * FROM read_csv_auto('/etc/passwd')", FRAMES)


def test_answers_agree_shapes():
    assert answers_agree(12.344, 12.34, 'percent')
    assert answers_agree(['Cà phê sữa'], 'Cà phê sữa', 'string')
    assert answers_agree([1, 'x'], [1, 'X'], 'list')
    tab = {'columns': ['k', 'v'], 'rows': [['An', 100], ['Bình', 50]]}
    assert answers_agree({'columns': ['a', 'b'], 'rows': [['Bình', 50.0], ['An', 100.4]]}, tab, 'table')


def test_calibration_chain_equals_v5_without_new_features():
    f = features({'intent': {'metric': 'revenue'}, 'status': 'answered'})
    assert _keys(f) == [('revenue', 'answered', '-'), ('revenue', 'answered'), ('answered',), ()]
    g = features({'intent': {'metric': 'revenue'}, 'status': 'answered', 'agree': 'agree', 'p_answerable': 0.9})
    assert ('answered', 'agree:agree', 'ans:a2') in _keys(g)


def test_calibration_agree_and_rescue():
    rows = []
    for i in range(40):
        rows.append({'intent': {'metric': 'revenue'}, 'status': 'answered', 'agree': 'agree', 'verdict': 'correct'})
        rows.append({'intent': {'metric': 'revenue'}, 'status': 'answered', 'agree': 'disagree',
                     'verdict': 'wrong' if i % 4 else 'correct'})
        rows.append({'intent': {}, 'status': 'abstain', 'p_answerable': 0.05, 'verdict': 'abstain',
                     'gold_type': 'unanswerable' if i % 5 else 'number'})
    cal = Calibrator().fit(rows)
    assert cal.decide(dict(rows[0], verdict=None))['status'] == 'answered'
    assert cal.decide(dict(rows[1], verdict=None))['status'] == 'abstain'
    assert cal.decide({'status': 'abstain', 'p_answerable': 0.1})['status'] == 'unanswerable'
    assert cal.decide({'status': 'abstain', 'p_answerable': 0.9})['status'] == 'abstain'
    assert Calibrator(rescue=False).fit(rows).decide({'status': 'abstain', 'p_answerable': 0.1})['status'] == 'abstain'
    assert ans_bin(0.19) == 'u2' and ans_bin(0.95) == 'a2' and ans_bin(None) is None


def test_calibration_roundtrip(tmp_path):
    cal = Calibrator().fit([{'intent': {'metric': 'm'}, 'status': 'answered', 'verdict': 'correct'}])
    cal.save(tmp_path / 'c.json')
    back = Calibrator.load(tmp_path / 'c.json')
    assert back.stats == cal.stats and back.rescue == cal.rescue


def test_shop_split_deterministic_and_disjoint():
    shops = [f'biz_{i}' for i in range(100, 130)]
    a = shop_split(shops, 0.2)
    assert a == shop_split(list(reversed(shops)), 0.2)
    tr, va = a
    assert not set(tr) & set(va) and len(va) == 6
    folds = kfold(shops, 3)
    assert sorted(sum(folds, [])) == sorted(shops)


def test_neighbours_cover_common_errors():
    seed = {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 6, 'year': 2026}], 'params': {}}
    names = {'products': ['Mì Hảo Hảo tôm chua cay', 'Trứng gà so']}
    got = {d: it for d, it in neighbours(seed, 'top 3 mat hang ban chay thang 6/2026', names, [], '2026-08-24')}
    assert 'metric=top_products' in got and 'compare=previous' in got
    top = {'metric': 'top_products', 'params': {'k': 1, 'by': 'revenue'}, 'periods': seed['periods']}
    got = {d: it for d, it in neighbours(top, 'top 3 mat hang ban chay thang 6/2026', names, [], '2026-08-24')}
    assert got['k=3']['params']['k'] == 3 and got['by=qty']['params']['by'] == 'qty'
    assert seed == {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 6, 'year': 2026}], 'params': {}}


def test_money_numbers():
    assert _money_numbers('don tu 500k tro len') == [500000.0]
    assert _money_numbers('tren 1.500.000 d') == [1500000.0]
    assert _money_numbers('2 trieu') == [2000000.0]


def test_protect_restore_keeps_numbers_and_names():
    q = 'Doanh thu của Coca Cola 330ml trong tháng 5 năm 2026 là bao nhiêu?'
    masked, keep = protect(q, ['Coca Cola 330ml'])
    assert 'Coca' not in masked and '2026' not in masked and keep[0] == 'Coca Cola 330ml'
    assert restore(masked, keep) == q
    assert restore(masked.replace('ZZ1ZZ', ''), keep) is None
    assert guard('thang 3/2026 bn', 'tháng 4/2026 bao nhiêu') is None
    assert telex_word('được') == 'dduwowcj'


def test_is_correct_unchanged():
    assert is_correct({'type': 'number', 'answer': 5}, {'type': 'number', 'answer': 5})
    assert is_correct({'type': 'unanswerable'}, {'type': 'unanswerable'})
    assert not is_correct({'type': 'abstain'}, {'type': 'number', 'answer': 5})


def test_shorthand_money_and_mixed_dates():
    import pandas as pd
    from datamate.values import parse_datetimes, parse_number_value
    cases = {'25k': 25000, '1,39tr': 1390000, '1tr440': 1440000, '-3tr040': -3040000,
             '2 triệu': 2000000, '1.2 tỷ': 1.2e9, '55.000đ': 55000, '12k đ': 12000}
    for text, want in cases.items():
        assert parse_number_value(text)[0] == want, text
    assert parse_number_value('25 kg') == (25.0, 'kg')          # a real unit stays a unit
    col = pd.Series(['30/12/2025', '31/12', '1/1', '45660', '5 thg 1 2026'])
    got = parse_datetimes(col, allow_serial=True).dt.strftime('%Y-%m-%d').tolist()
    assert got == ['2025-12-30', '2025-12-31', '2026-01-01', '2025-01-03', '2026-01-05']


def test_dropped_parent_does_not_veto_child_key():
    """A table wrongly proposed as `order` (no order_date) is dropped after the checks;
    its low join overlap must not remove sales_line.order_id first."""
    from datamate.ingest import RawTable
    from datamate.mapper import TableMapping, TypedTables, validate_mapping
    sales = pd.DataFrame({'Mã đơn': [f'HD{i}' for i in range(20)], 'SL': [1] * 20})
    other = pd.DataFrame({'Mã đơn': [f'GH{i}' for i in range(10)]})
    typed = TypedTables({'s': RawTable('s', sales, list(sales.columns)), 'o': RawTable('o', other, list(other.columns))})
    mapping = {'s': TableMapping('s', 'sales_line', {'order_id': 'Mã đơn', 'qty': 'SL'}),
               'o': TableMapping('o', 'order', {'order_id': 'Mã đơn'})}
    validate_mapping(mapping, typed)
    assert mapping['s'].columns.get('order_id') == 'Mã đơn'


def test_vocab_cues_channel_payment_pharmacy_tet():
    from datamate.metrics import CHANNEL_SYN, PAYMENT_SYN, vocab_match
    from datamate.slots import apply_cues
    from datamate.timex import periods_of
    assert vocab_match('zalo', CHANNEL_SYN)('zalo_oa') and not vocab_match('zalo', CHANNEL_SYN)('store')
    assert vocab_match('phone', CHANNEL_SYN)('Điện thoại')
    assert vocab_match('cash', PAYMENT_SYN)('Tiền mặt') and not vocab_match('cash', PAYMENT_SYN)('Chuyển khoản')
    it = {'metric': 'revenue', 'filters': {'payment_method': 'Zalo OA'}, 'params': {}}
    apply_cues(it, 'doanh thu cac don ban qua zalo oa thang 12/2025')
    assert it['filters'] == {'channel': 'zalo'}
    it = {'metric': 'revenue', 'filters': {'payment_method': 'transfer'}, 'params': {}}
    apply_cues(it, 'doanh thu cac don tra bang tm thang 7/2026')
    assert it['filters']['payment_method'] == 'cash'
    it = {'metric': 'revenue', 'filters': {'group': 'tiêu hoá'}, 'params': {}, 'answerable': False}
    apply_cues(it, 'tru thuoc ke don ra thang 2/2026 cac mat hang con lai ban duoc bao nhieu tien')
    assert it['filters'] == {'prescription': False} and it['answerable'] is None
    it = {'metric': 'revenue', 'filters': {'product': 'Vitamin C 500mg'}, 'params': {}}
    apply_cues(it, 'thuoc co hoat chat vitamin c thang 10/2025 ban duoc tong cong bao nhieu tien')
    assert it['filters'] == {'active_ingredient': 'vitamin c'}
    assert periods_of('doanh thu tet nam nay so voi tet nam truoc', '2026-08-05') == [{'type': 'tet', 'year': 2026}]


def test_walk_in_abbreviation_and_flags():
    from datamate.rules import WALK_IN, _flag
    assert 'kl' in WALK_IN
    assert _flag(True) and _flag('TRUE') and _flag(1) and _flag('Có') and not _flag(False) and not _flag(None) \
        and not _flag('Không')


def test_augment_keeps_facts_and_heldout_families_separate():
    import random
    from datamate.augment import HELDOUT_FAMILIES, TRAIN_FAMILIES, apply, telex_word, variants
    assert not set(TRAIN_FAMILIES) & set(HELDOUT_FAMILIES)
    assert telex_word('tiền') == 'tieenf' and telex_word('nhất') == 'nhaats'
    q = 'Số kg Nếp cái hoa vàng bán được trong tháng 11/2025 là bao nhiêu?'
    for fam in TRAIN_FAMILIES + HELDOUT_FAMILIES:
        for seed in range(5):
            out = apply(q, fam, random.Random(seed), names=['Nếp cái hoa vàng'])
            assert '11/2025' in out                                    # numbers / dates never change
            if fam in ('typo', 'telex', 'filler', 'reorder', 'abbrev'):
                assert 'Nếp cái hoa vàng' in out or 'nếp cái hoa vàng' in out.lower()
    assert all(f in TRAIN_FAMILIES for f, _ in variants(q, TRAIN_FAMILIES, 3, 0))


def test_split_camel_and_readme_db_notes():
    from datamate.ingest import read_readme
    from datamate.values import split_camel
    assert split_camel('SLQuyDoi') == 'SL Quy Doi' and split_camel('MaHoaDon') == 'Ma Hoa Don'
    r = read_readme(None, text='- **Dòng hàng**: `chi_tiet_don.TriGia` là thành tiền của dòng; `don_hang.Ma` là mã.')
    assert r['columns']['chi_tiet_don']['trigia'].startswith('thành tiền')


def test_subset_table_is_not_the_order_header():
    """A debt / delivery list keyed by order id covers only part of the sales lines: it must lose the `order` role,
    the sales lines keep their order id."""
    from datamate.ingest import RawTable
    from datamate.mapper import TableMapping, TypedTables, validate_mapping
    sales = pd.DataFrame({'Mã đơn': [f'HD{i}' for i in range(20)], 'SL': [1] * 20})
    debts = pd.DataFrame({'Mã đơn': [f'HD{i}' for i in range(4)], 'Hạn': ['2025-01-0%d' % (i + 1) for i in range(4)],
                          '_file': 'd.csv', '_sheet': ''})
    typed = TypedTables({'s': RawTable('s', sales, list(sales.columns)), 'd': RawTable('d', debts, list(debts.columns))})
    mapping = {'s': TableMapping('s', 'sales_line', {'order_id': 'Mã đơn', 'qty': 'SL'}),
               'd': TableMapping('d', 'order', {'order_id': 'Mã đơn', 'order_date': 'Hạn'})}
    validate_mapping(mapping, typed)
    assert mapping['s'].columns.get('order_id') == 'Mã đơn' and 'order_id' not in mapping['d'].columns


def test_cues_only_overwrite_on_positive_evidence():
    """Found by an outside review: numbers of a month / quarter are not top-k; 'doanh số' ranks by revenue;
    growth / 'gấp mấy lần' are comparisons; status and payment words match whole words only."""
    import re
    from datamate.mapper import PAYMENT_WORDS, STATUS_WORDS
    from datamate.normalize import norm
    from datamate.rules import canonical_status
    from datamate.slots import apply_cues

    def run(question, intent):
        apply_cues(intent, norm(question))
        return intent
    assert run('tháng 5 khách nào mua nhiều nhất', {'metric': 'top_customers', 'params': {'k': 1}})['params']['k'] == 1
    assert run('quý 2 mặt hàng nào bán chạy nhất', {'metric': 'top_products', 'params': {'k': 1}})['params']['k'] == 1
    assert run('top 3 khách mua nhiều nhất tháng 5', {'metric': 'top_customers', 'params': {'k': 1}})['params']['k'] == 3
    assert run('tháng này 3 mặt hàng nào bán chạy nhất', {'metric': 'top_products', 'params': {'k': 1}})['params']['k'] == 3
    assert run('top 3 sản phẩm theo doanh số', {'metric': 'top_products', 'params': {'k': 3, 'by': 'revenue'}})['params']['by'] == 'revenue'
    assert run('top 3 sản phẩm bán chạy', {'metric': 'top_products', 'params': {'k': 3, 'by': 'revenue'}})['params']['by'] == 'qty'
    assert run('top 3 sản phẩm tháng này', {'metric': 'top_products', 'params': {'k': 3, 'by': 'revenue'}})['params']['by'] == 'revenue'
    for q in ('doanh thu tháng này tăng trưởng bao nhiêu %', 'doanh thu tháng này gấp mấy lần tháng trước'):
        assert run(q, {'metric': 'revenue', 'compare': 'previous'})['compare'] == 'previous'
    assert run('doanh thu tháng này', {'metric': 'revenue', 'compare': 'previous'})['compare'] is None
    assert not re.search(STATUS_WORDS, 'tra sau') and re.search(STATUS_WORDS, 'da huy')
    assert not re.search(PAYMENT_WORDS, 'them da') and re.search(PAYMENT_WORDS, 'the')
    assert canonical_status('Đã giao hàng') == 'hoàn thành' and canonical_status('Đã chốt') == 'hoàn thành'
    assert canonical_status('Chờ lấy hàng') == 'đang giao' and canonical_status('Đang giao') == 'đang giao'
    # a status filter the model invented: dropped when the metric already says it or the question names no status;
    # an unknown value never silently selects zero orders
    from datamate.rules import status_filter_value
    assert status_filter_value('cancelled') == 'huỷ' and status_filter_value('Đã huỷ') == 'huỷ'
    assert status_filter_value('completed') == 'hoàn thành' and status_filter_value('hoan_thanh') == 'hoàn thành'
    assert status_filter_value('returned') == 'trả hàng' and status_filter_value('đang giao') == 'đang giao'
    assert status_filter_value('ban_chiu') is None and status_filter_value('closed') is None
    assert 'status' not in run('8-2025 bị huỷ mấy đơn', {'metric': 'cancelled_count', 'filters': {'status': 'cancelled'}})['filters']
    assert 'status' not in run('quý 1/2026 tổng cộng có bao nhiêu đơn', {'metric': 'order_count', 'filters': {'status': 'completed'}})['filters']
    assert run('tháng 5 có bao nhiêu đơn hoàn thành', {'metric': 'order_count', 'filters': {'status': 'completed'}})['filters']['status'] == 'completed'
    assert run('tháng 5 có bao nhiêu đơn bán chịu', {'metric': 'order_count', 'filters': {'status': 'ban_chiu'}})['filters']['status'] == 'ban_chiu'
    # whole words: "huy" inside "vận CHUYển" is not a cancellation; a bare "trả" by the customer is a return
    assert canonical_status('Đang vận chuyển') == 'đang giao' and canonical_status('Đã chuyển hàng') == 'hoàn thành'
    for s in ('Đã hủy đơn', 'Huỷ', 'Khách huỷ', 'Bom hàng', 'Giao thất bại', 'Cancelled'):
        assert canonical_status(s) == 'huỷ', s
    for s in ('Khách trả', 'Khách đã trả', 'Trả', 'Đã trả', 'Hoàn', 'Trả hàng một phần', 'Hoàn đơn'):
        assert canonical_status(s) == 'trả hàng', s
    for s in ('Khách trả sau', 'Khách trả tiền', 'Đã trả tiền', 'Trả góp', 'Hoàn thành', 'Hoàn tất', 'Xong'):
        assert canonical_status(s) == 'hoàn thành', s


def test_launch_two_processes_logs_follow_the_docker_guide(tmp_path):
    """datamate.launch splits shops over 2 worker processes, merges submission.jsonl, and every log has the
    fields of the organisers' guide (id, answer = final line, elapsed_ms, thinking, code/inputs/output)."""
    import json
    import os
    import shutil
    import subprocess
    root = Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train'))
    data = tmp_path / 'data'
    (data / 'data').mkdir(parents=True)
    for biz in ('biz_101', 'biz_102'):
        shutil.copytree(root / 'data' / biz, data / 'data' / biz)
    shutil.copy(root / 'calendar.csv', data / 'calendar.csv')
    shutil.copy(root / 'rulebook.md', data / 'rulebook.md')       # as /data: the rulebook gate must stay OFF by default
    qs = [json.loads(l) for l in (root / 'questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    qs = [q for b in ('biz_101', 'biz_102') for q in [q for q in qs if q['business_id'] == b][:3]]
    (data / 'questions.jsonl').write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in qs), encoding='utf-8')
    env = dict(os.environ, DATAMATE_TEST_BACKEND='fake_backend:FakeQwen', DATAMATE_TEST_DATA=str(data),
               PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / 'tests')]), PYTHONUTF8='1')
    out = tmp_path / 'result'
    r = subprocess.run([sys.executable, '-m', 'datamate.launch', '--data-root', str(data), '--out-dir', str(out),
                        '--model', 'fake', '--gpus', '2', '--every', '1'],          # as predict.sh: no extra arguments
                       env=env, cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    sub = [json.loads(l) for l in (out / 'submission.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [s['id'] for s in sub] == [q['id'] for q in qs]
    assert (out / 'parts' / 'submission.gpu1.jsonl').exists()
    answered = 0
    for q, s in zip(qs, sub):
        log = json.loads((out / 'logs' / q['business_id'] / f"{q['id']}.json").read_text(encoding='utf-8'))
        assert log['id'] == q['id'] and log['answer'] == {k: v for k, v in s.items() if k != 'id'}
        assert isinstance(log['elapsed_ms'], int) and log['elapsed_ms'] >= 0 and 'thinking' in log
        assert log.get('route') != 'rule_gate'                 # gate off unless predict gets --rule-gate
        assert s['type'] != 'unanswerable'                     # guard: never written to the submission
        if s['type'] not in ('abstain',):
            answered += 1
            assert log['code'] and log['output'] is not None
    assert answered >= 3


RB_BASE = """# Rulebook
## 1. Đơn hàng
| Luật | Mặc định |
|---|---|
| Số đơn | chỉ tính đơn không huỷ. Đơn trả không tính |
| Tỉ lệ đơn huỷ | phần trăm đơn huỷ trong mọi đơn. Làm tròn 2 chữ số |
| Giao nhiều đợt | **Số đợt giao** = số đợt có ngày giao trong tháng |
| Tồn theo đơn vị lớn | list 2 số |
## 6. Theo ngành
### Cà phê
| Luật | Mặc định |
|---|---|
| Size M, size L | món có tên kết thúc bằng (M) hoặc (L) |
## 7. Không trả lời được
- Không có dữ liệu khác với bằng 0.
"""


def test_rulebook_parse_and_compare_statuses():
    """Format-only parsing (## sections, ### industries, table rows, bullets, bold defined terms) and the 5 statuses."""
    from datamate.rulebook import compare, parse, snapshot
    rules = parse(RB_BASE)
    assert [r.kind for r in rules] == ['row'] * 5 + ['bullet']
    assert rules[4].industry == 'Cà phê' and rules[4].section_no == 6
    assert 'so dot giao' in rules[2].triggers and 'size l' in rules[4].triggers
    covered = {r.key: ['x'] for r in rules if 'giao' not in r.key}
    base = snapshot(rules, covered)
    same, _ = compare(rules, base)
    assert [s['status'] for s in same] == ['same', 'same', 'uncovered', 'same', 'same', 'same']
    other = (RB_BASE.replace('Đơn trả không tính |', 'Đơn trả không tính. Đơn giao một phần vẫn tính |')
                    .replace('Làm tròn 2 chữ số', 'Làm tròn 1 chữ số')
                    .replace('| Tồn theo đơn vị lớn | list 2 số |\n', '')
                    + '## 3. Xếp hạng\n| Luật | Mặc định |\n|---|---|\n| Khách quen | **Khách quen** là khách có từ 3 đơn |\n')
    st, removed = compare(parse(other), base)
    by_title = {s['rule'].title: s['status'] for s in st}
    assert by_title['Số đơn'] == 'supplemented' and by_title['Tỉ lệ đơn huỷ'] == 'modified'
    assert by_title['Khách quen'] == 'new' and by_title['Giao nhiều đợt'] == 'uncovered'
    assert [b['title'] for b in removed] == ['Tồn theo đơn vị lớn']
    assert all(s['status'] == 'same' for s in compare(rules, None)[0])


def test_rule_gate_catches_new_terms_only():
    """The gate fires on a question using a NEW rule (new word) or an uncovered rule, never with the same rulebook
    on a question about a covered rule; a gated question abstains without calling the intent model."""
    from datamate.normalize import norm
    from datamate.rulebook import Gate, compare, parse, snapshot
    rules = parse(RB_BASE)
    base = snapshot(rules, {r.key: ['x'] for r in rules if 'giao' not in r.key})
    gate = Gate(*[compare(rules, base)[0], base])
    assert gate.check(norm('tháng 5 có bao nhiêu đợt giao hàng')) and not gate.check(norm('tháng 5 có bao nhiêu đơn'))
    newer = RB_BASE + '## 3. Xếp hạng\n| Luật | Mặc định |\n|---|---|\n| Khách zorba | **Khách zorba** là khách có từ 3 đơn |\n'
    g2 = Gate(compare(parse(newer), base)[0], base)
    hit = g2.check(norm('tháng này có mấy khách zorba'))
    assert hit and hit['status'] == 'new' and not g2.check(norm('tháng này có mấy khách mua hàng'))
    from datamate.pipeline import answer

    class _Shop:
        names = {}
    called = []
    out = answer(_Shop(), {'id': 'q', 'question': 'tháng này có mấy khách zorba'}, lambda *a: called.append(1), None, gate=g2)
    assert out['status'] == 'abstain' and out['route'] == 'rule_gate' and not called


def test_month_shorthand_is_parsed_not_guessed():
    """T5/2026, Th3/26, thg 5-2026, bare 5/2026, 7-2025, 8/26 all mean "month m of year y"; full dates, quarters and
    other numbers before a slash stay as written (public questions use these forms, train almost never does)."""
    from datamate.normalize import norm
    from datamate.timex import periods_of

    def month(q):
        p = periods_of(norm(q), '2026-08-08')
        return (p[0].get('month'), p[0].get('year')) if p and p[0].get('type') == 'month' else p
    for q, want in [('T7/2025 doanh thu bao nhiêu', (7, 2025)), ('Th3/2026 nhập hàng bao nhiêu tiền', (3, 2026)),
                    ('3/2026 quán bán được mấy ly', (3, 2026)), ('8/26 tiền bán là bnhiu', (8, 2026)),
                    ('7-2025 quán có mấy khách', (7, 2025)), ('Doanh thu th 2/26 so tháng trước', (2, 2026)),
                    ('T12/2025 dthu trung bình mỗi đơn', (12, 2025)), ('thg 5/2026 dthu', (5, 2026)),
                    ('doanh thu tháng 5-2026', (5, 2026)), ('tháng 6/2026 bán bao nhiêu', (6, 2026))]:
        assert month(q) == want, (q, month(q))
    # found by tests/perturb_questions.py on train: a range of bare months, and a word ending like a blocking word
    assert 'tu thang 8/2025 toi thang 10/2025' in norm('Từ 8/25 tới 10/25, tháng nào bán được nhiều tiền nhất?')
    assert 'thang 10/2025' in norm('các đơn trả bằng ví điện tử 10/2025: mỗi bên bao nhiêu?')
    assert periods_of(norm('quý 3/2026 doanh thu'), '2026-08-08') == [{'type': 'quarter', 'quarter': 3, 'year': 2026}]
    assert periods_of(norm('ngày 15/05/2026 doanh thu'), '2026-08-08')[0]['type'] == 'day'
    assert periods_of(norm('đến hết ngày 12/05/2026 còn nợ'), '2026-08-08')[0]['type'] == 'as_of'
    for q in ('top 3/2026', 'giá 3/2026', 'từ 1/1 đến 5/8', 'T2 tuần này bán'):       # not a month of a year
        assert 'thang' not in norm(q), q


def test_time_forms_found_by_question_perturbation():
    """Classes found by tests/perturb_all.py on the 24 train shops (closed Vietnamese time vocabulary, rulebook §2):
    year said relative to today, dates with - . or 2-digit year, dates in words, Q1/quý IV, counts in words,
    month ranges without a year, telex "quys", "tuần/tháng vừa rồi"."""
    from datamate.normalize import norm
    from datamate.timex import periods_of

    def per(q, as_of='2026-06-15'):
        return periods_of(norm(q), as_of)

    def m(month, year):
        return {'type': 'month', 'month': month, 'year': year}
    # "tháng M năm nay" is month M of this year, not year-to-date; "năm ngoái/năm trước" is last year
    assert per('doanh thu tháng 2 năm nay') == [m(2, 2026)]
    assert per('thang 7 nam ngoai ban bn') == [m(7, 2025)]
    assert per('quý 1 năm trước dthu') == [{'type': 'quarter', 'quarter': 1, 'year': 2025}]
    assert per('doanh thu năm nay') == [{'type': 'year_to_date'}]
    for q in ('ngày 24-03-2026 bán gì', 'ngày 24.03.2026 bán gì', 'ngày 24/03/26 bán gì', 'ngày 24 tháng 3 năm 2026 bán gì'):
        assert per(q) == [{'type': 'day', 'date': '2026-03-24'}], q
    assert per('từ ngày 21 tháng 7 năm 2025 đến hết ngày 27 tháng 7 năm 2025 có mấy món ế') == \
        [{'type': 'range', 'start': '2025-07-21', 'end': '2025-07-27'}]
    for q in ('doanh thu Q1/2026', 'doanh thu Q1 2026', 'Q1-26 doanh thu', 'doanh thu quý I/2026', 'quys 1/2026 dthu'):
        assert per(q) == [{'type': 'quarter', 'quarter': 1, 'year': 2026}], q
    assert per('dthu ba tháng liền nhau kết thúc ở tháng 12/2025') == [m(10, 2025), m(11, 2025), m(12, 2025)]
    assert per('Bảy ngày gần nhất doanh thu') == [{'type': 'last_n_days', 'n': 7}]
    # a month without a year: this year's unless it starts after today (rulebook), ranges may cross a year
    assert per('dthu 3 tháng liền nhau kết thúc ở tháng 12') == [m(10, 2025), m(11, 2025), m(12, 2025)]
    assert per('Từ tháng 8 tới tháng 10, tháng nào bán nhiều nhất') == [m(8, 2025), m(9, 2025), m(10, 2025)]
    assert per('Từ tháng 8/2025 tới tháng 10/2025') == [m(8, 2025), m(9, 2025), m(10, 2025)]
    assert per('từ tháng 11 đến tháng 2') == [m(11, 2025), m(12, 2025), m(1, 2026), m(2, 2026)]
    # months without a year: every named month counts, and a named month beats "tháng trước" (a comparison)
    assert per('Cho tôi doanh thu của tháng 8, tháng 9 và tháng 10') == \
        [{'type': 'month', 'month': 8}, {'type': 'month', 'month': 9}, {'type': 'month', 'month': 10}]
    assert per('dthu tháng 3 hơn hay kém th trước bn %') == [{'type': 'month', 'month': 3}]
    assert per('tháng trước bán bao nhiêu') == [{'type': 'last_month'}]
    assert per('dthu tuần vừa rồi') == [{'type': 'last_week'}]
    assert per('tháng vừa rồi bán bao nhiêu') == [{'type': 'last_month'}]
    for q in ('giá 1.200.000đ', 'size 1/2', 'quận 1 2026', 'q1 25 đơn', 'Thép D10 cây 11.7m'):  # not a date/quarter
        assert per(q) == [], q
    # a count written as a word before a counted noun -> digits (found by Qwen on the GPU perturbation run, 4 shops)
    assert '5 khach mua nhieu tien nhat' in norm('Cho mình năm khách mua nhiều tiền nhất tháng 6/2025.')
    assert 'it nhat 5 don' in norm('tỉ lệ khách mua ít nhất năm đơn là bnhiu %')
    assert norm('bảy ngày kể từ ngày đó').startswith('7 ngay') and 'top 3 mat hang' in norm('top ba mặt hàng')
    for q, kept in [('bà khách Lan nợ bao nhiêu', 'ba khach'), ('năm tháng gần nhất', 'nam thang'),
                    ('giá một gói', 'mot goi'), ('sau ngày 5/3/2026', 'sau ngay'), ('năm 2025 có mấy khách', 'nam 2025')]:
        assert kept in norm(q), q                       # "bà" (Mrs), "năm" (year), "một" (per), "sau" (after) stay
    for bad in (None, '', 'prod'):                      # a missing / broken as_of never crashes the tagger
        assert per('tháng 2 năm nay, từ tháng 8 tới tháng 10', bad) is not None


def test_threshold_written_next_to_filters_is_moved_only_for_metrics_that_use_it():
    """LLM output off the template: {"filters": {"min_value": X}} is params.min_value one level off. Moved for a
    metric that uses the key; for any other metric it stays an unknown filter (abstain, not an ignored condition).
    A range written start_date / end_date is the same range."""
    from datamate.intent import validate_intent
    from datamate.slots import normalize_params
    month = [{'type': 'month', 'month': 5, 'year': 2026}]
    it = {'metric': 'order_count', 'periods': month, 'filters': {'min_value': 500000, 'strict': True, 'product': 'A'}}
    normalize_params(it)
    assert it['params'] == {'min_value': 500000, 'strict': True} and it['filters'] == {'product': 'A'}
    it = {'metric': 'customers_min_orders', 'periods': month, 'filters': {'min_orders': 3}}
    normalize_params(it)
    assert it['params'] == {'threshold': 3.0} and not it['filters']
    it = {'metric': 'order_count', 'periods': month, 'filters': {'min_value': 1}, 'params': {'min_value': 2}}
    normalize_params(it)
    assert it['params']['min_value'] == 2 and not it['filters']            # params already says it: keep params
    it = {'metric': 'revenue', 'periods': month, 'filters': {'min_value': 500000}}
    normalize_params(it)
    assert it['filters'] == {'min_value': 500000} and 'unknown filter min_value' in validate_intent(it, {})
    it = {'metric': 'revenue', 'periods': [{'type': 'range', 'start_date': '2026-05-01', 'end_date': '2026-05-10'}]}
    normalize_params(it)
    assert it['periods'] == [{'type': 'range', 'start': '2026-05-01', 'end': '2026-05-10'}]


def test_status_values_beat_a_header_sharing_one_word():
    """Found by perturb_shops noreadme: with no README, a column of English statuses under an unusual header lost the
    status role to the sales-channel column "Bán qua" (shares "qua" with "kết quả")."""
    from datamate.concepts import ENTITIES
    from datamate.mapper import field_score
    status = next(f for f in ENTITIES['order'].fields if f.name == 'status')

    def card(header, values):
        return {'header': header, 'kind': 'category', 'non_null': 100, 'null_ratio': 0, 'all_values': values}
    for values in (['completed', 'cancelled', 'returned', 'shipping'], ['Đã giao', 'Đã huỷ', 'Khách trả', 'Đang vận chuyển'],
                   ['delivered', 'pending', 'refunded']):
        assert field_score(card('Xử lý', values), status, 100) > field_score(card('Bán qua', ['store', 'zalo_oa', 'phone']), status, 100)


def test_launch_guards_whole_shop_and_unanswerable():
    """datamate.launch: a shop with more than 20% of its questions "unanswerable" abstains as a whole; elsewhere only
    the unanswerable answers become abstain; other answers and questions without an answer are untouched."""
    from datamate.launch import apply_guards
    qs = [{'id': f'a{i}', 'business_id': 'bad'} for i in range(10)] + [{'id': f'b{i}', 'business_id': 'ok'} for i in range(10)]
    got = {f'a{i}': {'id': f'a{i}', 'type': 'unanswerable' if i < 3 else 'number', 'answer': i} for i in range(9)}
    got.update({f'b{i}': {'id': f'b{i}', 'type': 'unanswerable' if i < 2 else 'number', 'answer': i} for i in range(10)})
    out, why, blocked = apply_guards(qs, got)
    assert blocked == {'bad'} and 'a9' not in out                      # 3/10 > 20%; 2/10 is not
    assert all(out[f'a{i}'] == {'id': f'a{i}', 'type': 'abstain'} for i in range(9))
    assert [out[f'b{i}']['type'] for i in range(10)] == ['abstain'] * 2 + ['number'] * 8 and out['b5']['answer'] == 5
    assert set(why) == {f'a{i}' for i in range(9)} | {'b0', 'b1'} and got['a0']['type'] == 'unanswerable'
    # questions stopped by the rulebook gate are not part of the share: 2 unanswerable of the 8 evaluated = 25%
    got2 = dict(got, b8={'id': 'b8', 'type': 'abstain'}, b9={'id': 'b9', 'type': 'abstain'})
    assert apply_guards(qs, got2)[2] == {'bad'} and apply_guards(qs, got2, gated={'b8', 'b9'})[2] == {'bad', 'ok'}


def test_price_effect_and_expiry_cues_and_loose_periods():
    """Classes seen on public (15/11 13h): the model writes price-rise questions as quantity + compare 'previous'
    with a period {"type": "range", "days": N}, and puts as_of as the change date when the question gives none;
    expiry ('hạn dùng') questions are sent to another metric; a size filter that matches no product crashed."""
    import json
    import os
    from datamate.normalize import norm
    from datamate.periods import Calendar, resolve
    from datamate.pipeline import load_shop
    from datamate.metrics import run
    from datamate.scoring import is_correct
    from datamate.slots import apply_cues
    from datetime import date

    # period with a length only = the last N days up to as_of
    p = resolve({'type': 'range', 'days': 30}, date(2026, 8, 21))
    assert (p.start, p.end) == (date(2026, 7, 23), date(2026, 8, 22))

    def cue(question, intent):
        apply_cues(intent, norm(question))
        return intent
    q1 = 'Sau lần tăng giá Topping X lên 7.400 đồng, số phần bán ra trong 30 ngày kể từ ngày tăng thay đổi bao nhiêu % so với 30 ngày liền trước?'
    it = cue(q1, {'metric': 'quantity', 'compare': 'previous', 'output': 'pct', 'filters': {'product': 'Topping X'},
                  'params': {'date': '2026-08-21', 'new_price': 7400}})
    assert it['metric'] == 'price_effect' and it['params']['days'] == 30 and 'date' not in it['params']
    q2 = 'pin aa đổi giá từ 22.000đ lên 23.000đ vào ngày 02/06/2026. 14 ngày kể từ ngày đó bán được nhiều hay ít hơn 14 ngày liền trước bao nhiêu %'
    it = cue(q2, {'metric': 'price_effect', 'params': {'date': '2026-06-02', 'days': 7}})
    assert it['params'] == {'date': '2026-06-02', 'days': 14}            # a written date is kept
    assert cue('doanh thu 7 ngày sau khi tăng giá so với 7 ngày trước', {'metric': 'revenue'})['metric'] == 'revenue'
    assert cue('tháng này bán được bao nhiêu hộp', {'metric': 'quantity'})['metric'] == 'quantity'
    assert cue('còn bao nhiêu lô chưa bán hết mà hạn dùng rơi vào 120 ngày tới',
               {'metric': 'unsold_products', 'filters': {'status': 'expiring'}})['metric'] == 'expiring'
    assert cue('đơn quá hạn thanh toán', {'metric': 'debt_total'})['metric'] == 'debt_total'
    # what the question counts (abbreviations đh / bq / bnhiu, no accents)
    assert cue('Hnay tổng bnhiu đh z?', {'metric': 'revenue'})['metric'] == 'order_count'
    assert cue('Số đh ca chiều nhiều hay ít hơn ca sáng mấy %', {'metric': 'revenue'})['metric'] == 'order_count'
    assert cue('doanh thu của mấy đơn online tháng này', {'metric': 'revenue'})['metric'] == 'revenue'
    assert cue('Dthu binh quan mot dh tuan truoc bao nhieu tien?', {'metric': 'revenue'})['metric'] == 'avg_order_value'
    assert cue('Lai gop th6/2025 duoc bao nhieu z?', {'metric': 'revenue'})['metric'] == 'gross_profit'
    assert cue('Tuần trước quán bán được mấy đĩa vậy?', {'metric': 'order_count'})['metric'] == 'quantity'
    assert cue('tuần trước có mấy đơn mua 2 ly trở lên', {'metric': 'order_count'})['metric'] == 'order_count'
    it = cue('Th nay khach tra no cho quan duoc bnhiu tien roi?', {'metric': 'debt_total'})
    assert it['metric'] == 'new_debt_and_repaid' and it['params']['part'] == 'repaid'
    assert cue('khách A nợ thêm bao nhiêu và trả nợ được bao nhiêu', {'metric': 'debt_total'})['metric'] == 'debt_total'
    it = cue('9/2025 khach Ha nợ thêm bao nhiêu tiền, trả bớt được bao nhiêu?', {'metric': 'new_debt_and_repaid',
                                                                                'params': {'part': 'new'}})
    assert it['params']['part'] is None                                  # both numbers
    assert cue('2/2026 hàng mô lãi gộp nhiều nhất rứa?', {'metric': 'gross_profit'})['metric'] == 'top_products'
    assert cue('tháng 2 lãi gộp bao nhiêu', {'metric': 'gross_profit'})['metric'] == 'gross_profit'
    # a comparison the model left out; a plain "tháng trước" period is not a comparison
    it = cue('Doanh thu tháng 9/2025 so dới tháng trước lên hay xuống bao nhiêu % dậy?',
             {'metric': 'revenue', 'periods': [{'type': 'month', 'month': 9, 'year': 2025}]})
    assert it['compare'] == 'previous' and it['output'] == 'pct'
    assert not cue('doanh thu tháng trước bao nhiêu', {'metric': 'revenue', 'periods': [{'type': 'last_month'}]}).get('compare')

    # filters with no ground in the question are dropped; grounded ones (even partly, or by code) are kept
    def flt(question, filters, metric='revenue'):
        return cue(question, {'metric': metric, 'filters': dict(filters)})['filters']
    assert flt('Tuần trước bán được bao nhiêu tiền z?', {'product': 'Bay thợ hồ Total 160mm'}) == {}
    assert flt('Tháng 9/2025 Cháo ngao bán được mấy nồi?', {'product': 'Cháo nghêu'}, 'quantity') == {'product': 'Cháo nghêu'}
    assert flt('9/2025 khach Ha Duy Trung mua bao nhiêu', {'customer': 'Hà Duy Trung'}) == {'customer': 'Hà Duy Trung'}
    assert flt('khách KH023 tháng này mua bao nhiêu', {'customer': 'Lê Văn A'}) == {'customer': 'Lê Văn A'}
    assert flt('Tu dau nam den hom nay quan ban duoc bao nhieu tien', {'payment_method': 'Chuyển khoản'}) == {}
    assert flt('tháng này đơn trả chuyển khoản bao nhiêu', {'payment_method': 'transfer'}) == {'payment_method': 'transfer'}
    assert flt('7 ngay qua tinh ca hom nay ban duoc may don', {'shift': 'tinh ca'}, 'order_count') == {}
    assert flt('1/26 ca sang doanh thu duoc bao nhieu', {'shift': 'ca sang'}) == {'shift': 'ca sang'}
    assert flt('Đơn bán tại quầy tháng ni, doanh thu mấy đồng?', {'shift': 'quầy'}) == {'channel': 'store'}

    # the metric itself: compare / a days-only period added by the model do not change the price-effect answer
    root = Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train'))
    shop = load_shop(root / 'data' / 'biz_103', 'biz_103')
    cal = Calendar(root / 'calendar.csv')
    gold = {r['id']: r for r in map(json.loads, (root / 'answers.jsonl').read_text(encoding='utf-8').splitlines()) if r}
    intent = {'metric': 'price_effect', 'periods': [{'type': 'range', 'days': 14}], 'compare': 'previous', 'output': 'pct',
              'filters': {'product': 'Nước suối Lavie 1.5L'}, 'params': {'date': '2026-01-27', 'new_price': 10500}}
    got = run(shop.views, intent, '2026-07-09', cal)
    assert is_correct({'id': 'q_89bd9d9dfb79', **got}, gold['q_89bd9d9dfb79']), got
    # no date: found from the prices (first rise to the new price)
    got = run(shop.views, {**intent, 'params': {'new_price': 10500, 'days': 14}}, '2026-07-09', cal)
    assert is_correct({'id': 'q_89bd9d9dfb79', **got}, gold['q_89bd9d9dfb79']), got
    # a size written nowhere in the product names: abstain instead of crashing / answering 0
    from datamate.metrics import NeedsReview
    import pytest
    with pytest.raises(NeedsReview):
        run(shop.views, {'metric': 'quantity', 'periods': [{'type': 'this_month'}], 'filters': {'size': 'XXL'}},
            '2026-07-09', cal)


def test_order_fields_on_a_one_sheet_export():
    """Invoice and lines in ONE sheet (order info repeated on every line): the order total after the order discount
    ("Tổng thanh toán") is an order field, not the sum of the lines; a 'Tiền giảm' repeated on each line is the order
    discount, not a line discount. Found on public (debts counted 10 000 too much on every discounted order)."""
    import pandas as pd
    from types import SimpleNamespace
    from datamate.mapper import TableMapping
    from datamate.rules import header_from_lines
    from datamate.values import parse_numbers
    rows = []
    for i in range(6):
        for j in range(2):
            rows.append({'Đơn số': f'D{i}', 'Thành tiền': 100 + j, 'Tiền giảm': 10 * i, 'Tổng thanh toán': 201 - 10 * i,
                         'Da tra': 201 - 10 * i, 'Ghi chú tiền': 5 * j})
    frame = pd.DataFrame(rows)
    t = SimpleNamespace(headers=list(frame.columns), frame=frame)
    typed = SimpleNamespace(get=lambda table, h, kind: parse_numbers(frame[h])[0])
    sm = TableMapping('x', 'sales_line', {'order_id': 'Đơn số', 'line_total': 'Thành tiền', 'line_discount': 'Tiền giảm'})
    lines = pd.DataFrame({'order_id': frame['Đơn số'], 'line_total': frame['Thành tiền']})
    hdr = header_from_lines(t, sm, typed, lines)
    assert hdr is not None and list(hdr['order_total']) == [201, 191, 181, 171, 161, 151]
    assert list(hdr['order_discount']) == [0, 10, 20, 30, 40, 50] and hdr.attrs['order_discount_col'] == 'Tiền giảm'
    assert 'paid_amount' in hdr
    # a column that varies inside an order is a line field, even when its name fits an order field
    frame['Tổng thanh toán'] = [100 + k for k in range(len(frame))]
    hdr = header_from_lines(t, sm, typed, lines)
    assert hdr is not None and 'order_total' not in hdr
    # every order has one line: order- and line-level cannot be told apart -> nothing
    one = lines.assign(order_id=[f'E{k}' for k in range(len(lines))])
    assert header_from_lines(t, sm, typed, one) is None


def test_two_values_of_one_dimension_give_a_list():
    """'doanh thu đơn COD và đơn tiền mặt mỗi loại bao nhiêu' / 'tại quầy bao nhiêu, qua điện thoại bao nhiêu':
    one number per named value, in the order of the question (train gold is a list). Not for comparisons / shares."""
    from datamate.normalize import norm
    from datamate.slots import apply_cues

    def cue(question, intent):
        intent.setdefault('periods', [{'type': 'this_month'}])
        apply_cues(intent, norm(question))
        return intent
    it = cue('tháng này, dthu các ddown trả bằng cod và các đơn trả bằng tm mỗi loại bao nhiêu',
             {'metric': 'revenue', 'filters': {'payment_method': 'cash'}})
    assert it['split_by'] == ['payment_method', ['cod', 'cash']] and 'payment_method' not in it['filters']
    it = cue('6/2025 dthu don tai quay bao nhieu, don qua dien thoai bao nhieu?', {'metric': 'revenue',
                                                                              'filters': {'channel': 'phone'}})
    assert it['split_by'] == ['channel', ['store', 'phone']]
    it = cue('So doanh thu các đơn trả bằng ví điện tử với doanh thu các đơn trả bằng tiền mặt tháng 6/2026: mỗi bên bao nhiêu?',
             {'metric': 'revenue', 'compare': 'explicit'})
    assert it['split_by'] == ['payment_method', ['ewallet', 'cash']] and it['compare'] is None
    assert 'split_by' not in cue('doanh thu đơn tiền mặt chiếm bao nhiêu % so với chuyển khoản', {'metric': 'revenue'})
    assert 'split_by' not in cue('doanh thu đơn chuyển khoản tháng này', {'metric': 'revenue'})


def test_one_sales_file_per_month_is_one_table(tmp_path):
    """Found by perturb_shops split_month_t: `BanHang_T3_2025.csv`, `BanHang_Thang04_2025.csv`, `2025_05_BanHang.csv`
    (same columns) were read as separate tables, so the mapper saw one month of sales. A file with other columns and
    tables whose names differ by letters stay apart."""
    from datamate.ingest import read_business
    head = 'Mã đơn,Ngày,Tên hàng,Số lượng,Thành tiền\n'
    for i, name in enumerate(['BanHang_T3_2025', 'BanHang_Thang04_2025', '2025_05_BanHang', 'BanHang_T3_2026']):
        (tmp_path / f'{name}.csv').write_text(head + f'D{i},0{i + 1}/03/2025,Trà,1,10000\n', encoding='utf-8')
    (tmp_path / 'BanHang_T6_2025.csv').write_text('Mã khách,Tên khách\nK1,An\n', encoding='utf-8')
    (tmp_path / 'NhapHang_T3_2025.csv').write_text(head + 'N1,01/03/2025,Trà,5,40000\n', encoding='utf-8')
    tables = read_business(tmp_path)
    assert len(tables['banhang'].frame) == 4 and len(tables['banhang'].sources) == 4
    assert len(tables['nhaphang_t3'].frame) == 1                     # one file: name unchanged
    assert sorted(tables) == ['banhang', 'banhang_t6', 'nhaphang_t3']


@pytest.mark.parametrize('names', [
    ['BanHang 03.2025', 'BanHang 04.2025', 'BanHang 05.2025'],            # month.year after a space
    ['BanHang T3.2025', 'BanHang T4.2025', 'BanHang T12.2025'],
    ['BanHang_Mar_2025', 'BanHang_Apr_2025', 'BanHang_December_2025'],    # English month names
    ['DonBan_Q1_2025', 'DonBan_Q2_2025', 'DonBan_Quy3_2025'],             # one file per quarter
    ['Thang3_2025', 'Thang4_2025', 'Thang5_2025'],                         # names made only of the period
    ['BanHang_202503', 'BanHang_202504', 'BanHang_2025-05'],
])
def test_period_named_files_with_same_columns_are_one_table(tmp_path, names):
    """Generalisation of the month join (perturb families split_month_dot / split_month_en): any common way of
    putting the month / quarter in a file name gives ONE table when the columns are the same."""
    from datamate.ingest import read_business
    head = 'Mã đơn,Ngày,Tên hàng,Số lượng,Thành tiền\n'
    for i, name in enumerate(names):
        (tmp_path / f'{name}.csv').write_text(head + f'D{i},0{i + 1}/03/2025,Trà,1,10000\n', encoding='utf-8')
    (tmp_path / 'KhachHang.csv').write_text('Mã khách,Tên khách\nK1,An\n', encoding='utf-8')
    tables = read_business(tmp_path)
    sales = [t for n, t in tables.items() if n != 'khachhang']
    assert len(tables) == 2 and len(sales) == 1 and len(sales[0].frame) == 3, sorted(tables)


def test_delivery_rounds_book_and_count():
    """Rulebook "Giao nhiều đợt": a delivery book (order, round, delivery date) is its own table, not a catalogue or a
    purchase list; rounds in month X = (order, round) pairs delivered in X. Train gold of two shops with differently
    named books; the cue picks only questions that count rounds."""
    import os
    from datamate.metrics import NeedsReview, run
    from datamate.normalize import norm
    from datamate.periods import Calendar
    from datamate.pipeline import load_shop
    from datamate.slots import apply_cues
    import pytest
    root = Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train'))
    cal = Calendar(root / 'calendar.csv')
    for biz, (y, m, gold) in (('biz_117', (2026, 1, 872)), ('biz_118', (2025, 7, 983))):
        shop = load_shop(root / 'data' / biz, biz)
        assert 'delivery' in {mp.entity for mp in shop.mapping.values()}
        assert 'purchase_line' not in {mp.entity for t, mp in shop.mapping.items() if 'giao' in t}
        got = run(shop.views, {'metric': 'delivery_batches', 'periods': [{'type': 'month', 'month': m, 'year': y}]},
                  '2026-09-10', cal)
        assert got == {'answer': gold, 'type': 'number'}
        with pytest.raises(NeedsReview):                # orders by number of rounds: not defined -> abstain
            run(shop.views, {'metric': 'delivery_batches', 'periods': [{'type': 'month', 'month': m, 'year': y}],
                             'params': {'min_batches': 2}}, '2026-09-10', cal)

    def cue(question, metric='revenue'):
        it = {'metric': metric, 'periods': [{'type': 'this_month'}], 'filters': {'product': 'X'}}
        apply_cues(it, norm(question))
        return it
    assert cue('tháng 8/2025 xe ddax giao total mấy đợt hàng')['metric'] == 'delivery_batches'
    assert cue('Đếm số đợt giao hàng trong tháng 4/2025.')['metric'] == 'delivery_batches'
    it = cue('Tới hôm nay, mấy đơn đặt tháng 6/2025 đã được chở thành 2 đợt trở lên?', 'order_count')
    assert it['metric'] == 'delivery_batches' and it['params']['min_batches'] == 2
    assert cue('tháng này giao hàng được bao nhiêu đơn', 'order_count')['metric'] == 'order_count'
    assert cue('doanh thu đợt khuyến mãi tháng này')['metric'] == 'revenue'


def test_shop_without_sales_table_abstains_cleanly(tmp_path):
    """A shop whose only table is not a sales table: a sales question abstains (NeedsReview), it does not crash on a
    missing frame (a public shop crashed on every question with 'NoneType' object is not subscriptable)."""
    from datamate.metrics import NeedsReview, run
    from datamate.pipeline import load_shop
    pd.DataFrame({'Ngày chi': ['01/03/2025', '02/03/2025', '05/03/2025'] * 4, 'Mục': ['điện', 'nước', 'thuê'] * 4,
                  'So tien': [500000, 200000, 3000000] * 4, 'Ghi chú': ['', 'tháng 3', ''] * 4}) \
        .to_csv(tmp_path / 'SoTay_ChiPhi.csv', index=False)
    shop = load_shop(tmp_path, 'x')
    assert shop.views.frames.get('sales_lines') is None
    # an expense book (date, item, amount, note) is not a service book: it names no worker and no vehicle
    assert [m.entity for m in shop.mapping.values()] == ['expense']
    for metric in ('revenue', 'order_count', 'best_day', 'top_products', 'stock'):
        with pytest.raises(NeedsReview):
            run(shop.views, {'metric': metric, 'periods': [{'type': 'month', 'month': 3, 'year': 2025}],
                             'filters': {'product': 'A'} if metric == 'stock' else {}}, '2025-04-01')


def _service_shop(tmp_path):
    """Repair book with headers unlike the public shop: one row = one ticket, money = ticket total, worker nicknames,
    warranty tickets with money 0, staff list with commission %."""
    rows = [  # date, vehicle, jobs, worker, money, note
        ('01/03/2025', 'Air Blade 59A1-111.11', 'thay nhớt, vá ruột', 'anh Tâm', 100000, ''),
        ('01/03/2025', 'AB 59A1-222.22', 'bảo dưỡng', 'Tâm', 300000, ''),
        ('02/03/2025', 'Wave Alpha 59A1-333.33', 'thay bugi', 'c.Hoa', 50000, ''),
        ('02/03/2025', 'Alpha 59A1-444.44', 'làm điện', 'chị Hoa', 150000, ''),
        ('02/03/2025', 'wave 59A1-555.55', 'rửa xe', 'Hoa', 30000, ''),
        ('03/03/2025', 'air blade 59A1-111.11', 'BH vá', 'Tâm', 0, 'bảo hành'),
        ('03/03/2025', 'Air Blade 59A1-111.11', 'thay má phanh', 'Tâm', 200000, ''),
        ('04/03/2025', 'Vision 59A1-666.66', 'thay lốp', 'Hoa', 400000, ''),
    ] * 2
    pd.DataFrame(rows, columns=['Ngày làm', 'Biển số xe', 'Công việc', 'KTV', 'Thành tiền', 'Ghi chú']) \
        .to_csv(tmp_path / 'SoDichVu.csv', index=False)
    pd.DataFrame({'Họ tên': ['Lê Minh Tâm', 'Phạm Thu Hoa'], 'Hoa hồng (%)': [30, 20]}) \
        .to_csv(tmp_path / 'NhanSu.csv', index=False)
    from datamate.pipeline import load_shop
    return load_shop(tmp_path, 'x')


def test_service_book_is_read_as_tickets(tmp_path):
    """Rulebook "Sửa xe": a service book is a sales book with one ticket per row (tickets counted with warranty ones,
    average over paid tickets, workers by full name, commission = % x worker's money, vehicles by plate with short
    model names). Item-level questions abstain: jobs are free text."""
    from datamate.metrics import NeedsReview, model_matches, run
    shop = _service_shop(tmp_path)
    assert {m.entity for m in shop.mapping.values()} == {'service_ticket', 'staff'}
    assert shop.views.service_book and not shop.views.no_order_id

    def ask(metric, filters=None, params=None):
        return run(shop.views, {'metric': metric, 'periods': [{'type': 'month', 'month': 3, 'year': 2025}],
                                'filters': filters or {}, 'params': params or {}}, '2025-04-01')['answer']
    assert ask('revenue') == 2 * 1230000
    assert ask('order_count') == 16                                   # warranty tickets are tickets
    assert ask('avg_order_value') == round(2 * 1230000 / 14)          # paid tickets only
    assert ask('order_count', {'staff': 'Lê Minh Tâm'}) == 8          # 'anh Tâm', 'Tâm' -> full name
    assert ask('revenue', {'customer': 'thợ Phạm Thu Hoa'}) == 2 * 630000   # worker named in the wrong slot
    assert ask('commission', {'staff': 'Lê Minh Tâm'}) == round(0.30 * 2 * 600000)
    assert ask('commission', params={'table': True})['rows'] == [['Lê Minh Tâm', 360000], ['Phạm Thu Hoa', 252000]]
    assert ask('commission', params={'k': 1}) == 'Lê Minh Tâm'
    assert ask('top_staff', params={'by': 'orders'}) == 'Lê Minh Tâm'   # 8 vs 8 tickets: tie -> name order
    assert ask('top_staff', params={'by': 'revenue'}) == 'Phạm Thu Hoa'
    assert ask('warranty_count') == 2
    assert ask('warranty_rate') == pytest.approx(100 * 2 / 14, abs=0.01)
    assert ask('vehicle_count', params={'model': 'Air Blade'}) == 2  # 'AB' = Air Blade; same plate counted once
    assert ask('vehicle_count', params={'model': 'Wave Alpha'}) == 2  # 'Alpha' yes, 'wave' alone no
    assert ask('vehicle_count') == 6
    assert model_matches('ex', 'Exciter') and not model_matches('wave', 'Wave RSX')
    for metric, filters in (('order_count', {'product': 'vá ruột'}), ('top_products', {}), ('top_customers', {})):
        with pytest.raises(NeedsReview):
            ask(metric, filters)
    assert 'products' not in shop.names and shop.names['staff'] == ['Lê Minh Tâm', 'Phạm Thu Hoa']


def test_service_cues():
    """Service vocabulary (lượt xe / phiếu sửa, hoa hồng thợ, bảo hành, xe khác nhau) -> service metrics; sales
    questions of other shops ('phiếu nhập hàng', 'đơn') are left alone."""
    from datamate.normalize import norm
    from datamate.slots import apply_cues

    def cue(question, metric='revenue', filters=None):
        it = {'metric': metric, 'periods': [{'type': 'this_month'}], 'filters': filters or {}, 'params': {}}
        apply_cues(it, norm(question))
        return it
    it = cue('Tháng 8/2025 thợ Lê Minh Tâm lãnh bao nhiêu tiền huê hồng?', filters={'staff': 'Lê Minh Tâm'})
    assert it['metric'] == 'commission' and it['filters'] == {'staff': 'Lê Minh Tâm'}
    assert cue('Bảng hoa hồng từng thợ tháng 7, xếp giảm dần')['params'] == {'table': True}
    assert cue('Th2/2026 thợ mô hoa hồng cao nhất?')['params'] == {'k': 1}
    assert cue('tháng này thợ Tâm làm đc mí phiếu sửa xe', filters={'staff': 'Tâm'})['metric'] == 'order_count'
    assert cue('Th3/2026 thợ mô làm nhiều lượt xe nhất?', 'top_customers')['params'] == {'by': 'orders'}
    assert cue('Trong tháng 9/2025, ai là thợ chăm chỉ nhất?')['params'] == {'by': 'days'}
    assert cue('Th4/2026 thợ nào làm ra dthu cao nhất?', 'best_day')['params'] == {'by': 'revenue'}
    assert cue('Quý 2/2026 bao nhiêu lượt xe quay lại bảo hành?', 'order_count')['metric'] == 'warranty_count'
    assert cue('Quý 4 phiếu bảo hành chiếm bao nhiêu % số phiếu thu tiền?')['metric'] == 'warranty_rate'
    assert cue('không tính xe bảo hành, bình quân 1 phiếu sửa hết bao nhiêu tiền?', 'avg_order_value',
               {'product': 'xe bảo hành'}) == {'metric': 'avg_order_value', 'periods': [{'type': 'this_month'}],
                                               'filters': {}, 'params': {}, 'share_of_total': False,
                                               'split_by': None, 'compare': None, 'output': None}
    it = cue('Có bao nhiêu chiếc xe Wave Alpha khác nhau tới sửa tháng 12?', 'quantity', {'product': 'xe Wave Alpha'})
    assert it['metric'] == 'vehicle_count' and it['params'] == {'model': 'Wave Alpha'}
    assert cue('tháng 10 có mấy chiếc xe khác nhau vô sửa từ 2 lần trở lên', 'quantity')['metric'] == 'quantity'
    # not service questions
    assert cue('tháng 9/2025 tổng giá trị các phiếu nhập hàng là bao nhiêu', 'purchase_total')['metric'] == 'purchase_total'
    assert cue('tháng này bán được bao nhiêu đơn', 'order_count')['metric'] == 'order_count'
    assert cue('nhân viên nào bán được nhiều tiền nhất tháng này')['metric'] == 'revenue'
    assert cue('doanh thu bó hoa hồng tháng này', filters={'product': 'hoa hồng'})['metric'] == 'revenue'


def _selfcheck_shop(n_tables=1, roles=None, dates=None, no_order_id=False):
    """Tables with the SAME columns (one per month) + a mapping + views, for datamate.selfcheck.shop_check."""
    from types import SimpleNamespace
    head = ['Mã đơn', 'Ngày', 'Tên hàng', 'Số lượng', 'Thành tiền']
    tables, mapping = {}, {}
    roles = roles or ['sales_line'] + [None] * (n_tables - 1)
    for i, role in enumerate(roles):
        name = f'banhang_t{i + 1:02d}'
        tables[name] = SimpleNamespace(headers=head, frame=pd.DataFrame([[f'D{i}', '01/01/2025', 'Trà', 1, 10]] * 50,
                                                                          columns=head))
        mapping[name] = SimpleNamespace(entity=role)
    dates = dates if dates is not None else pd.date_range('2025-01-01', '2025-12-31', freq='D')
    views = SimpleNamespace(frames={'sales_lines': pd.DataFrame({'order_date': [d.date() for d in dates]})},
                            no_order_id=no_order_id)
    return tables, mapping, views


def test_shop_self_check_catches_a_shop_read_wrong():
    """Whole-shop guard from the DATA (not from the share of "unanswerable"): sales split over tables nobody joined,
    lines counted as orders against the README, months missing from the sales view -> block. Thresholds come from
    train (24 shops + every perturb family pass; split_month_t without the month join is caught)."""
    from datamate.selfcheck import shop_check
    readme = '- Dữ liệu có đến hết 31/12/2025.'
    assert shop_check(*_selfcheck_shop(1), readme)['block'] == []
    # 12 monthly files with the sales columns, only one read as sales (11/12 of the rows lost)
    res = shop_check(*_selfcheck_shop(12), readme)
    assert res['signals']['lost_sales'] > 0.9 and res['block']
    # ... also when the others got random roles (a series of >= 3 same-column tables)
    assert shop_check(*_selfcheck_shop(roles=['sales_line', 'expense', 'unit_conversion', 'order']), readme)['block']
    # a sales book and a purchase book written alike (a pair with two roles) is not a lost month
    assert shop_check(*_selfcheck_shop(roles=['sales_line', 'purchase_line']), readme)['block'] == []
    # every line its own order while the README says the order's info repeats on its lines
    multi = readme + '\n Sổ chi tiết bán hàng: mỗi dòng một dòng hàng, thông tin đơn lặp lại ở mọi dòng của đơn.'
    assert shop_check(*_selfcheck_shop(1, no_order_id=True), multi)['block']
    assert shop_check(*_selfcheck_shop(1, no_order_id=True), readme)['block'] == []      # hand book without numbers
    assert shop_check(*_selfcheck_shop(1), multi)['block'] == []
    # the sales view ends months before the README's end date / has an empty month inside
    early = pd.date_range('2025-01-01', '2025-03-31', freq='D')
    assert 'README end date' in ' '.join(shop_check(*_selfcheck_shop(1, dates=early), readme)['block'])
    holed = [d for d in pd.date_range('2025-01-01', '2025-12-31', freq='D') if d.month != 6]
    assert shop_check(*_selfcheck_shop(1, dates=holed), readme)['signals']['gap_months'] == ['2025-06']
    assert shop_check(*_selfcheck_shop(1, dates=holed), readme)['block']
    # a blocked shop abstains on every question without asking the intent model
    from types import SimpleNamespace
    from datamate.pipeline import answer
    shop = SimpleNamespace(report={'selfcheck': {'block': ['x']}})
    out = answer(shop, {'id': 'q', 'question': 'doanh thu tháng 3'}, lambda *a: pytest.fail('asked'), None)
    assert out['status'] == 'abstain' and out['route'] == 'shop_check'


def _stt_book(tmp_path, stt_of, blank_later=False):
    """Hand-kept sales book, one CSV per month (joined by ingest). stt_of(month, order, line, row) -> STT cell."""
    import random
    rng, row = random.Random(0), 0
    for month in (3, 4):
        rows = []
        for order in range(1, 13):
            n = 1 + order % 3                                   # 1-3 lines per order
            pay = 1000 * (order + month)
            for line in range(n):
                stt = stt_of(month, order, line, row)
                rows.append({'Ngày': f'{order:02d}/{month:02d}/2025', 'STT': None if blank_later and line else stt,
                             'Khách': f'Khách {order}', 'Hàng': rng.choice(['Ốp', 'Cáp', 'Sạc']), 'SL': 1,
                             'Thành tiền': 100 * (line + 1), 'Khách trả': pay})
                row += 1
        pd.DataFrame(rows).to_csv(tmp_path / f'SoBan_T{month}_2025.csv', index=False)
    from datamate.pipeline import load_shop
    return load_shop(tmp_path, 'x')


@pytest.mark.parametrize('blank_later', [False, True])
def test_order_number_column_is_the_order_id(tmp_path, blank_later):
    """Hand-kept book "STT: số thứ tự đơn" (lines of one order share the number, numbering restarts every month /
    sheet): STT is the order id, keyed with the sheet/file; the order fields repeated on the lines ("Khách trả") are
    read once per order. Without it every line was its own order (order counts unanswerable, totals per line)."""
    shop = _stt_book(tmp_path, lambda month, order, line, row: order, blank_later)
    v = shop.views
    assert not v.no_order_id
    assert len(v.frames['orders']) == 24                        # 12 orders x 2 months, numbers restart in April
    o = v.frames['orders'].sort_values('order_date')
    assert list(o['n_lines'][:3]) == [2, 3, 1] and list(o['order_total'][:3]) == [4000, 5000, 6000]
    assert any('restart per sheet' in n for n in v.notes)


@pytest.mark.parametrize('kind', ['line_number', 'row_number'])
def test_stt_that_is_not_an_order_number_is_not_used(tmp_path, kind):
    """"STT: số thứ tự dòng trong đơn" (1, 2, 1, 1, 2, 3 ...: the same few numbers in many blocks) and a plain row
    number (never repeats) are not order numbers: the book stays one sale per line, as before."""
    stt = (lambda month, order, line, row: line + 1) if kind == 'line_number' else (lambda month, order, line, row: row + 1)
    shop = _stt_book(tmp_path, stt)
    assert shop.views.no_order_id and len(shop.views.frames['orders']) == len(shop.views.frames['sales_lines'])
    from datamate.mapper import order_number_blocks
    s = order_number_blocks(pd.Series([1, 1, 2, 3, 3, 3, 4]), pd.Series(['a'] * 7))
    assert s['one_block_per_number'] == 1 and s['multi_line_orders'] == 2
    assert order_number_blocks(pd.Series([1, 2, 1, 1, 2, 3, 1]), pd.Series(['a'] * 7))['one_block_per_number'] < 0.7


def test_shop_self_check_sold_names_against_the_catalogue():
    """Sold product names mostly missing from the catalogue's name column (a book writing abbreviations that another
    column of the catalogue lists, "Ghi tắt") -> product names read wrong -> block. Train: 100% on every shop."""
    from types import SimpleNamespace
    from datamate.selfcheck import shop_check
    full = [f'Ốp lưng mẫu {i}' for i in range(30)]
    short = [f'OL{i}' for i in range(30)]
    cat = pd.DataFrame({'Ghi tắt': short, 'Tên hàng': full})
    tables = {'danhmuc': SimpleNamespace(headers=list(cat.columns), frame=cat)}
    mapping = {'danhmuc': SimpleNamespace(entity='product', table='danhmuc', columns={'product_name': 'Tên hàng'})}

    def views(names):
        return SimpleNamespace(frames={'sales_lines': pd.DataFrame({'product': names})}, no_order_id=False)
    ok = shop_check(tables, mapping, views(full), '')
    assert ok['block'] == [] and ok['signals']['sold_names_in_catalogue'] == 1.0
    assert shop_check(tables, mapping, views([n.upper() for n in full]), '')['block'] == []   # spelling-insensitive
    bad = shop_check(tables, mapping, views(full[:15] + short[15:]), '')
    assert bad['signals']['sold_names_in_catalogue'] == 0.5 and bad['block']
    assert shop_check(tables, mapping, views(short[:10]), '')['block'] == []                 # too few names to tell


def test_mapping_prompt_keeps_readme_conventions(monkeypatch):
    """build_prompt cut the README at 3000 characters: a long README lost its last section "## Quy ước" (orders over
    several lines, data end date). With DATAMATE_README_CONVENTIONS_FIRST=1 the non-column sections go first; a
    README within 3000 characters gives EXACTLY the old prompt either way (short-README shops do not change)."""
    import json
    from datamate.mapper import MAP_SYSTEM, build_prompt, concept_catalogue, mapping_to_json

    def old_prompt(text):
        user = (f'README:\n{text[:3000]}\n\nCONCEPTS:\n{concept_catalogue()}\n\n'
                f'TABLES:\n\n\nDRAFT (from header matching, may be wrong):\n'
                f'{json.dumps(mapping_to_json({}), ensure_ascii=False)}\n\nReturn the corrected JSON.')
        return [{'role': 'system', 'content': MAP_SYSTEM}, {'role': 'user', 'content': user}]
    short = '# Dữ liệu\n\n## File\n- `a.csv`\n\n## Cột trong `a.csv`\n- **Mã đơn**: mã đơn\n\n## Quy ước\n- Dữ liệu có đến hết 30/09/2026.\n'
    cols = ''.join(f'- **Cột {i}**: mô tả khá dài của cột số {i} trong sổ bán hàng\n' for i in range(120))
    long = f'# Dữ liệu\n\nSổ bán.\n\n## File\n- `a.csv`\n\n## Cột trong `a.csv`\n{cols}\n## Quy ước\n- Các dòng cùng STT là một đơn.\n'
    assert len(short) < 3000 < len(long)
    for flag in ('0', '1'):
        monkeypatch.setenv('DATAMATE_README_CONVENTIONS_FIRST', flag)
        assert build_prompt({}, {'text': short}, {}) == old_prompt(short)
    monkeypatch.setenv('DATAMATE_README_CONVENTIONS_FIRST', '0')
    assert build_prompt({}, {'text': long}, {}) == old_prompt(long)                     # default: unchanged
    assert 'cùng STT là một đơn' not in build_prompt({}, {'text': long}, {})[1]['content']
    monkeypatch.setenv('DATAMATE_README_CONVENTIONS_FIRST', '1')
    user = build_prompt({}, {'text': long}, {})[1]['content']
    assert 'cùng STT là một đơn' in user and 'Sổ bán.' in user and '**Cột 0**' in user
    assert user.index('## Quy ước') < user.index('## Cột trong')


def test_shipping_and_voucher_rows_are_not_sales_lines(tmp_path):
    """Found by perturb_shops non_item_fee: a book writing the order's shipping fee / voucher as one more line of the
    order (same order id, "Phí ship" 15 000 / "Voucher" -10 000, no quantity, no price) counted it as an item and as
    revenue. Rulebook §1: revenue = item lines, without shipping and without order discounts. A priced line with a
    quantity keeps its place even when named like that; "Phí phục vụ" stays (it counts in revenue)."""
    rows = []
    for i in range(1, 7):
        rows += [{'Mã đơn': f'D{i}', 'Ngày': f'0{i}/03/2025', 'Tên hàng': 'Trà sữa', 'Số lượng': 2, 'Đơn giá': 20000,
                  'Thành tiền': 40000},
                 {'Mã đơn': f'D{i}', 'Ngày': None, 'Tên hàng': 'Phí ship' if i % 2 else 'Voucher', 'Số lượng': None,
                  'Đơn giá': None, 'Thành tiền': 15000 if i % 2 else -10000}]
    rows.append({'Mã đơn': 'D7', 'Ngày': '07/03/2025', 'Tên hàng': 'Phí phục vụ', 'Số lượng': None, 'Đơn giá': None,
                 'Thành tiền': 5000})
    rows.append({'Mã đơn': 'D7', 'Ngày': '07/03/2025', 'Tên hàng': 'Voucher quà tặng 50k', 'Số lượng': 1,
                 'Đơn giá': 50000, 'Thành tiền': 50000})
    pd.DataFrame(rows).to_csv(tmp_path / 'BanHang.csv', index=False)
    from datamate.pipeline import load_shop
    v = load_shop(tmp_path, 'x').views
    lines, orders = v.frames['sales_lines'], v.frames['orders']
    assert not lines['product'].isin(['Phí ship', 'Voucher']).any()
    assert len(orders) == 7 and orders['revenue'].sum() == 6 * 40000 + 5000 + 50000
    assert any('shipping / voucher' in n for n in v.notes)


def test_share_of_the_total_with_no_part_named_abstains(tmp_path):
    """Public (dev_002, dev_013): "T2/2026 đơn huỷ chiếm bao nhiêu phần trăm?" -> the model gave share_of_total with a
    filter that was dropped as not in the question; part = whole -> answered 100%, which is never what is asked.
    A share with no part left abstains (NeedsReview, not "unanswerable": it must not count towards the 20% shop cap);
    a share with a part keeps its answer."""
    import pytest
    from datamate.metrics import NeedsReview, run
    from datamate.periods import Calendar
    from datamate.pipeline import load_shop
    rows = [{'Mã đơn': f'D{i}', 'Ngày': f'{1 + i % 28:02d}/03/2025', 'Tên hàng': 'Trà' if i % 4 else 'Bánh',
             'Nhóm hàng': 'đồ uống' if i % 4 else 'đồ ăn', 'Số lượng': 1, 'Đơn giá': 20000, 'Thành tiền': 20000}
            for i in range(40)]
    pd.DataFrame(rows).to_csv(tmp_path / 'BanHang.csv', index=False)
    import os
    cal = Calendar(Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train')) / 'calendar.csv')
    v = load_shop(tmp_path, 'x').views
    month = [{'type': 'month', 'month': 3, 'year': 2025}]
    got = run(v, {'metric': 'revenue', 'periods': month, 'filters': {'product': 'Bánh'}, 'share_of_total': True},
              '2025-04-10', cal)
    assert got == {'answer': 25.0, 'type': 'percent'}
    with pytest.raises(NeedsReview):
        run(v, {'metric': 'revenue', 'periods': month, 'filters': {}, 'share_of_total': True}, '2025-04-10', cal)


def test_loyal_and_big_spender_customers_follow_the_rulebook(tmp_path):
    """Rulebook: "khách trung thành nhất" = most DAYS with a purchase; "khách sộp nhất" = highest AVERAGE order value
    among customers with >= 3 orders. Public (dev_002, dev_006) answered both by total money. "sốp" alone (slang for
    the shop) is not the customer term."""
    import os
    from datamate.metrics import run
    from datamate.normalize import norm
    from datamate.periods import Calendar
    from datamate.pipeline import load_shop
    from datamate.slots import apply_cues

    def by(question):
        it = {'metric': 'top_customers', 'periods': [{'type': 'this_month'}], 'params': {'by': 'revenue'}}
        apply_cues(it, norm(question))
        return it['params'].get('by')
    assert by('Tháng 3/2025, trong các khách hàng, ai trung thành nhất?') == 'days'
    assert by('Khách sộp nhất tháng 5/2026 là ai?') == 'avg_order'
    assert by('khach hang nao sop nhat thang nay') == 'avg_order'
    assert by('Top 5 khách chi nhiều tiền nhất tuần rồi là ai?') == 'revenue'
    assert by('sốp có khách nào mua nhiều tiền nhất tháng này') == 'revenue'
    rows, n = [], 0
    for cust, orders in (('An', [(d, 1, 50000) for d in range(1, 11)]),          # 10 days, 500k
                         ('Bình', [(3, 1, 400000), (3, 2, 400000), (5, 1, 400000)]),  # 2 days, 1.2M, avg 400k
                         ('Chi', [(7, 1, 900000), (8, 1, 900000)])):          # 2 orders only: not "sộp"
        for day, k, money in orders:
            n += 1
            rows.append({'Mã đơn': f'D{n}', 'Ngày': f'{day:02d}/03/2025', 'Khách hàng': cust, 'Tên hàng': 'Trà',
                         'Số lượng': 1, 'Đơn giá': money, 'Thành tiền': money})
    pd.DataFrame(rows).to_csv(tmp_path / 'BanHang.csv', index=False)
    cal = Calendar(Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train')) / 'calendar.csv')
    v = load_shop(tmp_path, 'x').views
    it = {'metric': 'top_customers', 'periods': [{'type': 'month', 'month': 3, 'year': 2025}]}
    ask = lambda b: run(v, {**it, 'params': {'by': b}}, '2025-04-10', cal)['answer']
    assert ask('revenue') == 'Chi' and ask('days') == 'An' and ask('avg_order') == 'Bình'


def test_rulebook_ranking_terms_pick_their_metric(tmp_path):
    """Public rulebook §3 (new): "khách hay đổi ý nhất" = most cancelled orders; "mặt hàng được ưa chuộng nhất" = in the
    most orders; "ngày đắt khách nhất" = the most orders; "giờ cao điểm" = the one-hour slot (by order time) with the
    most orders, answered by its start hour. The model gave best_day / revenue for these (dev_004, dev_008)."""
    import os
    from datamate.metrics import run
    from datamate.normalize import norm
    from datamate.periods import Calendar
    from datamate.pipeline import load_shop
    from datamate.slots import apply_cues

    def cue(question, metric='revenue'):
        it = {'metric': metric, 'periods': [{'type': 'this_month'}], 'params': {}}
        apply_cues(it, norm(question))
        return it['metric'], it['params'].get('by')
    assert cue('Trong quý 3/2025, ai là khách hay đổi ý nhất của cửa hàng?', 'best_day') == ('top_customers', 'cancelled')
    assert cue('Mặt hàng được ưa chuộng nhất tháng 5/2025 là gì?', 'top_products') == ('top_products', 'orders')
    assert cue('Ngày nào đắt khách nhất trong tháng 4/2026?', 'best_day') == ('best_day', 'orders')
    assert cue('Trong tháng 3/2026, giờ cao điểm trong ngày của cửa hàng là mấy giờ?') == ('best_day', 'hour')
    assert cue('Ngày nào doanh thu cao nhất tháng 9/2025?', 'best_day') == ('best_day', None)
    rows, n = [], 0
    plan = [(2, '08:15', 'An', 'hoàn thành', 'Trà', 5), (2, '08:40', 'An', 'huỷ', 'Trà', 5), (2, '09:05', 'Bình', 'huỷ', 'Trà', 5),
            (2, '09:20', 'Bình', 'huỷ', 'Bánh', 5), (3, '08:05', 'Chi', 'hoàn thành', 'Bánh', 50),
            (4, '14:10', 'Chi', 'hoàn thành', 'Bánh', 50), (4, '08:30', 'An', 'hoàn thành', 'Kẹo', 1),
            (4, '15:00', 'Dũng', 'hoàn thành', 'Kẹo', 1)]
    for day, hm, cust, status, item, qty in plan:
        n += 1
        rows.append({'Mã đơn': f'D{n}', 'Ngày': f'{day:02d}/03/2025', 'Giờ': f'{day:02d}/03/2025 {hm}', 'Khách hàng': cust, 'Trạng thái': status,
                     'Tên hàng': item, 'Số lượng': qty, 'Đơn giá': 10000, 'Thành tiền': qty * 10000})
    pd.DataFrame(rows).to_csv(tmp_path / 'BanHang.csv', index=False)
    cal = Calendar(Path(os.environ.get('DATAMATE_TRAIN', ROOT / 'data' / 'train')) / 'calendar.csv')
    v = load_shop(tmp_path, 'x').views
    month = [{'type': 'month', 'month': 3, 'year': 2025}]
    ask = lambda metric, by: run(v, {'metric': metric, 'periods': month, 'params': {'by': by}}, '2025-04-10', cal)
    assert ask('top_customers', 'cancelled')['answer'] == 'Bình'
    assert ask('top_products', 'orders')['answer'] == 'Bánh' or ask('top_products', 'orders')['answer'] == 'Kẹo'
    assert ask('top_products', 'qty')['answer'] == 'Bánh'
    assert ask('best_day', 'orders')['answer'] == '2025-03-04'          # 3 orders not cancelled on the 4th
    assert ask('best_day', 'hour') == {'answer': 8, 'type': 'number'}


def test_undefined_judgement_of_a_person_abstains():
    """"Khách khó tính nhất", "NCC uy tín", "thợ nhiệt tình nhất", "nhân viên có tận tâm không": no rule or column defines
    these judgements (train gold of such questions: unanswerable); the model answered them by money. They abstain.
    "hàng trong kho tính theo giá vốn" is not "khó tính"; the rulebook terms (trung thành, sộp) are answered."""
    import pytest
    from datamate.metrics import NeedsReview, run
    from datamate.normalize import norm
    from datamate.slots import apply_cues

    def flag(question, metric='top_customers'):
        it = {'metric': metric, 'periods': [{'type': 'this_month'}], 'params': {}}
        apply_cues(it, norm(question))
        return it['params'].get('undefined_term')
    for q in ('Tháng 10/2025, trong các khách hàng, ai khó tính nhất?', 'Khách trung thực nhất tháng 10/2025 là ai?',
              'Xem giúp mình tháng 11/2025, nhà cung cấp uy tín của cửa hàng là ai?',
              'Trong tháng 3/2026, ai là thợ nhiệt tình nhất?', 'Nhân viên Phùng Thu Trang làm việc có tận tâm với khách không?',
              'lê phúc đạt có lễ phép, chu đáo với khách hông'):
        assert flag(q), q
    for q in ('Hết ngày 08/08/2026, hàng tồn trong kho tính giá vốn là bao nhiêu tiền?',
              'Tháng 3/2025, trong các khách hàng, ai trung thành nhất?', 'Khách sộp nhất tháng 5/2026 là ai?',
              'Top 5 khách chi nhiều tiền nhất tuần rồi là ai?'):
        assert not flag(q, 'stock_value' if 'kho' in q else 'top_customers'), q
    with pytest.raises(NeedsReview):
        run(None, {'metric': 'top_customers', 'periods': [{'type': 'this_month'}],
                   'params': {'undefined_term': 'kho tinh nhat'}}, '2025-04-10')
