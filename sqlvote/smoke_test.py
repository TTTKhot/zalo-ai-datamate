"""End-to-end smoke test without a model: scripted replies go through prompt -> SQL -> vote -> scorer
on real training shops (an Excel ledger with monthly sheets, and a multi-file CSV shop).

  python -m sqlvote.smoke_test <train split dir> <cache dir>

Exit code 1 when a scripted answer no longer matches the gold answer (e.g. after changing clean.py).
"""
import sys
from pathlib import Path

from .backends import FnBackend
from .dates import load_calendar
from .run import Config, ShopRunner
from .scorer import read_jsonl

ORDERS_105 = '''WITH o AS (SELECT ma_hoa_don, MIN(ngay_giao_dich) FILTER (WHERE so_luong > 0) AS d,
  BOOL_OR(status_4tt = 'huỷ') AS huy, BOOL_OR(status_4tt = 'trả hàng' OR so_luong < 0) AS tra
  FROM sobanhang GROUP BY 1)'''


def reply(note, period, typ, sql=None, reason=None):
    head = f'NOTE: {note}\nPERIOD: {period}\nTYPE: {typ}\n'
    return head + (f'SQL:\n```sql\n{sql}\n```' if sql else f'REASON: {reason}')


CASES = {
    'biz_105': {   # ledger typed into Excel, one sheet per month, returns as negative lines
        'q_2b96cf7eb6b3': reply('doanh thu = tổng thành tiền dòng của đơn không huỷ, không trả; kỳ theo ngày đặt.',
                                '2026-01-01..2026-01-31', 'number', f'''{ORDERS_105}
SELECT SUM(s.tri_gia) FROM sobanhang s JOIN o USING (ma_hoa_don)
WHERE NOT o.huy AND NOT o.tra AND s.so_luong > 0 AND o.d BETWEEN DATE '2026-01-01' AND DATE '2026-01-31\''''),
        'q_00558c1410ef': reply('tỉ lệ huỷ = đơn huỷ / mọi đơn đặt trong kỳ.', '2025-06-01..2025-06-30', 'percent',
                                f'''{ORDERS_105}
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE huy) / COUNT(*), 2) FROM o
WHERE d BETWEEN DATE '2025-06-01' AND DATE '2025-06-30\''''),
        'q_2c664c3eaf2c': reply('tiền nhập = tổng thành tiền phiếu nhập có ngày phiếu trong kỳ.',
                                '2026-03-01..2026-03-31', 'number',
                                "SELECT SUM(thanh_tien) FROM sonhaphang WHERE ngay_nhap BETWEEN DATE '2026-03-01' AND DATE '2026-03-31'"),
        'q_281d6d8a83c6': reply('doanh thu từng tháng, từ tháng cũ đến tháng mới.', '2026-01-01..2026-03-31', 'list',
                                f'''{ORDERS_105}
SELECT SUM(s.tri_gia) FROM sobanhang s JOIN o USING (ma_hoa_don)
WHERE NOT o.huy AND NOT o.tra AND s.so_luong > 0 AND o.d BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
GROUP BY date_trunc('month', o.d) ORDER BY date_trunc('month', o.d)'''),
        'q_3ad4ff264376': reply('shop không ghi lời khen của khách.', 'none', 'unanswerable',
                                reason='Dữ liệu không ghi đánh giá của khách về nhân viên'),
    },
    'biz_129': {   # several CSV files joined by codes
        'q_07f86ff2d62b': reply('doanh thu = tổng thành tiền dòng, đơn không huỷ không trả, theo ngày bán.',
                                '2026-03-01..2026-03-31', 'number', '''SELECT SUM(c.tien_ban) FROM chi_tiet_don c
JOIN don_hang d ON c.so_ct = d.so_phieu
WHERE d.tinh_trang_don_4tt IN ('hoàn thành', 'đang giao') AND d.ngay_ban BETWEEN DATE '2026-03-01' AND DATE '2026-03-31\''''),
        'q_072e9d4f9c8e': reply('đơn huỷ = đơn có trạng thái huỷ, theo ngày bán.', '2025-01-01..2025-01-31', 'number',
                                '''SELECT COUNT(*) FROM don_hang
WHERE tinh_trang_don_4tt = 'huỷ' AND ngay_ban BETWEEN DATE '2025-01-01' AND DATE '2025-01-31\''''),
        'q_214e94e42454': reply('ngày có doanh thu cao nhất trong tháng.', '2025-06-01..2025-06-30', 'date',
                                '''SELECT d.ngay_ban FROM chi_tiet_don c JOIN don_hang d ON c.so_ct = d.so_phieu
WHERE d.tinh_trang_don_4tt IN ('hoàn thành', 'đang giao') AND d.ngay_ban BETWEEN DATE '2025-06-01' AND DATE '2025-06-30'
GROUP BY 1 ORDER BY SUM(c.tien_ban) DESC, 1 LIMIT 1'''),
    },
}


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    split, cache = Path(sys.argv[1]), Path(sys.argv[2])
    questions = {q['id']: q for q in read_jsonl(split / 'questions.jsonl')}
    golds = {g['id']: g for g in read_jsonl(split / 'answers.jsonl')}
    rulebook = (split / 'rulebook.md').read_text(encoding='utf-8')
    calendar = load_calendar(split / 'calendar.csv')
    failed = 0
    for shop, cases in CASES.items():
        current = {}
        backend = FnBackend(lambda messages: cases[current['id']])
        runner = ShopRunner(split / 'data' / shop, shop, cache, rulebook, calendar, backend, Config(k=4, workers=1))
        print(f'[{shop}] prompt prefix {len(runner.prefix)} ký tự, dữ liệu {runner.data_start} → {runner.data_end}')
        for qid in cases:
            current['id'] = qid
            rec = runner.answer(questions[qid], golds[qid])
            failed += rec['verdict'] != 'correct'
            print(f'  {rec["verdict"]:8s} {qid} -> {rec["submission"].get("answer", rec["submission"]["type"])}'
                  f' | gold {golds[qid]["answer"]} | {rec["samples"][0].get("error") or ""}')
        # the "period wholly outside the data" gate: an empty result for a 2020 period becomes unanswerable
        table = runner.meta['tables'][0]['name']
        gated = runner.evaluate(reply('kỳ trước khi shop có dữ liệu', '2020-01-01..2020-01-31', 'number',
                                      f'SELECT SUM(1) FROM {table} WHERE 1 = 0'))
        ok = gated['status'] == 'unanswerable' and gated.get('gated')
        failed += not ok
        print(f'  {"correct" if ok else "wrong":8s} cổng kỳ ngoài dữ liệu -> {gated["status"]}')
        runner.close()
    print('TẤT CẢ ĐÚNG' if not failed else f'{failed} trường hợp SAI')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
