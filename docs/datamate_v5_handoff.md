# DataMate v5 — handoff

Mục tiêu: tổng quát hoá cho loại shop chưa gặp, không sửa theo từng biz / từng câu.

## Kiến trúc
```
ingest → profile (thẻ cột) → mapper (heuristic + Qwen JSON + kiểm tra cố định) → rules (view chuẩn theo rulebook)
       → intent: Qwen JSON → timex (đối chiếu kỳ) → slots (chuẩn hoá params + cue) → sanitize → validate (+1 lần sửa)
       → metrics → calibration (trả lời / bỏ trống)
```
| Module | Vai trò |
|---|---|
| values.py | parse tiền VN, số lượng có đơn vị, ngày (dd/mm, serial Excel, "1 thg 6 2025") |
| ingest.py | dò dòng tiêu đề, gộp sheet/file cùng header, đọc README |
| profile.py | thẻ cột: kiểu, tỉ lệ parse, giá trị mẫu → prompt cho LLM |
| concepts.py | khái niệm rulebook |
| mapper.py | heuristic → Qwen sửa bằng JSON → kiểm tra cố định |
| rules.py | §8 làm sạch; trạng thái; hoàn trả; đơn vị gốc; khách; công nợ §4; nhập/tồn §5 |
| periods.py | tuần, tháng, quý, N ngày, Tết âm lịch, kỳ trước / cùng kỳ |
| timex.py | nhận diện biểu thức thời gian; kỳ rõ ràng mà LLM ghi khác → dùng timex |
| slots.py | chuẩn hoá params + cue chung: so sánh, cùng kỳ tháng/năm trước, top-k, bán chạy=số lượng, ca, trở lên/trên |
| metrics.py | ~35 metric; thiếu khái niệm → unanswerable; không chắc → abstain |
| intent.py | prompt + few-shot (tên giả), sanitize, validate |
| normalize.py | telex, lỗi dấu, viết tắt |
| calibration.py | P(đúng) theo bucket, trả lời nếu P>0.5 |
| eval_grouped.py / score_run.py | chấm log; giữ kín theo shop |
| predict.py / predict.sh / Dockerfile | chạy offline, log từng câu |

## Kết quả
- Không GPU (parser kịch bản, chỉ test): 394/397 trên biz_101/103/104/106.
- Qwen3.5-4B, code cũ (chưa timex/slots), 40–50 câu đầu mỗi shop: 146 đúng / 35 sai / 9 bỏ trống → 111.
- Phát lại output đó qua code mới: 188 đúng / 2 sai → 186 (lạc quan: luật viết từ chính các lỗi này).
- Điểm khách quan: chạy SKIP_FIRST_PER_BIZ = 50 (câu chưa dùng).

## Việc tiếp theo (v6)
- LoRA Qwen trên cặp (câu hỏi → intent JSON đúng đáp án), thay dần cue rule trong slots.py.
- Đường SQL đối chiếu; XLM-R answerable làm đặc trưng calibration.
- Shop khác loại (nhà thuốc biz_124...), đủ answers.jsonl.
