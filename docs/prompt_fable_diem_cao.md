# Prompt cho Fable — vì sao đội khác đạt 0,96–1,0 còn mình ~0,4?

(Dán nguyên phần dưới vào một phiên Fable mở ở thư mục `E:\ZaloAI\datamate-ws`.)

---

Bạn là người nghiên cứu cho dự án DataMate (Zalo AI Challenge 2026). Đọc trước: `CLAUDE.md`, `docs/HIEN_TRANG.md`
(mục 0b–0g là mới nhất), `README.md`, `docker/HUONG_DAN.md`. Trả lời bằng tiếng Việt, giải thích dễ hiểu (người dùng là
sinh viên năm 1). Chỉ viết tài liệu `docs/plan_diem_cao.md`; KHÔNG sửa code.

## Bối cảnh
- Bài toán: agent offline trả lời 1000 câu hỏi tiếng Việt về dữ liệu bán hàng của 14 shop public (csv/xlsx + README mỗi
  shop, chung `rulebook.md`, `calendar.csv`). Chấm: đúng +1, sai −1, bỏ trống 0 (điểm = (đúng − sai)/1000).
- Luật: mô hình mở < 15B tham số, chạy trong Docker không mạng trên 2×RTX 5090, giới hạn 6 giờ cho cả bộ (≈ 43 giây/câu
  nếu chạy 2 GPU song song). Public test không được dùng để train/học ngưỡng/đưa vào Docker.
- Hệ thống hiện tại (v6): Qwen3.5-4B fp16 chỉ dịch câu hỏi → JSON ý định (metric + kỳ + bộ lọc), rồi thư viện phép tính
  viết tay (`datamate/metrics.py`) tính trên bảng đã ánh xạ (`mapper.py`, `rules.py`); nhiều luật sửa ý định
  (`slots.py`, `timex.py`); câu không chắc thì bỏ trống (luật chặn cả shop > 20% unanswerable, cổng rulebook).
- Điểm leaderboard thật hôm 15/11: file 13 = 0,293; file 20 = 0,340; bản Docker ước ≈ 0,42. Bản do ChatGPT/Codex tự
  giải (nhãn 3rd APIs, `runs/tham_chieu_gpt/`) = 0,908. Đội khác: 0,96, top đầu ~1,0 (chưa rõ nhãn SLM hay APIs).
- Bản Docker chỉ trả lời ~549/1000 câu, ~84% số trả lời là đúng → **mất điểm chủ yếu vì bỏ trống ~450 câu**, không phải
  vì trả lời sai. 5 shop bị chặn cả shop (cấu trúc file lạ: bán hàng tách nhiều file theo tháng, sổ nợ/sổ dịch vụ kiểu
  lạ); nhiều câu thuộc "phép tính chưa có trong thư viện" (sửa xe, trả góp, giao nhiều đợt, phải trả NCC…).

## Câu hỏi cần trả lời
1. **0,96–1,0 có khả thi với nhãn SLM (< 15B, offline) không?** Hay nhiều khả năng các đội đó nộp nhãn 3rd APIs / tự
   giải bằng LLM lớn? Nêu căn cứ (ví dụ: ChatGPT tự giải chỉ 0,908; mức 1,0 nghĩa là gần như mọi câu đều đúng).
2. **Kiến trúc nào có trần cao hơn kiến trúc "ý định + thư viện phép tính" của mình?** So sánh ít nhất:
   (a) giữ v6 và mở rộng thư viện + ánh xạ; (b) LLM viết code pandas/SQL cho từng câu, đọc README + rulebook + schema đã
   làm sạch, có tự chạy–sửa lỗi–bỏ phiếu (đường `sqlvote/` đã thử: OOM trên T4, nhưng 5090 có 32 GB); (c) lai: v6 trả lời
   khi chắc, đường viết code cho phần đang bỏ trống. Với mỗi cách: trần ước tính, rủi ro sai (−1), thời gian/câu trên 5090,
   model nào (Qwen3.5-4B/9B, Qwen2.5-Coder-14B, … tổng < 15B).
3. **Trong ~20 giờ còn lại (hạn nộp Docker chính thức 23:59 16/11, tối đa 2 lần), làm gì cho điểm tăng nhiều nhất mà ít
   rủi ro nhất?** Xếp hạng việc theo (điểm dự kiến tăng) / (giờ công + rủi ro). Có số liệu từ `docs/HIEN_TRANG.md`.
4. Những lớp lỗi lớn còn lại (5 shop bị chặn: 288 câu; phép tính chưa có: ~125 câu) — cách sửa tổng quát nào áp được
   cho shop chưa gặp ở private test?

## Ràng buộc khi phân tích
- Không đọc câu/log của 6 shop train giữ kín (biz_104, 106, 110, 114, 119, 126) và 4 shop public giữ kín (dev_001, 007,
  009, 010) khi tìm lỗi; với các shop đó chỉ dùng điểm tổng.
- Không đề xuất gắn logic với mã câu/mã shop, không dùng public để train hay học ngưỡng, không đưa tham chiếu ChatGPT vào
  Docker.
- Mỗi đề xuất phải kèm cách đo trên máy không cần GPU (24 shop train scripted `tests/run_shops.py`, replay
  `kaggle/replay_public.py` + `kaggle/score_public_ref.py --policy`, `tests/perturb_shops.py`) hoặc nói rõ cần GPU.

## Đầu ra
`docs/plan_diem_cao.md`: (1) kết luận ngắn cho câu hỏi 1–2; (2) bảng việc cho ~20 giờ tới, thứ tự làm, cách đo, điểm
dự kiến; (3) việc KHÔNG nên làm và vì sao. Ngắn gọn, ưu tiên số liệu.
