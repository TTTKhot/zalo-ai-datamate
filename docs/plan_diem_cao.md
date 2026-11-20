# Kế hoạch điểm cao — viết 00h30 16/11/2026 (còn ~23 giờ tới hạn Docker chính thức 23:59 16/11)

Tài liệu nghiên cứu, KHÔNG sửa code. Số liệu lấy từ `docs/HIEN_TRANG.md` (0b–0g, mục 11) và từ file lý do bỏ trống
`runs/20261115-1216/nop/BC_code_1730_tho.reasons.jsonl` (code chốt, đếm theo lớp; không mở câu của 4 shop public giữ kín
và 6 shop train giữ kín). "Tham chiếu" = so với bài ChatGPT tự giải (đúng ~95%); leaderboard thật ≈ tham chiếu + 0,05.

## 1. Kết luận ngắn

### Câu 1 — 0,96–1,0 có phải nhãn SLM không?
**Gần như chắc chắn không phải kết quả của một hệ SLM offline chạy một lượt.** Căn cứ:
- Điểm = (đúng − sai)/1000. 0,96 nghĩa là tối đa ~20 câu sai (980/20) hoặc 40 câu bỏ trống mà không sai câu nào.
  ~1,0 nghĩa là đúng gần cả 1000 câu, kể cả câu mập mờ.
- ChatGPT/Codex (model lớn nhất hiện có, tự chạy code, không giới hạn thời gian) chỉ đúng 954/1000 = 0,908. Một model
  < 15B, 43 giây/câu, không mạng mà hơn nó 50–90 câu là rất khó tin.
- Muốn từ 0,91 lên 1,0 phải biết câu nào đang sai → cần người đọc + nhiều model lớn đối chiếu + dò bằng leaderboard
  (5 lượt/ngày; nộp từng nhóm câu, phần còn lại bỏ trống — chính mình đã làm vậy với file 19).
- Public leaderboard nhận file jsonl tự tải lên, nhãn tự khai (mình từng khai nhầm file 19). Nó không kiểm chứng SLM.
  Chỗ kiểm chứng duy nhất là vòng private: BTC chạy lại Docker, lệch ≤ 0,03.
- Phần không chắc: một đội viết bộ đọc riêng cho từng shop public có thể đạt rất cao trên public với SLM, nhưng cách
  đó không sang được private. Ước đoán của tôi (không có số đo): hệ SLM trung thực trên public khoảng 0,6–0,8.

→ **Đừng lấy 0,96 làm mốc.** Mốc có nghĩa: bản Docker ≈ 0,425 → 0,52–0,58 trên public, và quan trọng hơn là không
vỡ trên shop private chưa gặp (điểm xếp hạng cuối là private).

### Câu 2 — kiến trúc nào trần cao hơn?
| | (a) v6 + mở rộng thư viện/ánh xạ | (b) LLM viết pandas/SQL cho mọi câu | (c) lai: v6 khi chắc, viết code cho phần bỏ trống |
|---|---|---|---|
| Trần public (ước) | 0,65–0,75 | cao nhất về lý thuyết (ChatGPT = kiểu này, 0,908), nhưng với < 15B: 0,3–0,6 | 0,6–0,8 |
| Trần trên shop/ngành chưa gặp | thấp hơn: mỗi ngành mới phải viết tay | cao hơn: đọc rulebook + README lúc chạy | cao nhất trong 3 cách |
| Rủi ro sai (−1) | thấp: 84% câu trả lời đúng (459/90) | cao: số đo của chính mình bên dưới | vừa, phụ thuộc bộ lọc tin cậy |
| Giây/câu trên 5090 | ~2–3 (ước từ T4: 1000 câu/77 phút/2 GPU = 9,2 giây; 5090 nhanh ~3–4 lần) → cả bộ ~25 phút, dùng < 10% của 6 giờ | K=4 bản nháp, prompt 8–10k token: ~45–60 (ước từ 3 phút/câu trên T4) → vượt 43 giây nếu chạy cả 1000 câu | chỉ ~450 câu bỏ trống × ~50 giây / 2 GPU ≈ 3 giờ → vừa đủ |
| Model | Qwen3.5-4B fp16 (đang dùng) | cần model code mạnh hơn 4B | 4B (ý định) + 9B (code) |
| Đo được trong 20 giờ? | Có, trên CPU | Không | Không |

Số đo đã có về đường viết code bằng 4B (đều xấu):
- Route `sql_only` (v6 bỏ trống, SQL trả lời) trên public: **1 khớp / 15 khác** (0g/12h30).
- "Chỉ trả lời khi metric = SQL": chính xác 85% nhưng điểm +0,222 < +0,376 của không SQL.
- `sqlvote` trên T4: 20 câu → 1 đúng / 3 sai / 16 bỏ trống, OOM ở prefill.
- 9B không hơn 4B ở việc dịch ý định (184 = 184; public +0,125 so với +0,137).

Ràng buộc cứng với model lớn hơn:
- **Qwen2.5-Coder-14B (~14,7B)**: fp16 ≈ 29,5 GB, không còn chỗ cho ngữ cảnh 8–10k token trên 5090 32 GB; image không có
  bitsandbytes. 14,7B + 4B > 15B → phải bỏ luôn Qwen 4B, tức đổi cả đường ý định chưa từng đo.
- **Qwen3.5-9B**: fp16 ≈ 18–19 GB, vừa một 5090. Tổng 4B (weights 9,3 GB ≈ 4,65B tham số) + 9B sát mốc 15B → phải đếm
  chính xác từ file weights trước khi tin.
- Hậu cần: image hiện 11,8 GB nén; Drive miễn phí 15 GB; ổ E còn 13 GB, ổ C 15 GB. Thêm 9B (~19 GB) là không tải lên nổi.
- Không còn lượt Test Solution, máy không có GPU → model mới sẽ chạy LẦN ĐẦU ngay trong lần chấm thật.

→ **Trong 20 giờ: chỉ làm (a).** (c) là hướng đúng về lâu dài (ngân sách thời gian còn thừa > 90%), nhưng chỉ đáng làm
khi có GPU ≥ 24 GB để đo và có lượt chạy thử Docker.

## 2. Việc cho ~23 giờ tới

### Chỗ đang mất điểm (code chốt, 1000 câu public)
| Nhóm | Câu | Hiện trạng | Nguyên nhân tầng dữ liệu (đã kiểm bằng `load_shop`, ánh xạ heuristic) |
|---|---|---|---|
| dev_002, dev_005 | 128 | chặn cả shop | bán hàng tách file theo tháng `BanHang_T1_2025` → 13–18 bảng rời (mục 11) |
| dev_011, dev_014 (điện thoại) | 103 | chặn cả shop; nếu thả: 7/15 và 0/18 | cột **STT** (số thứ tự đơn) không được nhận là mã đơn → mỗi dòng thành một đơn, mất "Bớt / Khách trả" cấp đơn; 3 sheet sổ nợ/góp/bảo hành không có vai nào |
| dev_013 (mẹ và bé) | 57 | chặn; nếu thả: 1/24 | header 2 dòng, dòng "Voucher / Dùng điểm / Phí ship" lẫn trong dòng hàng, danh sách khách bị nhận là sản phẩm |
| dev_012 (sửa xe) | 50 | 49 câu bỏ trống vì **crash `TypeError: NoneType`** | sổ "mỗi dòng một phiếu, có Ngày + Tiền" bị nhận là sổ CHI PHÍ → không có bảng bán. Qwen vẫn dịch đúng sang phép tính đã có (revenue 21, best_day 8, order_count 7, avg_order_value 4…) → **không phải thiếu phép tính** |
| 8 shop đọc được | 662 | 489 khớp / 102 khác, 71 bỏ trống (không cổng) | lệch công nợ, nhập hàng, quy đổi đơn vị; 9 câu hạn dùng chưa có phép tính |

Tức là: phần lớn "~450 câu bỏ trống" là do **đọc sai cấu trúc file**, không phải thiếu phép tính. Tham chiếu chỉ có
31/1000 câu thật sự "không trả lời được".

### Bảng việc (xếp theo điểm dự kiến / (giờ công + rủi ro))
Điểm tính trên thang public (lạc quan cho private, vì lớp lỗi được thấy từ public). Mọi việc: test fixture trong
`tests/test_v6.py` + `python -m pytest -q tests` + 24 shop train không shop nào tụt.

| # | Việc | Điểm dự kiến | Giờ | Rủi ro | Cách đo không cần GPU |
|---|---|---|---|---|---|
| 1 | **Tắt cổng rulebook** (`predict.sh` thêm `--no-rule-gate`; giữ chặn cả shop + unanswerable→bỏ trống) | **+0,018** (đo thật: 0,443 so với ≈0,425) | 0,5 | thấp | replay → phải ra đúng file 21 (+0,387 tham chiếu); chạy lại `test_launch_two_processes_logs_follow_the_docker_guide` |
| 2 | **Gộp file/sheet theo tháng** vào `ingest.read_business` (chuyển bản thử `merge_month_tables`) | **+0,079** tham chiếu (dev_002 27/7, dev_005 67/8) | 1,5–2 | thấp–vừa (đụng ingest mọi shop) | `perturb_shops.py --families rewrite split_month split_month_t`: 6,1% → 100%; 24 shop gốc không đổi bảng nào; `replay_public` + `score_public_ref --policy --by-shop` |
| 3 | **Không crash khi shop không có bảng bán**: trả lý do sạch thay cho `TypeError` | 0 (an toàn) | 0,3 | rất thấp | fixture shop chỉ có sổ chi phí → lý do "no sales table" |
| 4 | **Kiểm tra cấp shop từ dữ liệu** (bảo hiểm cho private, xem mục 3.4) | public ≈ +0,008; private: tránh mất ~0,02–0,03 mỗi shop đọc sai lọt lưới | 2–3 | vừa (chặn nhầm shop tốt) | ngưỡng đặt sao cho 24 shop train + mọi họ perturb đều qua; họ `split_month_t` KHÔNG gộp phải bị bắt |
| 5 | **Số thứ tự đơn làm mã đơn** (STT / Số TT / HĐ; trùng lặp giữa các sheet-tháng → khoá = sheet + STT) → `header_from_lines` (0d) tự lấy được "Bớt / Khách trả" cấp đơn | +0,02–0,04 (dev_011 + dev_014 = 103 câu; chỉ phần câu bán hàng) | 2–3 | vừa–cao: shop được thả mà ngành điện thoại (thu máy cũ, trả góp) chưa có luật → cần việc 4 đi kèm | họ perturb mới `stt_order`: đổi tên cột mã đơn shop train thành "STT", đánh số lại theo tháng → đáp án phải giữ 100%; replay public |
| 6 | **Sổ một dòng = một phiếu** (dev_012): shop không có bảng bán nào, có sổ Ngày + Tiền mà README không gọi là chi phí → đó là sổ bán, mỗi dòng một đơn | +0,015–0,025 (50 câu) | 2 | vừa: luật ngành sửa xe (bảo hành Tiền 0, hoa hồng thợ) chưa có | họ perturb mới `ticket_ledger`: shop train có bảng đơn → bỏ cột mã đơn + bảng dòng hàng; doanh thu/số đơn/ngày cao nhất phải giữ; shop có sổ chi phí thật không được đổi vai |
| 7 | Lệch phép tính ở shop đọc được: tuổi nợ/số khách nợ, `purchase_total`, quy đổi đơn vị top_products | +0,01–0,02 | 2–3 mỗi lớp | vừa (dễ thành vá theo câu) | chỉ sửa khi cụm ≥ vài câu ở ≥ 2 shop; replay; 4 shop public giữ kín không tụt |
| 8 | dev_013: dòng không phải hàng + header 2 dòng | +0,02–0,03 (57 câu) | 4–6 | cao | — |

**Dự kiến:** việc 1–3 → ≈ **0,52**; thêm 4–6 nếu đo ra dương → **0,55–0,58**. Việc 7–8: chỉ làm khi 1–6 xong sớm.

### Lịch (2 lần nộp chính thức, lấy lần cuối)
| Giờ | Việc |
|---|---|
| ngay | Dọn chỗ: ổ E còn 13 GB, file xuất mới ~11,8 GB; Drive 15 GB → chuyển/xoá file `.tar.gz` cũ trước khi xuất bản mới (giữ MD5 cũ). Bản cũ (MD5 `5685d677…`, ≈0,425) là **đường lui** nếu mọi thứ hỏng |
| sáng, ≤ 3 giờ công | Việc 1 + 2 + 3 → pytest, 24 shop, perturb, replay public |
| chốt A ≤ 11h | `make_context.py --no-lora --no-xlmr` → `bash docker/build.sh be_cooked` → Drive → kiểm MD5 → **nộp lần 1 (bản A) trước ~15h** |
| song song lúc build | (cần GPU, hỏi người dùng) 1 lần Kaggle 14 shop public bằng code A, fp16, ~77 phút: replay dùng ánh xạ heuristic nên KHÔNG thấy mapper LLM xử lý bảng đã gộp thế nào; kiểm chữ ký code trong log |
| 11h–17h | Việc 4 → 5 → 6, mỗi việc đo xong mới sang việc sau |
| **chốt B cứng 17h** | Chỉ build B nếu: 24 shop không tụt, perturb không tụt, replay public tăng ở cả shop đã đọc lẫn tổng 4 shop giữ kín. Không đạt → giữ A, không nộp lần 2 |
| 17h–22h30 | build B → Drive → MD5 → nộp lần 2. Quá 22h30 chưa xong → dừng, A là bản cuối |

Vòng private (20–23/11) phải tự chạy đúng image đã nộp, fp16, để lệch ≤ 0,03.

## 3. Câu 4 — cách sửa tổng quát cho shop chưa gặp
Nguyên tắc: sửa ở **tầng đọc dữ liệu** theo cách người ta ghi sổ, không theo ngành hay tên shop; mỗi lớp có một họ
biến đổi trên shop train để đo trước khi nhìn public.

1. **Một bảng bị chia nhiều file/sheet** (việc 2): gộp các bảng cùng bộ cột mà tên chỉ khác ở token ngày/tháng/năm.
   Chưa phủ, nên thêm họ đo nếu còn giờ: tháng viết chữ ("Tháng Ba"), năm chỉ nằm trong tên file, file tháng lệch 1 cột.
2. **Khoá đơn** (việc 5): cột số thứ tự/số hoá đơn là mã đơn; nếu số lặp lại giữa các sheet/tháng thì khoá gồm cả
   sheet. Trường cấp đơn lặp trên mọi dòng đã có luật ở 0d.
3. **Shop nào cũng phải có sổ bán** (việc 6): không bảng nào nhận vai bán hàng mà có sổ Ngày + Tiền → đó là sổ bán,
   mỗi dòng một đơn. Áp cho sửa xe, spa, dịch vụ… mà không cần biết ngành.
4. **Kiểm tra cấp shop từ dữ liệu** (việc 4), thay cho việc chỉ dựa vào "> 20% câu unanswerable" (dev_011 từng lọt với
   10%; file 20 không chặn shop chỉ được 0,340 so với ≈0,425 của cùng code có chặn, tham chiếu +0,284 so với +0,369 →
   chặn đúng shop đáng giá ~0,085). Tín hiệu đề xuất, ngưỡng
   lấy từ train:
   - tỉ lệ dòng của các file có dạng sổ bán thật sự vào view bán (tách tháng không gộp: chỉ 1/12);
   - có ≥ 2 bảng cùng bộ cột nhận vai khác nhau, hoặc bảng nhiều dòng không có vai nào;
   - `no_order_id` (mỗi dòng một đơn) trong khi README nói một đơn nhiều dòng;
   - view bán có tháng trống giữa kỳ, hoặc ngày cuối lệch xa "Dữ liệu có đến hết …" trong README.
   Shop trượt → bỏ trống cả shop. Đây là luật an toàn, không tăng điểm public nhiều nhưng chặn −1 hàng loạt ở private.
5. **Phép tính chưa có** (hạn dùng theo lô, giao nhiều đợt, trả góp, phải trả NCC…): KHÔNG viết thêm trong 20 giờ —
   mỗi loại chỉ 5–12 câu và private sẽ có ngành khác. Chỉ bảo đảm chúng ra **bỏ trống** (như cue `expiry` đã làm).
   Cách tổng quát thật sự cho lớp này là đường (c) ở mục 1, làm sau khi có GPU để đo.

## 4. Việc KHÔNG nên làm
| Việc | Vì sao |
|---|---|
| Đổi sang kiến trúc viết code (b)/(c) hoặc thêm model 9B/14B trước hạn | Chưa có số đo nào dương (1/15, 1/3/16); không GPU để thử; không còn Test Solution; image/Drive/ổ đĩa không đủ chỗ; hỏng = 0 điểm |
| Bật lại `--sql`, calibration, LoRA, XLM-R | Đã đo trên public: SQL −0,013 và chậm gấp đôi; LoRA −0,060; calibration không đổi câu nào |
| Đuổi theo 0,96 | Xem câu 1: không phải mốc của hệ SLM offline |
| Viết phép tính riêng cho sửa xe / điện thoại / trả góp | Vài câu mỗi loại, private có ngành khác; dễ thành luật theo shop |
| Sửa để khớp từng câu tham chiếu | Tham chiếu sai ~46 câu; chỉ sửa cụm ≥ vài câu ở ≥ 2 shop |
| Chỉnh ngưỡng 20% hoặc ngưỡng việc 4 theo public | Trái luật (học ngưỡng trên public); ngưỡng lấy từ train + perturb |
| Thả shop bị chặn khi chưa có việc 4 | Shop đọc sai mà được trả lời: dev_013 1/24, dev_014 0/18 → mất ~0,02 mỗi shop |
| Build lần 2 sau 17h, hoặc nộp B khi chưa đo đủ | Lấy lần nộp CUỐI; build + tải lên mất 4–5 giờ; B chưa chắc hơn A thì A là bản tốt hơn |
| Chạy GPU nhiều lần lẻ | Chỉ cần 1 lần Kaggle public cho code A (và 1 cho B nếu có); hỏi người dùng trước mỗi lần |

## 5. Điều chưa chắc (đọc trước khi tin số)
- Mọi "điểm dự kiến" là replay log Qwen cũ với ánh xạ **heuristic**; Docker dùng mapper có Qwen → cần 1 lần GPU xác nhận.
- Tốc độ trên 5090 là suy từ T4, chưa đo. Image chưa từng chạy Qwen thật trong Docker trên 5090 (chỉ model giả).
- Số public sau các sửa này là lạc quan cho private; private có thể có kiểu ghi sổ khác cả 14 shop public — vì vậy
  việc 4 (bảo hiểm) xếp trên việc 5–6 dù điểm public thấp hơn.
- Ước đoán về trần của (b)/(c) và về điểm "SLM trung thực 0,6–0,8" không có số đo trong dự án.
