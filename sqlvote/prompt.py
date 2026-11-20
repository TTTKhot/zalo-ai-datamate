"""Prompt builder. The shop part (rulebook + README + schema) is a fixed prefix for every question of the
shop, so a server with prefix caching (vLLM) pays for it once."""
from __future__ import annotations

SYSTEM_A = '''Bạn là chuyên gia phân tích dữ liệu bán hàng. Viết MỘT câu DuckDB SQL (chỉ SELECT) trả lời câu hỏi tiếng Việt về dữ liệu của một cửa hàng.

Luật:
1. Mọi định nghĩa (doanh thu, đơn huỷ, đơn trả hàng, kỳ, bán chạy, công nợ, tồn kho, làm tròn, cách xếp hạng khi bằng nhau...) lấy từ RULEBOOK. README của shop cho biết dữ liệu được ghi thế nào. Câu hỏi nói khác rulebook thì theo câu hỏi.
2. "Hôm nay" là as_of_date. Dùng các MỐC LỊCH đã tính sẵn, không tự nhẩm ngày. Bản ghi sau hôm nay coi như chưa xảy ra, trừ khi rulebook nói khác.
3. Chỉ dùng bảng và cột có trong SCHEMA. Tên cột là dạng không dấu; tên gốc trong file nằm trong ngoặc kép ở chú thích. Cột có đuôi _4tt là trạng thái đã quy về 4 loại; cột có đuôi _dv là đơn vị ghi kèm số lượng.
4. Tên hàng, tên khách: lấy đúng chuỗi trong mục GIÁ TRỊ KHỚP nếu có; câu hỏi có thể viết không dấu, viết tắt, teencode.
5. Hình dạng kết quả SQL theo TYPE:
   - number, percent, date, boolean, string: đúng 1 dòng 1 cột.
   - list: 1 cột nhiều dòng theo đúng thứ tự cần trả (ORDER BY rõ ràng), hoặc 1 dòng nhiều cột khi câu hỏi hỏi nhiều số theo thứ tự.
   - table: cột đầu là tên đối tượng, các cột sau là số đo theo đúng thứ tự câu hỏi nêu.
6. Làm tròn ngay trong SQL: tiền ROUND(x) về đồng; phần trăm và số trung bình khác ROUND(x, 2). percent là số phần trăm (12.4, không phải 0.124). date là 'YYYY-MM-DD', câu hỏi theo tháng thì 'YYYY-MM' (strftime).
7. Nếu theo mục "Không trả lời được" của rulebook dữ liệu không đủ để trả lời (kỳ nằm hoàn toàn ngoài khoảng ngày có dữ liệu, shop không ghi loại thông tin cần, câu hỏi chủ quan) thì TYPE là unanswerable và không viết SQL.

Trả lời đúng khuôn sau, không thêm gì khác:
NOTE: <1-3 câu ngắn: luật áp dụng, bảng/cột dùng, kỳ lấy>
PERIOD: <YYYY-MM-DD..YYYY-MM-DD là khoảng ngày câu hỏi hỏi tới, hoặc none>
TYPE: <number|percent|date|boolean|string|list|table|unanswerable>
SQL:
```sql
SELECT ...
```
(với unanswerable: thay khối SQL bằng dòng REASON: <lý do ngắn>)'''

SYSTEM_B = SYSTEM_A.replace(
    'NOTE: <1-3 câu ngắn: luật áp dụng, bảng/cột dùng, kỳ lấy>',
    'NOTE: <liệt kê ngắn theo thứ tự: (a) số đo và luật rulebook định nghĩa nó, (b) điều kiện lọc đơn, (c) kỳ, (d) cách xếp/làm tròn>')
SYSTEMS = {'A': SYSTEM_A, 'B': SYSTEM_B}

DUCKDB_TIPS = ('Ghi chú DuckDB: hằng ngày viết DATE \'2026-01-31\'; so sánh ngày của cột TIMESTAMP dùng CAST(cot AS DATE); '
               '"/" là chia số thực; date_trunc(\'month\', d), strftime(d, \'%Y-%m\'), date_diff(\'day\', a, b), '
               'EXTRACT(hour FROM ts); đếm đơn dùng COUNT(DISTINCT ma_don); gộp chuỗi không cần thiết - trả về từng dòng.')


def shop_prefix(rulebook: str, meta: dict, schema: str) -> str:
    rng = ''
    if meta.get('data_start') or meta.get('data_end'):
        rng = (f'\nKhoảng ngày có dữ liệu của shop: {meta.get("data_start") or "?"} → {meta.get("data_end") or "?"}'
               f' (theo {meta.get("date_column") or "README"}).')
    readme = (meta.get('readme') or '').strip() or '(shop không có README)'
    return (f'# RULEBOOK (của bộ dữ liệu đang trả lời)\n{rulebook.strip()}\n\n'
            f'# SHOP\n## README\n{readme}\n\n## SCHEMA (DuckDB, dữ liệu đã làm sạch định dạng)\n{schema}\n{rng}\n\n{DUCKDB_TIPS}')


def render_shot(shot: dict) -> str:
    head = f'Câu hỏi (as_of_date {shot.get("as_of", "?")}): {shot["question"]}\n'
    body = f'NOTE: {shot.get("note") or "..."}\nPERIOD: {shot.get("period") or "none"}\nTYPE: {shot["type"]}\n'
    if shot['type'] == 'unanswerable':
        return head + body + f'REASON: {shot.get("reason") or "dữ liệu không đủ"}'
    return head + body + f'SQL:\n```sql\n{shot["sql"].strip()}\n```'


def build_messages(prefix: str, question: str, as_of: str, facts: str, matches: str = '', shots=None,
                   variant: str = 'A') -> list[dict]:
    parts = [prefix]
    if shots:
        parts.append('# VÍ DỤ ĐÃ KIỂM CHỨNG (shop khác: tên bảng/cột có thể khác, chỉ tham khảo cách áp luật)\n\n'
                     + '\n\n'.join(render_shot(s) for s in shots))
    q = [f'# CÂU HỎI\nas_of_date: {as_of}\nMỐC LỊCH (đã tính sẵn):\n{facts}']
    if matches:
        q.append(f'GIÁ TRỊ KHỚP trong dữ liệu với từ trong câu hỏi:\n{matches}')
    q.append(f'Câu hỏi: {question}')
    parts.append('\n'.join(q))
    return [{'role': 'system', 'content': SYSTEMS[variant]}, {'role': 'user', 'content': '\n\n'.join(parts)}]


def repair_messages(messages: list[dict], raw: str, problem: str) -> list[dict]:
    return messages + [{'role': 'assistant', 'content': raw},
                       {'role': 'user', 'content': f'Lỗi khi chạy: {problem[:600]}\nSửa lại và trả lời đúng khuôn (NOTE / PERIOD / TYPE / SQL).'}]
