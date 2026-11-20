# DataMate — tổng kết sản phẩm và kế hoạch tiếp theo (để Fable đánh giá)

Ngày viết: 2026-11-14. Người viết: phiên Claude chính. Người đọc: Fable (đánh giá độc lập).
Tài liệu chi tiết: `CLAUDE.md`, `docs/datamate_v6_handoff.md` (nhật ký từng lần chạy), `README.md`.

> **Ràng buộc khi đánh giá:** 6 shop giữ kín **biz_104, 106, 110, 114, 119, 126** — không mở câu hỏi, log hay lỗi
> từng câu của chúng (chỉ xem điểm tổng). Mọi phân tích lỗi chỉ trên 24 shop còn lại.

---

## 1. Bài toán và ràng buộc
- Agent **offline** (Docker, không mạng) trả lời câu hỏi tiếng Việt về dữ liệu bán hàng của từng shop
  (csv/xlsx/sqlite + README riêng mỗi shop; `rulebook.md` và `calendar.csv` chung).
- Chấm: đúng **+1**, sai **−1**, bỏ trống **0** → bỏ trống khi không chắc là chiến lược hợp lệ.
- Model mở, tổng tham số < 15B. Dữ liệu train: 30 shop, 3000 câu có đáp án. Public/private test = shop và câu **chưa gặp**.
- Ràng buộc tự đặt: không logic theo ID câu hỏi / business_id; luật mới phải đến từ rulebook hoặc từ vựng chung.
- Tài nguyên: Kaggle T4 ×2, quota ~30 giờ GPU/tuần; máy local không có GPU (chỉ chạy test, scripted, replay).
- Chưa biết / cần điền: hạn nộp public & private: ______ ; giới hạn thời gian chạy mỗi câu / cả bộ test: ______.

## 2. Sản phẩm hiện có (v6)

```
ingest → profile → mapper (heuristic + Qwen + kiểm tra cố định) → rules (view chuẩn theo rulebook)
  → ý định: Qwen3.5-4B (4-bit) [+ LoRA] → timex → slots (cue) → validate → thư viện ~35 metric ─┐
  → SQL: Qwen viết SQL trên view chuẩn → sqlglot → duckdb ─────────────────────────────────────┴→ agree?
  → XLM-R P(trả lời được) → calibration: trả lời / bỏ trống / unanswerable
```

| Thành phần | Trạng thái |
|---|---|
| Tầng đọc dữ liệu (ingest/profile/mapper/rules) | Đã chạy GPU nhiều lần; sửa nhiều lớp lỗi (mục 4) |
| Ý định bằng Qwen 4B, không LoRA | Đã chạy GPU (lần 1–6) |
| Đường SQL đối chiếu | Đã chạy GPU; điểm gần bằng đường metric (237 vs 237 ở lần 6) — chưa thấy lợi ích riêng |
| LoRA ý định + dữ liệu tăng cường | **Đang chạy lần đầu (lần 7)** |
| XLM-R "trả lời được" + calibration ngưỡng | **Đang chạy lần đầu nghiêm túc (lần 7)** |
| ViT5 chuẩn hoá câu hỏi (tuỳ chọn) | Chưa chạy, đang tắt |
| sqlvote (đường tham khảo: nguyên rulebook trong prompt, K bản SQL, bỏ phiếu) | Thử 2 lần trên T4: OOM / ~3 phút/câu → **dừng** |
| Đóng gói nộp bài (`predict.sh`, `Dockerfile`, `datamate_submit/`) | Có code, notebook tạo gói; **chưa build/chạy thử Docker offline end-to-end** |
| Vận hành: resume có chữ ký, 2 GPU song song, checkpoint LoRA | Có; 2 GPU đã xác nhận chạy (lần 5–6); checkpoint LoRA chưa thử thật |

Kiểm thử local: 32 test (`tests/`) + 27 test sqlvote, tất cả qua; `tests/run_shops.py` (ý định theo kịch bản, chỉ để đo
tầng dữ liệu/tính), `kaggle/replay.py` (phát lại output Qwen cũ qua code mới), `tests/perturb_shops.py` (độ bền).

## 3. Kết quả đo — đọc kèm mức độ khách quan

### 3.1 GPU, 10 câu cuối × 30 shop = 300 câu (Qwen 4B, không LoRA)
| Lần | Code | Điểm | Đúng/Sai/Trống |
|---|---|---|---|
| 1 | v6 gốc | 93 | — |
| 2 | sửa đọc dữ liệu đợt 1 | 145 | 214/69/17 |
| 4 | sửa tiền viết tắt, ngày lẫn, footer… | 184 | 234/50/16 |
| 9B | code lần 4, Qwen3.5-9B | 184 | 236/52/12 (chậm hơn ~25%) |
| 6 | sửa 30 câu "cả LLM lẫn scripted đều sai" theo lớp | **237** | 261/24/15 |

**Cảnh báo:** các bản sửa từ lần 2 → 6 được viết khi đã nhìn lỗi của chính 300 câu này (dù đều là luật chung) →
237 là **ước lượng lạc quan**, không phải điểm khách quan. Không có lần 6 nào tụt câu (0 đúng→sai).

### 3.2 CPU, ý định theo kịch bản (đo tầng dữ liệu + tính, không đo LLM)
- 30 shop × toàn bộ 3000 câu: 1139 → 1747 → **1989** (không shop nào giảm ở mỗi bước).
- Sau khi cố định shop giữ kín, chỉ trên 24 shop: 1593 → **1663**.
- Phân tích trần ý định (300 câu lần 4, bỏ biz_116): LLM 188 = scripted 188; trần "mỗi câu lấy cái đúng" = 218
  → ở thời điểm đó **tầng ý định không phải nút thắt chính**, tầng dữ liệu/tính mới là.

### 3.3 Độ bền khi shop viết dữ liệu khác đi (24 shop, 2080 câu scripted đúng)
| Họ biến đổi | Giữ được |
|---|---|
| bỏ dấu tên cột / CamelCase–snake_case / từ đồng nghĩa (danh sách độc lập với mapper) / xáo cột / tên bảng chung chung | **100%** (trước sửa: 96.1 / 96.1 / 86.7 / 93.0%) |
| README không mô tả cột (`noreadme`) | **96.6%** — biz_129 mất 63 câu (tên cột khó đoán → bảng chi tiết đơn bị nhận sai vai) |

### 3.4 Điểm khách quan đầu tiên — đang chờ (lần 7, Kaggle kernel v9, ~7–8 giờ, dự kiến xong tối 14/11)
6 shop giữ kín × 40 câu = 240 câu. So sánh: baseline (không LoRA) ↔ LoRA ↔ LoRA+SQL ↔ +XLM-R/calibration.
Thêm: exact-match ý định của LoRA theo từng họ nhiễu — họ train (no_accent, abbrev, telex, filler) so với
họ **giữ kín** (typo, reorder) để biết LoRA có tổng quát sang kiểu viết chưa thấy không.

## 4. Đã sửa gì (theo lớp, không theo câu)
- **Đọc số/ngày:** tiền viết tắt `25k`, `1,39tr`, `1tr440`, `2 triệu`, `1.2 tỷ`; ngày `d/m` không năm lấy năm của dòng
  trước; serial Excel khi tên cột có "ngày".
- **Cấu trúc bảng:** shop chỉ có đơn (không dòng hàng); sổ không mã đơn (id tổng hợp, metric cần mã đơn → không trả lời);
  dòng tổng/footer; bảng sqlite giữ tên thật; tên cột CamelCase (`MaHoaDon`); README kiểu CSDL "`bảng.Cột` là …".
- **Ánh xạ vai bảng:** hạ vai khi thiếu cột bắt buộc; bảng cha thiếu cột không được loại khoá bảng con; bảng con
  (công nợ, giao hàng) không bị nhận là đầu đơn (luật "tập con": mã của nó nằm trọn trong bảng dòng nhưng chỉ phủ một phần);
  gán vai tham lam theo điểm từng cặp (bảng, vai); cột giảm giá phải trống/0 ở đa số dòng; danh mục nối theo tên khi sổ
  bán không có mã hàng.
- **Từ vựng/rulebook:** trạng thái huỷ/bom/giao thất bại; khách lẻ viết tắt (kl, khle, kvl); Tết năm nay/năm trước và
  cùng kỳ Tết = Tết âm năm trước; kênh bán & thanh toán qua từ điển đồng nghĩa; nhà thuốc: bảng thuộc tính [mã, hoạt chất,
  kê đơn] + bộ lọc kê đơn / hoạt chất.
- **Vận hành:** 2 GPU song song (300 câu ~1,5 giờ thay vì ~3 giờ), resume có chữ ký, kiểm tra kiến trúc model khi đổi model.

## 5. Quyết định đã chốt (Fable có thể phản biện)
1. Giữ **Qwen 4B**, bỏ 9B: cùng điểm 184, chậm hơn ~25%, các câu 9B sửa/làm hỏng gần cân nhau.
2. Dừng **sqlvote** trên T4 (OOM ở prefill do prompt ~8–10k token).
3. **Shop giữ kín cố định** từ 14/11 (chọn 6 shop ít bị "đụng" nhất khi viết luật). Các bản sửa trước ngày này có nhìn
   10 câu cuối của mọi shop → điểm giữ kín lần 7 vẫn có thể hơi lạc quan cho đường baseline.
4. Dữ liệu tăng cường SFT chỉ biến đổi câu **đã có nhãn kiểm chứng bằng đáp án** (nhãn giữ nguyên, số/ngày/tên hàng được
   bảo vệ); họ nhiễu train tách khỏi họ nhiễu đo.
5. Cue cứng trong `slots.py` vẫn giữ song song LoRA (kênh, thanh toán, nhà thuốc chỉ do cue đặt, không vào prompt LLM).

## 6. Lỗi còn lại và rủi ro
**Lỗi đã biết trên 24 shop (lần 6 + scripted):**
- Thu nợ / khách trả nợ (nhiều shop); tác động đổi giá `price_effect`; câu cần 2 đáp án (danh sách theo kênh);
  tồn kho theo đơn vị lớn; biz_124 ánh xạ sai nặng (danh mục hàng → khách hàng); "tiền tươi" = tiền mặt chưa có.
- README nghèo + tên cột khó đoán → nhận sai vai bảng (họ `noreadme`).

**Rủi ro lớn:**
1. **Tổng quát hoá sang shop lạ:** phần lớn tiến bộ đến từ luật tầng dữ liệu; shop public/private có thể có cấu trúc mới.
   Phép đo độ bền hiện chỉ biến đổi *cách đặt tên*, chưa biến đổi *cấu trúc* (tách/gộp bảng, cột tiền ghép chữ…).
2. **Mẫu giữ kín nhỏ:** 240 câu / 6 shop → sai số lớn (một shop lỗi ánh xạ có thể kéo ±20 điểm); ngưỡng calibration học trên
   chính lượng này.
3. **Chưa thử nộp bài thật:** Docker offline, thời gian mỗi câu (ước ~30–40 giây/câu/GPU T4 với 4B, gồm cả đường SQL), bộ nhớ, đọc `/data` của đề.
4. **Công cụ đo lệch:** scripted không có logic cue → đánh giá thấp câu kênh/thanh toán/nhà thuốc; replay dựng ánh xạ bằng
   heuristic → không thấy lỗi mapper LLM.
5. Nhiều hằng số rulebook đang viết cứng trong code (nếu rulebook của private đổi tham số sẽ lệch).

## 7. Kế hoạch tiếp theo (đề xuất, theo thứ tự)

| # | Việc | Cần GPU? | Điều kiện xong |
|---|---|---|---|
| 0 | Đọc lần 7: baseline vs LoRA vs +SQL vs +XLM-R/calibration trên 240 câu giữ kín; `noise_eval` theo họ; thời gian | Không | Có bảng số; **quyết định giữ/bỏ LoRA**: giữ nếu LoRA ≥ baseline trên giữ kín và họ typo/reorder không thua họ train quá nhiều |
| 1 | Chạy thử nộp bài: build Docker từ `datamate_submit/`, chạy `predict.sh` offline trên 1–2 shop, đo thời gian & bộ nhớ | Có (ngắn) hoặc CPU | `submission.jsonl` đúng định dạng, không cần mạng |
| 2 | Tầng dữ liệu: nhận vai cột theo **giá trị** (cột có giá trị trùng mã đơn/mã hàng bảng khác, cột ngày/tiền theo phân phối) | Không | `noreadme` ≥ 99%, 5 họ còn lại vẫn 100%, scripted 24 shop không tụt |
| 3 | Thêm họ biến đổi **cấu trúc** vào `perturb_shops.py` (tách bảng dòng theo tháng, gộp đầu đơn + dòng, cột tiền có chữ "đ", thêm cột rác) | Không | Đo được và sửa tới khi giữ ≥ 98% |
| 4 | Lớp lỗi trên 24 shop: thu nợ, price_effect, câu nhiều đáp án, đơn vị lớn, từ vựng thanh toán | Không | Mỗi lớp có test; scripted 24 shop tăng, không shop tụt |
| 5 | Đưa logic cue vào `scripted_intent` để công cụ đo sát đường LLM | Không | Chênh scripted vs LLM trên 24 shop giảm |
| 6 | Calibration chắc hơn: 2-fold LoRA (A→B, B→A) để có dự đoán out-of-fold cho cả 30 shop rồi mới học ngưỡng | Có (~2× LoRA) | Ngưỡng học trên 30 shop, không shop nào chấm bằng adapter đã train trên nó |
| 7 | Đọc tham số rulebook từ `rulebook.md` thay vì hằng số | Không | Đổi tham số trong rulebook giả → đáp án đổi đúng |
| 8 | Lần chạy Kaggle gộp (lần 8): mọi thay đổi 2–5 + LoRA tốt nhất + calibration, trên shop giữ kín | Có (~6–8 giờ) | Điểm giữ kín tăng so với lần 7 |

Nguyên tắc: gộp việc GPU vào ít lần chạy nhất; mỗi thay đổi báo số trước/sau trên 24 shop và (khi có GPU) trên shop giữ kín.

## 8. Câu hỏi muốn Fable đánh giá
1. Cách đo hiện tại (6 shop giữ kín + perturb đổi tên + họ nhiễu giữ kín cho LoRA) có đủ để tin vào điểm public/private
   không? Thiếu phép đo nào quan trọng nhất?
2. Với trần ý định đã đo (LLM ≈ scripted, trần 218/300), đầu tư LoRA có đáng không, hay nên dồn sức vào tầng dữ liệu và
   calibration?
3. Thứ tự kế hoạch ở mục 7 có hợp lý không? Việc nào nên bỏ / thêm (đặc biệt rủi ro chưa thử nộp bài thật)?
4. Chiến lược bỏ trống: hiện 15/300 câu bỏ trống, 24 sai. Với luật +1/−1/0, nên chỉnh ngưỡng thế nào khi chỉ có 240 câu
   giữ kín để học?
5. Có dấu hiệu overfit / luật quá đặc thù nào trong các bản sửa ở mục 4 không (đọc `datamate/mapper.py`, `rules.py`,
   `slots.py`, `metrics.py`)?
6. Thiết kế dữ liệu tăng cường (`datamate/augment.py`) có hợp lý không; nên thêm họ biến đổi nào để gần câu hỏi thật?

---

## 9. Phản hồi của Fable (14/11) và kế hoạch đã điều chỉnh

### 9.1 Đã kiểm chứng và sửa ngay (luật chung, không đổi điểm trên dữ liệu đã biết)
| Fable nêu | Kiểm chứng | Sửa |
|---|---|---|
| "tháng 5 khách nào…" → k=5; "quý 2 mặt hàng…" → k=2 | Đúng | `slots.top_k`: số đứng sau tháng/quý/tuần/năm/ngày/ca/lần… không phải k |
| "top 3 … theo doanh số" bị ép sang số lượng | Đúng | Cue `by` chỉ ghi đè khi có từ khẳng định (lãi/lời → profit; doanh thu/doanh số/tiền… → revenue; bán chạy/bán nhiều/số lượng → qty); không có từ nào → giữ ý LLM |
| "tăng trưởng bao nhiêu %", "gấp mấy lần" bị xoá so sánh | Đúng | Thêm vào từ so sánh: tăng trưởng, so sánh, biến động, gấp … lần, tăng lên/giảm xuống, sụt giảm |
| `tra`, `the` không ranh giới từ trong mapper | Đúng | `STATUS_WORDS` / `PAYMENT_WORDS` khớp nguyên từ; "trả sau/trả trước" không phải trạng thái |
| "Đã giao hàng", "Đã chốt" thành "đang giao" | Đúng (`cho` khớp trong `chot`) | "đã giao/đã nhận/đã chốt" → hoàn thành; `\bcho\b` |

Công cụ mới `tests/cue_audit.py`: phát lại log Qwen, tắt từng nhóm cue để đếm "giúp / hại" (bỏ shop giữ kín).
Trên 590 câu (lần 2, 4, 6 × 24 shop): compare_kind +14, strict +8, channel_payment +12, pharmacy +19, shift +12, không
nhóm nào làm hại câu nào. LƯU Ý: cue được viết từ chính các câu này → "không hại" là kỳ vọng, không chứng minh tổng quát;
ba lỗi Fable tìm được đều nằm ở cách hỏi CHƯA có trong train — đúng loại rủi ro của cue.

### 9.2 Đồng ý, đưa vào kế hoạch
- Lần 7 chỉ dùng để **so sánh** baseline ↔ LoRA (theo cặp câu), không làm dự báo điểm public: 6 shop giữ kín dễ hơn
  (lần 6: 0,90 điểm/câu so với 0,76 của 24 shop còn lại). Ước lượng của Fable cho shop lạ: 0,55–0,70 điểm/câu.
- LoRA: không đầu tư thêm; quyết theo lần 7 (giữ nếu hơn baseline ≥ ~10 điểm trên 240 câu). **Bỏ 2-fold LoRA.**
- Bỏ trống: giữ ngưỡng 0,5, tăng prior calibration 4 → 10–20, cân nhắc tắt "rescue" — làm sau khi có dữ liệu lần 7.
- Đường SQL: tốn ~gấp đôi thời gian mỗi câu, chưa thêm điểm; nếu đề giới hạn thời gian thì cắt trước tiên.

### 9.3 Kế hoạch mới (thay mục 7)
| # | Việc | GPU? | Ghi chú |
|---|---|---|---|
| 0 | Đọc lần 7 (so cặp câu, `noise_eval`, thời gian) → giữ/bỏ LoRA, cấu hình calibration | Không | đang chờ |
| 1 | **Chạy thử nộp bài.** Máy local không có Docker/WSL → (a) người dùng cài Docker Desktop, hoặc (b) bước notebook chạy `predict.sh` từ `datamate_submit/` trong tiến trình mới, `HF_HUB_OFFLINE=1`, không mạng, đo giây/câu và bộ nhớ | Có (ngắn) | Cần biết định dạng nộp + giới hạn thời gian của đề |
| 2 | So **mapper LLM ↔ heuristic** trên 24 shop (1 lần gọi LLM/shop), chấm scripted bằng ánh xạ LLM | Có (rất ngắn) | gộp vào lần chạy 8 |
| 3 | Đưa logic cue vào `scripted_intent` (công cụ đo trước, sửa lớp lỗi sau) | Không | |
| 4 | Perturb thêm họ **độ lớn giá trị** (tiền theo nghìn đồng, shop nhỏ < 50 đơn, hàng theo gam/viên) và **cấu trúc** (tách/gộp bảng, cột rác) → sửa ngưỡng cứng trong `mapper.value_cue` thành tương đối | Không | |
| 5 | Nhận vai cột theo giá trị (README nghèo); từ vựng kênh/thanh toán lấy từ **giá trị thật trong cột** của shop thay vì danh sách cố định | Không | |
| 6 | Lớp lỗi trên 24 shop: thu nợ, price_effect, câu nhiều đáp án, đơn vị lớn, "tiền tươi" | Không | |
| 7 | Tăng cường SFT (nếu giữ LoRA): thay giá trị (tháng, k, tên hàng — đổi cả nhãn), từ đồng nghĩa nghiệp vụ, cách nói thời gian, ghép 2 họ; giữ kín họ "diễn đạt lại" | Có | lần 8 |
| 8 | Lần chạy gộp 8: 1 + 2 + LoRA/calibration theo kết quả lần 7 | Có | |
