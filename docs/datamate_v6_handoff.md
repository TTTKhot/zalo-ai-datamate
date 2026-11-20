# DataMate v6 — handoff (tiếp nối v5)

Mục tiêu giữ nguyên: tổng quát hoá cho loại shop chưa gặp, không gắn logic với id câu hỏi / id shop,
chạy offline, tổng tham số < 15B (thực tế < 6B), sai −1 nên ưu tiên bỏ trống khi không chắc.

## Kiến trúc v6
```
ingest → profile → mapper (heuristic + Qwen GỐC + kiểm tra cố định) → rules (view chuẩn)
  → ý định: Qwen + LoRA (prompt gọn, tên hàng lọc theo câu hỏi) → timex → slots → validate → metric ─┐
  → SQL: Qwen GỐC viết SQL trên view chuẩn → sqlglot → duckdb ───────────────────────────────────────┴→ agree
  → XLM-R P(trả lời được | câu hỏi, khả năng dữ liệu của shop)
  → calibration: trả lời / bỏ trống / cứu thành unanswerable
```
Adapter LoRA chỉ bật cho bước ý định; mapper và SQL chạy với adapter tắt (`QwenBackend.base()`), nên hai đường độc lập hơn.

## Module mới / đổi
| Module | Vai trò |
|---|---|
| sft_data.py | Bước 1: nhãn ý định đã kiểm chứng bằng đáp án. Hạt giống = parser kịch bản (chỉ dùng lúc tạo nhãn) + log Qwen cũ; nếu sai thì thử biến thể cách 1–2 bước trong từ vựng ý định; `answerable:false` chỉ là phương án cuối khi gold là unanswerable. Ghi train/val chia theo shop + report độ phủ. |
| splits.py | Chia shop theo hash tên, phân tầng theo loại dữ liệu (concepts); kfold. |
| train_lora.py | QLoRA 4-bit NF4 cho T4: LoRA r16 trên mọi Linear của phần ngôn ngữ, loss chỉ trên JSON đích, fp16 + GradScaler, gradient checkpointing, eval exact-match ý định trên shop val, dừng theo `--max-hours`. |
| intent.py | + `build_compact_messages`, `relevant_names`, `canonical_intent`. |
| pipeline.py | + `postprocess_intent`, `question_context`, `load_shop_cached`, `llm_intent_fn(prompt=, hint_fn=, apply_fixes=)`. |
| llm.py | `load_qwen` dùng chung cho train và suy luận, `chat_ids`, adapter + `base()`, FnBackend cho test. |
| sqlpath.py | Bước 2: SQL trên view chuẩn, sqlglot kiểm tra, duckdb không truy cập ngoài; `answers_agree`; route `sql_only` khi đường metric bỏ trống. |
| answerability.py | Bước 3: chuỗi khả năng shop; train XLM-R (chia theo shop, AUC); gắn `p_answerable`. |
| neural_norm.py | Bước 4 (tuỳ chọn): ViT5 chuẩn hoá có che số + tên hàng; chỉ là gợi ý. |
| calibration.py | + đặc trưng `agree`, bin `p_answerable`; cứu bỏ trống thành unanswerable theo thống kê bin. Đọc được calibration.json v5. |
| score_run.py | + `gold_type`, `--strip-sql`, `--strip-ans`. |
| report.py | Bảng trước/sau trên shop giữ kín. |
| predict.py | `--adapter --sql --answerability --hint-model --resume --no-fixes`. |
| predict.sh / Dockerfile | Đọc `/data`, ghi `/result/submission.jsonl` + `/result/logs/`; tự bật bước theo model có trong `/models`. |

## Đo kiểm (CPU, chỉ có dữ liệu biz_101)
- 21 test qua; parser kịch bản biz_101 40/40; sft_data phủ 40/40.
- Smoke end-to-end với backend giả; train_lora / XLM-R / ViT5 chạy với model tí hon.
- **Chưa có điểm giữ kín thật**: cần GPU → `notebooks/datamate_v6_kaggle.ipynb`, bảng `state/report_*.md`.

## Notebook Kaggle v6 (thứ tự)
1. Scripted + cache shop → 2. SFT data + split → 3. Baseline v5 trên shop val → 4. Train LoRA
→ 5. LoRA + SQL trên val → 6. XLM-R → 7. ViT5 (tuỳ chọn) → 8. calibration.json → 9. đóng gói `datamate_submit/` + `v6_state.zip`.
Chế độ nhanh: `MAX_Q_PER_SHOP_EVAL=40`, `LORA['limit']=800`, `LORA['epochs']=1`.

## Rủi ro
- Tốc độ LoRA phụ thuộc flash-linear-attention trên T4.
- Độ phủ nhãn SFT phụ thuộc hạt giống; thêm log Qwen v5 (`run_outputs`) làm hạt giống.
- Calibration học trên ~20% shop → nên 2-fold LoRA nếu dư GPU.

## Việc tiếp theo (v7)
- 2-fold LoRA; dùng exact-match theo metric để bỏ dần cue rule trong slots.py; few-shot SQL tự sinh; shop nhà thuốc.

## 2026-11-13 — Test 10 câu cuối × 30 shop (không LoRA, BASELINE_SQL) + sửa tầng đọc dữ liệu
- Lần 1 (v6 gốc, 4B): results_v5 = 93/300. Lần 2 (sửa mapper: hạ entity thiếu cột bắt buộc, shop chỉ có đơn,
  sổ không mã đơn, từ vựng trạng thái huỷ, cột ngày serial): 145/300 (`runs/20261113-1846`). Lần 3 = 9B, cùng code lần 2.
- Sau lần 2, sửa thêm (luật chung, tìm bằng scripted intent trên toàn bộ câu train):
  - `values.py`: tiền viết tắt `25k`, `1,39tr`, `1tr440`, `2 triệu`, `1.2 tỷ` (trước đây hậu tố bị coi là đơn vị);
    cột ngày lẫn `d/m` không năm: lấy năm của dòng có ngày đầy đủ liền trước (qua Dec→Jan thì +1).
  - `profile.py`: cột có date_cue mà parse ngày < 90% → thử lại serial + d/m.
  - `rules.py`: dòng `TỔNG NGÀY …` ghi ở cột tên hàng (không mã đơn, không số lượng) là footer, bỏ trước ffill;
    thiếu `order_date` nhưng có `order_time` → lấy ngày của `order_time`.
  - `mapper.py`: cột giảm giá phải trống/0 ở đa số dòng (cột tiền đầy đủ không phải giảm giá).
  - Notebook: thử cài `causal_conv1d` (giới hạn 15 phút, lỗi thì chạy chậm như cũ).
- Số đo: scripted 30 shop × toàn bộ câu 1139 → 1747 (không shop nào giảm); replay log lần 2: 113 → 141
  (14 sai→đúng, 0 đúng→sai). Lạc quan vì luật tìm từ chính các shop train này; cần đo lại trên GPU.
- `sqlvote/scan_v6_money.py`: dòng nghi mất hệ số còn lại chỉ ở nhà thuốc (giá < 1000đ, có thể là thật).

### 2026-11-14 — Lần 4 (code mới, 4B, 30 shop × 10 câu cuối) + sqlvote thử nhỏ
- `results_v5`: **184/300** (234 đúng / 50 sai / 16 bỏ trống); `results_v5_sql` 183. Lần 2 (code cũ) 145 → +39.
  Theo shop: 117 +14, 127 +12, 129 +8, 105 +6, 122 +6, 130 +5; **116 −12** (8 → −4).
- biz_116 tụt do `validate_mapping`: mapper LLM gán 2 bảng phụ (giao hàng, công nợ, có cột "Mã đơn hàng") là `order`;
  kiểm tra nối thấy `sales_line.order_id` khớp 21% → bỏ `order_id`; sau đó chính 2 bảng kia bị loại vì thiếu `order_date`.
  Sửa (luật chung): bảng cha thiếu cột bắt buộc không được dùng để loại khoá của bảng con. Test
  `test_dropped_parent_does_not_veto_child_key`. Chưa đo lại trên GPU (replay dựng ánh xạ bằng heuristic nên không thấy lỗi này).
- sqlvote: 20/20 bỏ trống vì CUDA OOM — `num_return_sequences=3` với prompt rất dài (nguyên rulebook + README) cần 6–9 GB
  một lần; sau lần OOM đầu bộ nhớ không được trả nên mọi câu sau hỏng luôn. Sửa `sqlvote/adapters.py`: sinh từng bản nháp,
  OOM thì dọn bộ nhớ và giữ bản đã có; `sqlvote/run.py`: lỗi một lượt sinh không làm mất các bản nháp khác. Chưa đo lại.
- Lần chạy 9B (kernel v6) được đẩy TRƯỚC hai bản sửa trên.

## 2026-11-14 — Chạy dài an toàn: resume có chữ ký + 2 GPU (lấy ý từ pipeline "chết giữa chừng vẫn sống lại")
Không đổi logic trả lời → điểm không đổi; mục tiêu là tiết kiệm GPU và không trộn kết quả cũ/mới âm thầm.
- `datamate/runstate.py` (mới): ghi atomic, đọc jsonl bỏ dòng ghi dở, `fingerprint` (sha file/thư mục, bỏ `checkpoint*`),
  `code_fingerprint` (code datamate ảnh hưởng dự đoán; trừ train_lora/sft_data/report/score_run/eval_grouped/splits).
- `predict.py --resume`: chữ ký {code, model, adapter, calibration, XLM-R, ViT5, prompt, sql, cờ} ở `submission.meta.json`.
  Lệch (hoặc run cũ không có meta) → log cũ của các shop đó dời sang `logs_stale_<n>/`, chạy lại từ đầu
  (`--force-resume` để bỏ qua). Khớp → chỉ dùng lại câu còn được hỏi VÀ có file log; dòng ghi dở bị bỏ.
  Log ghi atomic TRƯỚC dòng submission.
- `train_lora.py`: checkpoint đầy đủ mỗi `--save-every 50` bước tối ưu và khi hết `--max-hours` vào `<out>/checkpoint/`
  (LoRA, optimizer, scheduler, GradScaler, vị trí, RNG; đổi tên atomic, giữ `.old` khi đang đổi). Chạy lại cùng lệnh →
  tiếp giữa epoch. Chữ ký = sha SFT train/val + siêu tham số + tên base; lệch → train lại. `train_log.json` có
  `complete/step/total_steps`; xong thì xoá checkpoint. **Chưa chạy thử trên GPU** (máy local không có torch).
- Notebook: `PARALLEL_GPUS=True` — máy Kaggle `NvidiaTeslaT4` là **T4 x2** nhưng trước đây chỉ 1 tiến trình predict
  (`device_map='auto'` rải 1 model lên 2 GPU, không nhanh hơn). Giờ `run_val` chia shop val (cân theo số câu) cho 2 tiến
  trình, mỗi tiến trình `CUDA_VISIBLE_DEVICES` riêng, rồi gộp `submission.gpu*.jsonl` → `submission.jsonl` (score_run
  đọc logs chung, không đổi). Kỳ vọng phần predict ~gần một nửa thời gian; cần đo ở lần chạy tới.
- Notebook: `state/manifest.json` + `guard/sign`: SFT gắn {val_frac, val_shops, shops}; LoRA gắn {LORA, sha SFT, model};
  XLM-R gắn {sha split, model}. Khôi phục `v6_state` với cấu hình khác → phần cũ dời sang `/kaggle/working/stale/`
  và làm lại (trước đây đổi VAL_SHOPS vẫn dùng SFT cũ → shop val có thể lọt vào train LoRA → điểm val ảo).
  LoRA dừng vì hết giờ (`complete=false`) → lần sau chạy tiếp từ checkpoint. Đóng gói bỏ `checkpoint*`.
- Test: `tests/test_runstate.py` (dòng ghi dở, chữ ký, predict resume với backend giả).
- Chưa làm (v7): 2-fold LoRA song song 2 GPU (A→B, B→A) + assert mỗi shop có dự đoán out-of-fold đúng 1 lần,
  không shop nào bị chấm bởi adapter đã train trên nó, trước khi fit calibration trên cả 30 shop.

### 2026-11-14 — 9B thật (kernel v6, code lần 4, 30 shop × 10 câu cuối) — runs/20261114-0313
- Đã xác nhận dùng 9B (notebook "bỏ qua … khác kiến trúc", tải 9B). causal_conv1d: biên dịch quá 15 phút → bỏ qua.
- `results_v5` **184** (236/52/12) — bằng 4B (184). `results_v5_sql` 183. predict 163.9 phút; giây LLM 3368 vs 2697 (4B).
- Theo câu: 9B sửa 18 câu 4B sai/bỏ trống, làm sai 17 câu 4B đúng. Trong đó biz_116 +12 là do mapper LLM 9B không mắc
  lỗi bảng cha (đã sửa bằng luật ở 4B) → bỏ biz_116 ra: 4B 188 vs 9B 176. Nhiều câu 9B sai có CÙNG intent với 4B
  (unit_price, revenue ở 114/126/128/130/117) → nghi do ánh xạ bảng của mapper LLM 9B khác; chưa phân tích.
- Kết luận tạm: 9B không đáng đổi (chậm hơn ~25%, không hơn điểm); giữ 4B.

### 2026-11-14 — Phân tích 30 câu sai chung (LLM và scripted đều sai, 300 câu lần 4) + sửa tầng dữ liệu
So ý định: trên 300 câu (bỏ biz_116) LLM 188 = scripted 188, trần "mỗi câu lấy cái đúng" 218 → LoRA khó kéo nhiều;
30 câu cả hai đều sai là lỗi dữ liệu/tính. Sửa (luật chung, rulebook/từ vựng):
- `rules.py` danh mục: sổ bán không có mã hàng → danh mục nối theo TÊN (trước nối theo mã → nhóm hàng không khớp dòng
  nào → tỉ trọng/doanh thu theo nhóm = 0). `WALK_IN` thêm `kl/khle/kvl` (khách lẻ viết tắt; rulebook: khách lẻ không xếp hạng).
- Tết: timex hiểu "Tết năm nay/năm trước" (năm theo as_of); so cùng kỳ năm trước của kỳ Tết = Tết năm âm trước (calendar).
- Kênh bán/thanh toán: cue cố định trong `slots.py` ("qua zalo oa", "qua điện thoại", "tiền mặt/tm", "chuyển khoản/ck"…),
  bộ lọc `channel` mới (chỉ do cue đặt, không vào prompt LLM — `CUE_ONLY_FILTERS`); so khớp giá trị thô qua từ điển đồng nghĩa.
- Nhà thuốc: `mapper.product_attribute_tables` nhận bảng phụ [mã, hoạt chất, kê đơn] (không có tên hàng nên không làm
  `product` được), `rules` gắn `is_prescription/active_ingredient` vào danh mục theo mã; cue "kê đơn / không kê đơn /
  trừ thuốc kê đơn / hoạt chất X" → bộ lọc `prescription` / `active_ingredient` (hoạt chất so khớp đúng, phối hợp là loại riêng).
- `mapper.propose_heuristic`: gán vai bảng tham lam theo điểm CỦA TỪNG CẶP (bảng, vai) thay vì điểm cao nhất của bảng
  (trước: bảng lô nhập giành `stock_snapshot` bằng phương án phụ, báo cáo tồn kho bị đẩy thành `customer`).
- Kết quả: 30 câu → 21 đúng khi chạy lại với ý định LLM của lần 4. Scripted 3000 câu: 1747 → **1989** (+242), không shop
  nào giảm (102 +18, 112 +24, 115 +22, 116 +16, 117 +30, 118 +44, 119 +8, 120 +26, 121 +16, 122 +16, 124 +2, 127 +2, 130 +18).
  LƯU Ý: luật được viết từ lỗi của chính các câu train này → số scripted/300 câu là ước lượng LẠC QUAN.
- Còn lại: biz_124 ánh xạ sai nặng (danh mục hàng → customer), biz_123 không có bảng bán; câu hỏi 2 đáp án (list) theo
  kênh; tồn theo đơn vị lớn biz_122 ("no stock report"); 113 doanh thu hôm qua lệch; 127 thu nợ; 118 "huỷ vì giao trễ".
- Lần 6 (Kaggle, 4B, 30 shop × 10 câu cuối) xếp hàng sau lần 5 để đo trên GPU.

### 2026-11-14 — Lần 5 (runs/20261114-0429): 4B, 6 shop × 10 câu, sửa mapper + sqlvote OOM, đường 2 GPU
- **2 GPU chạy được**: "số GPU chạy predict song song: 2", mã thoát [0, 0], 60 câu 26.8 phút.
- results_v5 41/60 (lần 4 cùng 60 câu: 29). biz_116 −4 → 8 (sửa bảng cha bị loại).
- sqlvote: biz_101 chạy đủ 4 bản nháp nhưng ~3 phút/câu; từ biz_105 vẫn CUDA OOM ngay ở prefill kể cả 1 bản nháp.
  Prompt 20–25k ký tự (~8–10k token: nguyên rulebook + README + schema); Qwen3.5 không có kernel causal_conv1d/fla
  → bản PyTorch tốn bộ nhớ. 20 câu: sqlvote 1 đúng / 3 sai / 16 bỏ trống; ghép không tăng PA (v6 0.80, ghép 0.80/0.60).
  Kết luận: không chạy sqlvote GPU tiếp trên T4 với cấu hình này (muốn thử phải rút gọn prompt: chỉ mục rulebook liên quan).
- Lần 6 (kernel v8): 30 shop × 10 câu cuối, code sửa 30 câu sai chung — đang chạy.

### 2026-11-14 — Lần 6 (runs/20261114-0608): 4B, 30 shop × 10 câu cuối, code sửa 30 câu sai chung
- results_v5 **237/300** (261 đúng / 24 sai / 15 bỏ trống), results_v5_sql 237. Lần 4: 184 → **+53**; không câu nào tụt
  (26 sai→đúng, 1 bỏ trống→đúng). Theo shop: 116 +14, 118 +8, 122 +6, 102/112/120 +4, 108/109/111/115/121/130 +2, 119 +1.
  LẠC QUAN: luật được viết từ lỗi của chính 300 câu này (dù đều là luật chung) → cần đo trên câu/shop chưa dùng để sửa.
- Thời gian: đẩy 04:35 → xong ~06:08 (~1.5 giờ cho 300 câu với 2 GPU; lần 4 một GPU ~3 giờ).
- 24 câu còn sai: thu nợ / khách trả nợ (106, 109, 111, 127) · tác động đổi giá price_effect (103, 112×2, 121×2) ·
  biz_124 ánh xạ sai (đơn giá, nhóm khách, Tết) · câu 2 đáp án theo kênh (120) · tồn theo đơn vị lớn (122) · 123 nhập hàng ·
  lẻ: 101 doanh thu tháng (LLM đặt bộ lọc lạ), 104 topping, 110 "order ddos", 113 hôm qua, 118 huỷ vì giao trễ, 120 ca sáng,
  129 đơn giá/đơn huỷ.

## 2026-11-14 — Đổi cách làm: shop giữ kín cố định + kiểm tra độ bền + dữ liệu tăng cường
- **Shop giữ kín cố định: biz_104, 106, 110, 114, 119, 126** (`kaggle/config.json` val_shops; ghi trong CLAUDE.md).
  Không đọc lỗi của 6 shop này khi viết luật. (Các bản sửa trước ngày này đã nhìn 10 câu cuối của mọi shop → điểm val
  lần đầu còn hơi lạc quan; từ nay sạch.) Phân tích lỗi chỉ trên 24 shop còn lại (danh sách trong scratch/train24).
- Sửa trên 24 shop (scripted 24 shop 1593 → 1661):
  - ingest: bảng sqlite giữ tên bảng thật; mapper tách CamelCase tên cột (`values.split_camel`: MaHoaDon → ma hoa don);
    README kiểu CSDL "`bảng.Cột` là …" thành mô tả cột; từ đồng nghĩa `tri gia` cho line_total; "bán theo đơn" = kê đơn;
    bảng thuộc tính thuốc chọn cột mã theo độ khớp với danh mục (không lấy cột mã đầu tiên). biz_123 (POS sqlite) từ không
    nạp được bảng bán → chạy được (−14 → 48 scripted; câu còn sai chủ yếu do công cụ scripted, không phải tầng dữ liệu).
  - metrics: `purchase_total` có bộ lọc sản phẩm thì tính trên dòng nhập của sản phẩm đó; không có cột thành tiền thì
    SL × giá nhập (trước: bỏ qua bộ lọc / KeyError).
- `tests/perturb_shops.py`: "shop biến đổi" — đổi tên cột/bảng theo 4 họ (bỏ dấu, CamelCase/snake, từ đồng nghĩa độc lập
  với concepts.py, xáo cột + tên bảng chung chung), README sửa theo; đo % câu đúng còn đúng. Từ chối shop giữ kín.
- `datamate/augment.py` + `sft_data --augment K`: biến thể của câu ĐÃ có nhãn kiểm chứng (nhãn giữ nguyên; số/ngày/tên
  hàng được bảo vệ). Họ train: no_accent, abbrev, telex, filler. Họ GIỮ KÍN (không bao giờ vào train): typo, reorder.
  Shop val → `sft/val_noise.jsonl` (mọi họ); `train_lora --noise-val` đo exact-match theo từng họ → biết LoRA có tổng
  quát sang kiểu nhiễu chưa thấy không. Notebook: `LORA['augment']=2`, SFT guard gồm augment.
- `kaggle_cycle.py --lora key=val` (vd epochs=1 limit=3000 max_hours=3.5).
- Kiểm tra độ bền (`tests/perturb_shops.py`, 24 shop, 2080 câu scripted đúng) — trước → sau luật "bảng con":
  accents 96.1% → 100% · case 96.1% → 100% (lỗi công cụ hạ chữ hoa, đã sửa) · synonym 86.7% → 100% · shuffle 100% ·
  tablename 100% (README đổi tên file theo) · noreadme 96.6% (biz_129 −63: tên cột khó đoán, không README → bảng chi tiết
  đơn thành unit_conversion). Việc sau: nhận vai cột theo GIÁ TRỊ (cột có giá trị trùng mã đơn/mã hàng của bảng khác).
- Luật mới `mapper.validate_mapping` (HEADER_OF_LINES): bảng "đầu đơn" mà mã của nó đều nằm trong bảng dòng nhưng chỉ phủ
  một phần → bảng con (công nợ, giao hàng…): bỏ vai đầu đơn, bảng dòng giữ mã đơn (trước: xoá mã đơn của bảng dòng).
  Scripted 24 shop 1661 → 1663, không câu nào tụt. Test `test_subset_table_is_not_the_order_header`.

## Việc còn tồn (tổng hợp 2026-11-14, trước khi có kết quả lần 7)
- Lần 7 (kernel v9): shop giữ kín cố định × 40 câu, baseline + SQL, SFT tăng cường (augment=2), LoRA 1 epoch/3000 mẫu,
  XLM-R + calibration. Cần đọc: điểm baseline vs LoRA trên shop giữ kín (chỉ điểm tổng), `noise_eval` theo họ
  (typo/reorder giữ kín so với họ train), thời gian 2 GPU.
- Tầng dữ liệu: nhận vai cột theo GIÁ TRỊ khi README nghèo (họ noreadme 96.6%, biz_129); biz_124 ánh xạ danh mục → customer.
- Lớp lỗi trên 24 shop: thu nợ / khách trả nợ; price_effect; câu 2 đáp án theo kênh; tồn theo đơn vị lớn.
- Từ vựng: "tiền tươi" = tiền mặt (biz_129, chưa thêm vào `slots.PAYMENT_CUES` / `metrics.PAYMENT_SYN`).
- Công cụ: thêm logic cue của `slots.apply_cues` vào `tests/scripted_intent.py` để điểm scripted sát đường LLM hơn.
- Tuỳ chọn: đọc tham số rulebook từ `rulebook.md` thay vì hằng số trong code.
- Bài học vận hành (TaskStop để lại tiến trình mồ côi, Kaggle chỉ tải version mới nhất, model 9B bị thay bằng 4B,
  heredoc làm hỏng `\b`) đã ghi vào CLAUDE.md mục "Vận hành GPU" và "Môi trường Windows".

## 2026-11-14 — Đánh giá độc lập của Fable (`docs/tong_ket_cho_fable.md` mục 9) + sửa cue
- Fable: 6 shop giữ kín dễ hơn (lần 6: 0,90 vs 0,76 điểm/câu) → lần 7 chỉ dùng so sánh baseline↔LoRA; không đầu tư
  thêm LoRA, bỏ 2-fold; chạy thử nộp bài là việc đầu tiên; giữ ngưỡng 0,5, tăng prior, cân nhắc tắt rescue.
- Sửa (luật chung): `slots.top_k` không lấy số sau tháng/quý…; cue `by` của top_products chỉ ghi đè khi có từ khẳng định
  (thêm "doanh số"); từ so sánh thêm tăng trưởng / gấp … lần / so sánh / biến động; mapper `STATUS_WORDS`/`PAYMENT_WORDS`
  khớp nguyên từ; `canonical_status`: "đã giao/nhận/chốt" = hoàn thành. Test `test_cues_only_overwrite_on_positive_evidence`.
- `slots.apply_cues(skip=...)` + `tests/cue_audit.py`: đo từng nhóm cue giúp/hại trên log Qwen (bỏ shop giữ kín).
- Máy local không có Docker/WSL → chạy thử nộp bài cần cài Docker Desktop hoặc mô phỏng trên Kaggle (kế hoạch mục 9.3).

- **Phiên Fable 14/11 (chiều):** rulebook public khác train, thông báo BTC (Docker, Test Solution đóng 15/11), chạy public test trên Kaggle, việc gấp theo thứ tự → `docs/phien_fable_14-11.md`; kế hoạch đường rulebook → `docs/plan.md`.

## 2026-11-14 — Gói nộp theo hướng dẫn Docker của BTC (`zac2026_DataMate_docker_guideline_final.pdf`)
- Máy chấm: 2 × RTX 5090 (CUDA ≥ 12.8), 6 giờ cho cả private test (~500 câu), `/data` chỉ đọc, không mạng,
  `bash /code/predict.sh` không tham số. Log bắt buộc: id, answer (đáp án cuối), elapsed_ms, thinking, code/output.
- `docker/`: `Dockerfile` (base `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime`, không vLLM), `requirements.txt`
  (transformers==5.20.2 như Kaggle), `README_code.md` (khai báo model), `make_context.py` (dựng `/code` + training_code
  + `data_manifest.json` SHA-256), `build.sh` (build → kiểm tra → chạy thử model giả trên public test → save|gzip → MD5),
  `HUONG_DAN.md`. Dockerfile ở gốc repo là bản cũ (CUDA 12.4).
- `predict.sh` mới → `datamate/launch.py`: một tiến trình mỗi GPU (chia shop theo số câu), gộp `submission.jsonl`
  mỗi 15 giây, câu thiếu ghi abstain. Qwen chạy **fp16** (bỏ 4-bit trong image; `llm.load_qwen` tự lùi về fp16 nếu
  4-bit lỗi). Calibration/điểm cũ đo với 4-bit → cần một lần chạy Kaggle fp16 để xác nhận.
- `predict.log_record`: log có `answer` = dòng nộp cuối, giá trị của pipeline ở `pipeline_answer` (`scoring.to_submission`
  ưu tiên trường này nên score_run / replay / cue_audit vẫn chấm đúng). Test `test_launch_two_processes_logs_follow_the_docker_guide`
  (2 tiến trình, backend giả `tests/fake_backend.py` qua biến `DATAMATE_TEST_BACKEND`, chỉ dùng cho test).
- Chưa kiểm tra được: build thật (máy chưa có Docker), chạy GPU 5090 (chỉ lượt Test Solution của BTC).

## 2026-11-14 — Đường rulebook nấc 1 (`docs/plan.md` B1 + B3): tách rulebook, cổng bỏ trống
- `datamate/rulebook.py`: `parse` (chỉ dựa vào định dạng: `## N.`, `###` ngành, dòng bảng ≥ 2 cột, gạch đầu dòng,
  `**thuật ngữ**` được định nghĩa, `§N`), `snapshot` → `datamate/rulebook_base.json` (79 mục train; `rulebook_cover.py`
  ghi mục nào do metric/module nào thực hiện — 4 mục chưa phủ: giao nhiều đợt, lô gần hết hạn nhất, nhân viên bán giỏi
  nhất, hết hàng cuối ngày), `compare` (same / supplemented / modified / new / uncovered + removed), `Gate`.
  Rulebook public (chỉ đếm): 101 mục = 70 same, 2 supplemented, 25 new, 4 uncovered; 3 mục train bị bỏ.
- `Gate`: cụm kích hoạt = tên luật tách dấu phẩy + thuật ngữ in đậm được định nghĩa, bỏ từ giữ chỗ (kỳ/tháng/ngày…,
  "mặt hàng"); bắt khi tỉ lệ IDF các từ của cụm có trong câu ≥ 0,8 và cụm có ≥ 2 từ hoặc từ chưa có trong rulebook
  train. Bỏ qua §7–9. `pipeline.answer(..., gate=)`: câu bị bắt → abstain (`route='rule_gate'`), không gọi Qwen/SQL/
  calibration. `predict.py` tự đọc `<data-root>/rulebook.md` (`--no-rule-gate` để tắt), chữ ký resume gồm rulebook.
- Đo (CPU, 24 shop, scripted): cổng thật (rulebook train) bắt 21 câu = 15 sai + 6 bỏ trống → +15, không bắt câu đúng
  nào. "Bỏ một luật" (`tests/rulebook_eval.py --loro`): bắt đúng trung bình 0,40 (27 mục), bắt nhầm 0,65% lượt — đạt
  tiêu chí bắt nhầm ≤ 2% nhưng chưa đạt bắt đúng ≥ 0,60 (cần bước hỏi Qwen ở vùng lưng chừng, nấc sau).
- Public (chỉ số tổng): cổng bắt 154/1000 câu (146 thuộc mục mới, 23 mục khác nhau). Không biết bao nhiêu là bắt đúng →
  đo bằng 2 bản nộp public từ CÙNG một lần chạy: bản gốc và `python kaggle/apply_gate.py <sub> public_test/public_test <out>`.

## Lần 7 (14/11, kernel datamate-v6-auto, tải về runs/20261114-run7) — 6 shop giữ kín, 40 câu/shop, chỉ điểm tổng
| Bộ | Đúng | Sai | Trống | Điểm /240 |
|---|---|---|---|---|
| v5 (baseline, 4-bit) | 237 | 3 | 0 | 234 |
| v5_sql | 237 | 3 | 0 | 234 |
| lora / lora_sql / lora_sql_ans | 240 | 0 | 0 | 240 |
- Intent EM: baseline 89,5% → LoRA 92,0% (239 câu). LoRA train dừng vì hết giờ ở bước 346/375 (val EM 0,94),
  không có `noise_eval`. LoRA +6 trên mẫu nhỏ, không câu nào tụt.
- XLM-R "trả lời được" HỎNG: val_auc 0,79 (epoch 1) → 0,09 (epoch 2), recall câu unanswerable = 0 → không đưa vào Docker.
- Tải output: dùng Python310 (Python312 nhầm thư mục `kaggle/` của repo là module kaggle) và chỉ tải v6_state.zip +
  report (CLI tải cả cache ~900 MB → đứt mạng).

## Public có LoRA (15/11 1h, kernel datamate-public-lora, fp16, adapter lần 7 từ dataset thunhngl/datamate-lora-run7)
- Hai lỗi đã sửa trong notebook: dataset Kaggle bị làm phẳng (tìm adapter theo file + datamate_loader.json);
  **torchao 0.10 có sẵn trên Kaggle làm peft dừng khi gắn LoRA lên Qwen fp16** → gỡ torchao (image Docker không cài;
  `docker/build.sh` bước 2 thử gắn LoRA bằng peft). Lần 7 chạy 4-bit nên không gặp.
- "Kernel LỖI" ở ô 10 (calibration) là bình thường khi chỉ chạy public (không có results_*): file nộp đã có.
- Số tổng: LoRA 186 unans / 105 trống / 709 đáp án; gốc Colab 185 / 147 / 668; gốc Kaggle 178 / 120 / 702.
- Chữ ký code của bản LoRA (Kaggle) = `2753309cbb6c54a7`, TRÙNG bản Colab gốc → so sánh LoRA vs Colab gốc là cùng code
  (khác: LoRA + nền GPU). Trùng đáp án LoRA vs Colab gốc 592/1000. Bản Kaggle gốc `runs/20261114-2020` chạy CODE CŨ
  (phiên Fable) → con số 785/1000 Colab-vs-Kaggle-gốc KHÔNG đo được độ lệch giữa hai lần chạy; độ lệch thật chưa đo.
- File: `runs/20261115-0111/nop/` L1_lora_goc, L2_lora_cong, L3_lora_tran_unans, L4_lora_cong_va_tran_unans
  (giống cách tạo 1–4 của `runs/public_colab_fp16/nop/`).
- Docker: build 15/11 0h bị dừng theo ý người dùng (máy lag, code còn đổi). Đã có base image và
  `build/docker_context` (Qwen 4B + LoRA lần 7, không XLM-R, calibration gốc). Tên image `zaic2026_datamate_be_cooked:final`.
- `L8_lora_bo_shop_loi_khong_unans_co_cong.jsonl`: luật bản 8 của Fable (tỉ lệ unans tính TRƯỚC cổng — dựng lại
  bản 8 từ 1_goc khớp 1000/1000) áp lên LoRA: 5 shop bị bỏ, 550 câu có đáp án (bản 8 gốc: 522).
- `10_ban8_chi_khi_goc_va_lora_dong_y.jsonl` (runs/20261115-0111/nop): bản 8, chỉ giữ câu mà bản LoRA (L8) cho đáp án
  y hệt → 311 câu có đáp án. Bản 8 có 522 đáp án (306 đúng/216 sai); 8 và L8 cùng trả lời 480, giống 311, khác 169.
  Lý do: khi hai đáp án khác nhau thì tối đa một bên đúng → độ chính xác trung bình của mỗi bên ở nhóm này ≤ 50%.
  Nếu dùng: cài trong predict.py bằng một model (adapter bật/tắt qua peft `disable_adapter`) → ~2× thời gian suy luận.

## 15/11 05h45 — xem docs/HIEN_TRANG.md
Code 05h45 (sửa trạng thái + cách viết tháng) theo tham chiếu ChatGPT: +0,215 (ước leaderboard ≈ +0,25, lạc quan vì sửa từ lỗi public). LoRA hại public (−0,060 vs +0,048 cùng code) → Docker không LoRA. predict.sh còn lệch cấu hình đã đo (LoRA, --sql + calibration, thiếu 2 luật chặn) — sửa trước khi build.

## 15/11 17h — kiểm tra độ bền CÂU HỎI (`tests/perturb_all.py`), sửa bộ đọc thời gian
- Công cụ mới `tests/perturb_all.py` (stats/run/chatgpt-export/chatgpt-import/gpu-export/gpu-score): ~49 họ biến đổi
  tự sinh giữ nghĩa (tháng, ngày, quý, tương đối, tiền, %, số chữ, hoa/thường, dấu câu, 6 họ augment, chat) + 6 họ
  ChatGPT (`docs/chatgpt_perturb_prompt.md`, 120 câu train × 6 = 720 biến thể, `runs/perturb/chatgpt/`). Chỉ 24 shop
  train không giữ kín. Mỗi câu mất gán tầng: datamate (thật) / timex_miss / intent_scripted (công cụ, cần GPU).
- Lỗi thật đã sửa (luật thời gian chung, `datamate/timex.py` + `datamate/normalize.date_forms`, fixture
  `test_time_forms_found_by_question_perturbation`): "tháng M năm nay/ngoái/trước" (trước: đọc thành từ đầu năm),
  ngày 24-03-2026 / 24.03.2026 / 24/03/26 / "ngày 24 tháng 3 năm 2026", Q1/2026 · Q1 2026 · quý I, telex "quys",
  số đếm bằng chữ ("ba tháng liền nhau", "bảy ngày gần nhất"), khoảng "từ tháng A đến tháng B" (trước: chỉ A và B),
  tháng không ghi năm (năm theo rulebook §2; nhiều tháng; tháng có số thắng "tháng trước"), "tuần/tháng vừa rồi".
- Đo: 24 shop scripted 2087 → **2096** đúng (9 sai→đúng, 0 đúng→sai, không shop tụt); họ biến đổi: rel_month_yword
  29% → 96,9% (còn lại toàn tầng scripted), date_* 59,8–82,5% → 100%, quarter_* 0% → 100%, rel_month_noyear
  95,7% → 99%; ChatGPT: 0 câu mất ở tầng datamate. Replay public log A: khớp 146 → 147 (không viết từ lỗi public).
  pytest 44 qua.
- Chưa kết luận (tầng scripted, cần Qwen): tiền "1tr2"/"41k", số chữ, typo, viết tắt, chen tiếng Anh, giọng nhắn tin.
  Bộ GPU sẵn: `runs/perturb/gpu/public` (624 câu = 249 gốc + 375 biến thể, ~3,1 giờ Kaggle 2×T4), chấm bằng
  `python tests/perturb_all.py gpu-score --train-root data/train --manifest runs/perturb/gpu/manifest.json --submission <...>`.
  Điểm GPU trên shop train lạc quan (LoRA đã thấy các shop này), chỉ đọc phần "mất khi viết lại".
- Ứng viên nhỏ chưa sửa: "nay shop bán bn" ("nay" đứng đầu = hôm nay) — 2 câu ChatGPT, tầng timex_miss (Qwen vẫn có thể đúng).
- **GPU (15/11 18h30, kernel `datamate-perturb`, dataset riêng tư `thunhngl/datamate-perturb-q`, Qwen 4B fp16 không LoRA,
  624 câu, 58,5 phút trên T4×2; kết quả `runs/20261115-2315`, chấm `runs/perturb/gpu/score/report.md`):**
  câu gốc 236 đúng/9 sai/4 bỏ trống; giữ đúng khi viết lại: rel_month_yword 100%, money_tr 100%, money_k 90%,
  aug_abbrev 100%, aug_typo 100%, gpt_colloquial 98,2%, gpt_english_mix 98,2%, chat_mix 78,3% (gõ sai chồng, không
  thành lớp), **numword 78,9%** ("năm khách mua nhiều nhất" → 1 khách, "ít nhất năm đơn", "bảy ngày kể từ" → bỏ trống; 4 shop).
- Sửa lớp numword: `normalize.count_words` — số 2–10 viết bằng chữ, đúng dấu hoặc không dấu, đứng trước danh từ đếm
  (khách, đơn, ngày, tháng, mặt hàng…) → chữ số; giữ "bà", "năm tháng/tuần", "một", "sau". 24 shop scripted 2096 → 2096
  (không đổi), numword scripted 25% → 71,5% (phần còn lại tầng scripted). Chưa đo lại trên Qwen. pytest 44 qua.
