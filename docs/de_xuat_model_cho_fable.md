# Đề xuất: giữ Qwen 4B hay dùng model lớn hơn (≤ 15B)? — để Fable đánh giá

Ngày viết: 14/11/2026, ~17h30. Người viết: phiên Claude chính. Đọc kèm: `docs/phien_fable_14-11.md`, `docs/plan.md`,
`docs/datamate_v6_handoff.md` (3 mục cuối), `docker/HUONG_DAN.md`.

> Ràng buộc giữ nguyên: không mở câu/log từng câu của 6 shop giữ kín; public test chỉ xem số tổng.

## 1. Câu hỏi của người dùng
"Với những thay đổi mới, Qwen 4B có đủ mạnh không, khi giới hạn là 15B tham số?"

## 2. Bối cảnh lúc viết
- Hạn: Test Solution (BTC chạy thử Docker trên máy thật) **23:59 15/11**, 1 lượt/ngày; nộp chính thức **23:59 16/11**.
- Máy chấm: 2 × RTX 5090 32 GB, 6 giờ cho cả private test (hướng dẫn ước ~500 câu → ~43 giây/câu nếu 1 GPU, ~86 giây
  nếu chia 2 GPU), giới hạn tổng tham số mọi model lúc suy luận ≤ 15B (gồm cả embedding/classifier).
- Đã làm hôm nay (CPU, chưa chạy GPU):
  - Gói Docker theo hướng dẫn BTC: base PyTorch 2.7.1 + CUDA 12.8, Qwen **fp16** (bỏ 4-bit trong image), mỗi GPU một
    tiến trình, ghi đáp án liên tục, log đúng định dạng.
  - Nấc 1 đường rulebook (`docs/plan.md` B1 + B3): `datamate/rulebook.py` + cổng bỏ trống câu dùng luật mới/chưa phủ.
    Scripted 24 shop 1663 → 1678 (chỉ 15 câu sai → bỏ trống). "Bỏ một luật": bắt đúng 0,40, bắt nhầm 0,65%.
    Public: cổng bắt 154/1000 câu (146 thuộc mục luật mới).
- Đang chờ: lần 7 (LoRA + XLM-R, kernel `datamate-v6-auto`); kernel public `datamate-public-auto` xếp hàng sau nó.
- Chưa có: Docker trên máy (người dùng sẽ cài), weights Qwen trên máy (~9,3 GB, chờ người dùng đồng ý tải).

## 3. Bằng chứng đã có về cỡ model
| Đo | Kết quả | Nguồn |
|---|---|---|
| 4B vs 9B, cùng code, 300 câu (10 câu cuối × 30 shop), không LoRA | **184 = 184**; 9B sửa 18 câu, làm hỏng 17; chậm hơn ~25% | lần 4 vs `runs/20261114-0313` |
| Trần tầng ý định (lần 4, bỏ biz_116) | LLM 4B 188 = scripted 188; trần "mỗi câu lấy cái đúng" 218 | handoff 14/11 |
| Các câu 9B sai khác 4B | nhiều câu cùng intent → nghi do **mapper LLM 9B** ánh xạ bảng khác, chưa phân tích | handoff 14/11 |
| 4B viết SQL một mình (lần 6, 164 câu không giữ kín) | đúng 73 / sai 61 / không ra 30 → **chính xác 54%** trên câu có kết quả | `docs/plan.md` 1.3 |
| Lỗi SQL 4B | (a) thiếu luật (cancel_rate 0/11), (b) sai hình dạng đáp án | `docs/plan.md` 1.3 |

Kết luận tạm:
- **Đường chính (Qwen viết JSON ý định → thư viện metric tính)**: 4B đủ; nút thắt là tầng đọc dữ liệu, không phải
  model. Đổi sang 9B ở đây không có bằng chứng tăng điểm.
- **Đường mới (nấc 2: Qwen đọc định nghĩa trong rulebook rồi viết SQL cho câu bị cổng bắt, ~15% câu public)**: đây là
  việc cần suy luận, 4B mới đạt ~54% khi viết SQL tự do → **chỗ này model lớn hơn có thể tạo khác biệt**. Chưa đo.

## 4. Các lựa chọn trong giới hạn 15B
| Lựa chọn | Tổng tham số | Nhận xét |
|---|---|---|
| A. 4B như hiện nay (+ cổng bỏ trống) | 4,66 + XLM-R 0,28 (+ LoRA ~0,03) | đã đo, đã có calibration; câu luật mới chỉ được 0 điểm |
| B. 9B thay hẳn 4B | 9,65 + 0,28 | lớn nhất dòng Qwen3.5 dưới 15B (27B, 35B-A3B vượt); đường chính không hơn; phải học lại calibration, LoRA 4B không dùng được |
| **C. Lai: 4B cho đường chính, 9B chỉ cho câu bị cổng bắt (nấc 2)** | 4,66 + 9,65 + 0,28 = **14,59** (+ LoRA nếu dùng ≈ 14,62) | giữ nguyên phần đã kiểm chứng; 9B chỉ chạy ~15% câu |
| D. Qwen3-14B | 14,8 | thế hệ cũ hơn, không còn chỗ cho XLM-R; không đề xuất |

Bộ nhớ của C: 4B fp16 ≈ 9,3 GB + 9B fp16 ≈ 19,3 GB = 28,6 GB cùng một card 32 GB → quá sát (còn KV cache).
Cách tránh: **chạy 2 pha** — pha 1: 4B trả lời mọi câu trên 2 GPU (như hiện nay), ghi lại câu bị cổng bắt; giải phóng 4B;
pha 2: nạp 9B, chỉ chạy câu bị cổng bắt (chia 2 GPU). Không phải chia GPU theo model, không vượt bộ nhớ.

## 5. Đề xuất cụ thể
1. **15/11 – nộp Test Solution bằng phương án A** (4B + cổng bỏ trống), để biết Docker chạy được trên 5090 và đo thời gian
   thật. Không chờ phần nấc 2.
2. **Song song, làm nấc 2 với backend thay được** (`docs/plan.md` B5 mức A + B6 phép thử ẩn luật T1–T3 + B9 notebook):
   prompt SQL có 6–8 dòng luật truy hồi, 2 bản nháp greedy, chỉ trả lời khi trùng.
3. **Một lần chạy Kaggle** đo nấc 2 với **cả 4B và 9B** trên cùng bộ câu ẩn luật của 24 shop (T1 thật ~35 câu,
   T2 ẩn metric 4 nhóm × 50, T3 thuật ngữ bịa 120) + đối chứng "không có dòng luật". T4 không chứa 9B fp16 trên 1 card
   → đo 9B bằng `device_map` qua 2 T4 (fp16, giống image) hoặc 4-bit (khác image, chỉ để so tương đối).
4. **Quy tắc chọn** (chính xác = đúng / (đúng + sai) trên câu đường rulebook trả lời):
   | Kết quả | Nộp 16/11 |
   |---|---|
   | 9B ≥ 0,75 và hơn 4B ≥ 10 điểm % | C (lai, 2 pha) |
   | 4B ≥ 0,75 | nấc 2 với 4B (không cần 9B) |
   | cả hai < 0,55, hoặc bản có luật không hơn đối chứng | A (chỉ cổng bỏ trống) |
   | ở giữa | chỉ trả lời ở ô calibration p > 0,5, còn lại bỏ trống |
5. Không đổi model của đường chính trước 16/11 (không có thời gian học lại calibration và kiểm chứng).

## 6. Rủi ro
- **Thời gian**: B5 + B6 + B9 ước 6–8 giờ viết code + 4–5 giờ GPU; nếu trễ, nộp A.
- **Kiểm chứng**: không có máy 5090; T4 chỉ đo được tương đối. Lượt Test Solution 15/11 là lần duy nhất chạy trên máy
  thật trước hạn — nếu nộp C ngày 16/11 thì phần 9B chưa từng chạy trên 5090.
- **Tái lập vòng private** (|PA nộp − PA BTC chạy lại| ≤ 0,03): đội không có GPU để tự chạy Docker; nếu tạo
  `submission.jsonl` trên Kaggle thì phải cùng độ chính xác (fp16) với image. 9B fp16 không vừa 1 T4.
- **Lấy 9B thay 4B ở mapper** (ánh xạ bảng cho shop lạ) có thể có ích nhưng lần 9B cho thấy mapper 9B làm khác và
  không tốt hơn; không đề xuất trong đợt này.
- **Thời gian chạy**: 9B chỉ chạy ~15% câu, 2 bản nháp ~20–30 giây/câu trên T4, trên 5090 nhanh hơn nhiều → không lo 6 giờ.

## 7. Câu hỏi muốn Fable đánh giá
1. Kết luận "4B đủ cho đường chính" có vững không, với bằng chứng ở mục 3 (chỉ 300 câu, 1 lần chạy mỗi model)?
2. Phương án lai C có đáng rủi ro với hạn 16/11 không, hay nên chỉ nộp A rồi dồn sức cho chất lượng cổng?
3. Thiết kế đo ở mục 5.3 (cùng bộ câu ẩn luật cho 4B và 9B) và quy tắc chọn ở 5.4 có đủ chặt với cỡ mẫu ~300 câu?
4. Chạy 2 pha (nạp 4B → giải phóng → nạp 9B) hay mỗi GPU một model — cách nào an toàn hơn cho tái lập và thời gian?
5. Có nên ưu tiên tăng độ bắt đúng của cổng (0,40 → 0,60 bằng bước hỏi Qwen ở vùng lưng chừng) trước nấc 2 không?
6. Với 154/1000 câu public bị cổng bắt mà chưa biết đúng/sai: nộp 2 bản public (có/không cổng) từ cùng một lần chạy
   có phải cách đo tốt nhất không, và có vi phạm quy định "không dùng public test để tạo thông tin" không?
