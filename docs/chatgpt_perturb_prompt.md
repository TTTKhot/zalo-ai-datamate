# Prompt ChatGPT sinh biến thể câu hỏi (họ "mở" của `tests/perturb_all.py`)

Cách dùng:
1. `python tests/perturb_all.py chatgpt-export --train-root data/train --per-shop 5 --chunk 40 --out-dir runs/perturb/chatgpt <24 shop>`
   → các file `chunk_XX.txt` (prompt dưới đây + danh sách câu JSONL). Chỉ câu của 24 shop train không giữ kín.
2. Dán NGUYÊN một file vào một cuộc trò chuyện ChatGPT mới. Lưu câu trả lời thành `runs/perturb/chatgpt/out/chunk_XX.jsonl`.
3. `python tests/perturb_all.py chatgpt-import --train-root data/train --in runs/perturb/chatgpt/out --out runs/perturb/chatgpt/variants.jsonl`
   (tự loại dòng mất/thêm số, mất tên hàng/khách, id lạ; mở `review_sample.md` soát tay, xoá dòng sai trong `variants.jsonl`).
4. Đo: `python tests/perturb_all.py run ... --chatgpt runs/perturb/chatgpt/variants.jsonl <shop>` (họ `gpt_*`),
   hoặc đưa vào bộ GPU: `gpu-export ... --chatgpt runs/perturb/chatgpt/variants.jsonl`.

Biến thể do ChatGPT viết không phải dữ liệu train: KHÔNG đưa vào SFT/LoRA (ta dùng chúng để đo).

Phần giữa hai dấu `PROMPT` là thứ được chép vào mỗi file chunk.

<!-- PROMPT START -->
Bạn là người viết lại câu hỏi tiếng Việt. Mỗi câu dưới đây là câu một chủ cửa hàng hỏi trợ lý về dữ liệu bán hàng của shop
(doanh thu, số đơn, khách, mặt hàng, tồn kho, công nợ...). `as_of_date` là "hôm nay" của câu hỏi (chỉ để bạn hiểu, đừng chép vào câu).

Với MỖI câu, viết các biến thể sau, mỗi họ MỘT biến thể:
- `paraphrase`: đổi cấu trúc câu (đảo thành phần, đổi kiểu câu hỏi), nghĩa y hệt.
- `synonym`: thay từ chỉ số đo/hành động bằng từ đồng nghĩa CHẮC CHẮN cùng nghĩa (vd "doanh thu" → "tiền bán được",
  "số đơn" → "số hoá đơn", "khách hàng" → "người mua"). KHÔNG đổi "doanh thu" ↔ "doanh số" (doanh số có thể hiểu là số lượng),
  KHÔNG đổi "lãi gộp" ↔ "lợi nhuận", KHÔNG đổi "số lượng" ↔ "số đơn", KHÔNG đổi "huỷ" ↔ "trả hàng". Không chắc thì bỏ họ này.
- `colloquial`: giọng chủ shop nhắn tin (thân mật, có thể viết tắt quen thuộc như "dthu", "bn", "ko", "sp"), nghĩa y hệt.
- `english_mix`: chen vài từ tiếng Anh thông dụng (revenue, order, top, best seller, total, customer...), phần còn lại tiếng Việt.
- `verbose`: thêm câu dẫn hoặc lời thừa (chào, giải thích lý do hỏi) nhưng KHÔNG thêm điều kiện mới.
- `terse`: rút gọn tối đa, chỉ giữ các ý bắt buộc.

Quy định cứng (vi phạm thì dòng đó bị loại tự động):
1. Giữ NGUYÊN mọi con số, ngày, tháng, năm, quý, số tiền, phần trăm, ngưỡng ("từ 3 đơn trở lên", "trên 500.000đ"),
   viết đúng như câu gốc (không đổi "tháng 5/2026" thành "tháng 5 năm 2026", không đổi số thành chữ, không thêm số mới).
2. Giữ NGUYÊN tên mặt hàng, tên khách, tên kênh bán, hình thức thanh toán, tên nhóm hàng: viết đúng như câu gốc.
3. Không thêm, bớt hay đổi điều kiện; không đổi khoảng thời gian; không đổi "tháng này" thành tháng cụ thể hay ngược lại;
   không đổi số lượng kết quả ("top 3" vẫn là 3); không đổi loại đáp án (hỏi phần trăm vẫn hỏi phần trăm, hỏi danh sách vẫn hỏi danh sách).
4. Câu gốc có lỗi chính tả, không dấu hay viết tắt thì biến thể vẫn phải cùng nghĩa với ý người hỏi.
5. Không làm được họ nào cho một câu (vd không có từ đồng nghĩa chắc chắn) thì BỎ dòng đó, đừng viết bừa.

Đầu ra: CHỈ các dòng JSONL, mỗi dòng đúng một object `{"id": "<id của câu gốc>", "family": "<tên họ>", "variant": "<câu mới>"}`.
Không giải thích, không đánh số, không dùng code block, không thêm dòng nào khác.

Ví dụ (câu minh hoạ, không thuộc danh sách):
Vào: {"id": "q_vidu", "as_of_date": "2026-05-20", "question": "Doanh thu tháng 4/2026 của cửa hàng là bao nhiêu?"}
Ra:
{"id": "q_vidu", "family": "paraphrase", "variant": "Cửa hàng bán được doanh thu bao nhiêu trong tháng 4/2026?"}
{"id": "q_vidu", "family": "synonym", "variant": "Tiền bán được tháng 4/2026 của cửa hàng là bao nhiêu?"}
{"id": "q_vidu", "family": "colloquial", "variant": "ê dthu tháng 4/2026 shop mình bn vậy"}
{"id": "q_vidu", "family": "english_mix", "variant": "Revenue tháng 4/2026 của shop là bao nhiêu?"}
{"id": "q_vidu", "family": "verbose", "variant": "Mình đang làm báo cáo cuối tháng, cho mình hỏi doanh thu tháng 4/2026 của cửa hàng là bao nhiêu nhé?"}
{"id": "q_vidu", "family": "terse", "variant": "doanh thu tháng 4/2026?"}

Danh sách câu (mỗi dòng một câu):
<!-- PROMPT END -->
