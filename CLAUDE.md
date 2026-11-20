# DataMate (Zalo AI Challenge) — hướng dẫn cho Claude

Trả lời người dùng bằng tiếng Việt. Người dùng: sinh viên năm 1 KHDL (UIT).

## Bài toán
Agent offline (Docker, không mạng) trả lời câu hỏi tiếng Việt về dữ liệu bán hàng của 30 shop
(csv/xlsx + README mỗi shop, chung `rulebook.md`, `calendar.csv`). Chấm: đúng +1, sai −1, bỏ trống 0.
Mô hình mở, tổng tham số < 15B. Bản hiện tại **v6**: Qwen3.5-4B (4-bit) + LoRA ý định, đường SQL đối chiếu,
XLM-R "trả lời được", calibration ngưỡng bỏ trống. Kiến trúc: `README.md`; tài liệu thiết kế:
`docs/datamate_v6_handoff.md` (bản cũ: `docs/datamate_v5_handoff.md`).

## Luật bắt buộc khi sửa code
- KHÔNG gắn logic với ID câu hỏi hay business_id; không if/else cho một shop cụ thể.
- Luật mới phải là luật của rulebook hoặc từ vựng chung, áp được cho shop chưa gặp.
- Sau mỗi thay đổi: `python -m pytest -q tests` (chặn tụt điểm; cần `DATAMATE_TRAIN` trỏ tới data train,
  vd PowerShell: `$env:DATAMATE_TRAIN = "E:\ZaloAI\datamate-ws\data\train"`).
- Phát lại output Qwen cũ qua code mới chỉ là ước lượng LẠC QUAN nếu luật được viết từ chính các lỗi đó.
  Điểm khách quan của v6 = các **shop giữ kín** (`VAL`, chia trong `state/sft/split.json`): LoRA, XLM-R và
  ngưỡng đều không thấy shop đó. Đừng viết luật từ lỗi của shop val rồi báo điểm val như điểm khách quan.
- **Shop giữ kín cố định (từ 2026-11-14): biz_104, biz_106, biz_110, biz_114, biz_119, biz_126** (`kaggle/config.json`
  `val_shops`). KHÔNG đọc log/lỗi/câu hỏi của 6 shop này khi viết luật; phân tích lỗi chỉ trên 24 shop còn lại.
  Với shop giữ kín chỉ báo điểm tổng (không mở từng câu sai). Giao việc cho subagent cũng phải dặn điều này.

## Cách sửa để tổng quát hoá (người dùng rất quan tâm: public/private test là shop/câu chưa gặp)
- Không sửa theo từng câu sai. Gom lỗi thành **lớp** (vd "bảng con bị coi là đầu đơn", "khách lẻ viết tắt"), sửa lớp đó,
  rồi đo trên **toàn bộ câu của 24 shop** bằng scripted (`tests/run_shops.py`): báo điểm trước/sau và **không shop nào tụt**.
- Mỗi luật mới có một test fixture nhỏ trong `tests/test_v6.py` (đã từng viết ngược điều kiện `back < 0.8` mà không biết).
- Sửa mapper/rules/ingest xong → chạy thêm kiểm tra độ bền `python tests/perturb_shops.py --train-root data/train <24 shop>`
  (đổi tên cột/bảng: accents, case, synonym, shuffle, tablename, noreadme). Mức hiện tại: 5 họ đầu 100%, noreadme 96.6%;
  thay đổi làm tụt họ nào thì xem lại. Nếu một họ tụt mạnh bất thường, kiểm tra công cụ biến đổi có thực tế không trước
  (đã có 2 lần "tụt giả" do công cụ hạ chữ hoa CamelCase và không đổi tên file trong README).
- Giới hạn của scripted: `tests/scripted_intent.py` KHÔNG có logic cue của `slots.apply_cues` (kênh, thanh toán, nhà thuốc…)
  → điểm scripted thấp hơn thực tế ở các câu đó; "bỏ trống→sai" trong scripted có thể là do công cụ, không phải tầng dữ liệu.
- `kaggle/replay.py` dựng lại ánh xạ bằng **heuristic**, nên không thấy lỗi của mapper LLM (vd biz_116 lần 4) → lỗi ánh xạ
  chỉ thấy được trên GPU hoặc khi so `shop_report.json` của run.
- Dữ liệu tăng cường cho LoRA (`datamate/augment.py`, `sft_data --augment K`): chỉ tạo biến thể của câu ĐÃ có nhãn kiểm
  chứng bằng đáp án; họ train (no_accent, abbrev, telex, filler) tách khỏi họ giữ kín (typo, reorder) để đo LoRA có tổng
  quát sang kiểu nhiễu chưa thấy (`train_log.json` → `noise_eval`). Không thêm họ giữ kín vào train.

## Vòng lặp làm việc
1. Đọc `runs/LATEST` → `<run>/errors.md` (tạo bởi `kaggle/analyze_run.py`; có điểm mọi bộ `results_*`,
   lỗi của bộ đầy đủ nhất theo metric và theo `agree` metric/SQL, kèm bảng `state/report_*.md` của notebook).
2. Phân nhóm lỗi theo tầng: đọc dữ liệu/ánh xạ (mapper, rules) · hiểu câu hỏi (intent, timex, slots, LoRA/SFT)
   · tính (metrics) · SQL (sqlpath) · ngưỡng (calibration, answerability).
   Có thể giao việc phân nhóm cho subagent `error-analyst`.
3. Sửa code, chạy test, phát lại log cũ: `python kaggle/replay.py [runs/<stamp>] --train $DATAMATE_TRAIN [--run lora_sql|v5|v5_sql] [--no-sql]`
   (thiếu `--train` → StopIteration)
   (in điểm cũ → mới, chỉ-metric, và các câu đổi kết quả; ánh xạ bảng dựng lại bằng heuristic).
4. Hỏi người dùng trước khi chạy Kaggle (tốn quota GPU ~30 giờ/tuần; notebook v6 đủ bước mất ~5–6 giờ T4).
   Khi được đồng ý, giao subagent `kaggle-runner`: `python kaggle/kaggle_cycle.py -m "<mô tả thay đổi>"`
   (đẩy code → chạy `notebooks/datamate_v6_kaggle.ipynb` trên GPU → chờ → tải `v6_state.zip` + `state/report_*.md`
   → tóm tắt). Rút ngắn: `--quick` (chế độ nhanh của handoff: 40 câu/shop val, LoRA limit 800, 1 epoch), `--max 40` (câu mỗi shop val), `--step lora_train=0 xlmr=0` (tắt bước trong `RUN`),
   `--biz ...`, `--val-shops ...`, `--pick last` (câu cuối mỗi shop), `--sql-baseline` (baseline kèm SQL),
   `--hf-model Qwen/Qwen3.5-9B`, `--lora epochs=1 limit=3000 max_hours=3.5 augment=2`, `--sqlvote k=4 ...`.
   **Người dùng ít thời gian: gộp nhiều bước vào MỘT lần chạy** (baseline + SFT + LoRA + XLM-R…) thay vì chạy lẻ từng bước.
   Cấu hình mặc định ở `kaggle/config.json` (khoá → biến notebook:
   business_ids→BUSINESS_IDS, val_frac→VAL_FRAC, val_shops→VAL_SHOPS, max_q_per_shop_eval→MAX_Q_PER_SHOP_EVAL,
   quantize_4bit, use_llm_mapper, run→RUN, lora→LORA). `--only list` xem file output không tải.
   **Chọn nơi chạy GPU:** smoke test và thử nhỏ (vài shop, ≤ ~40 câu/shop, không train LoRA) chạy **Colab**
   trước: `python colab/colab_cycle.py --smoke -m "..."` (biz_101, 5 câu, chỉ baseline) hoặc cùng các cờ
   `--biz/--max/--val-shops/--step/--quick` như kaggle_cycle. Script dùng `colab run --gpu T4`, tải Qwen từ
   Hugging Face mỗi lần (không lưu Drive), lấy kết quả về `runs/<giờ>/` cùng định dạng Kaggle (analyze_run/replay
   dùng được); không xin được GPU trong 5 phút thì tự chuyển sang `kaggle_cycle.py`. **Train LoRA và chạy lớn**
   (đủ shop val, nhiều giờ) chạy **Kaggle**. Cả hai đều phải hỏi người dùng trước khi chạy.
5. Báo người dùng: điểm trước/sau (trên shop val), lỗi còn lại, việc tiếp theo. Cập nhật `docs/datamate_v6_handoff.md`.

## Vận hành GPU — lỗi đã gặp, đừng lặp lại
- Tài khoản Kaggle của người dùng: `thunhngl` (code `thunhngl/datamate-code`, kernel `thunhngl/datamate-v6-auto`,
  data `thunhngl/training-data`). Dataset `thinh0110/...` là của bạn người dùng → 403, không dùng.
- Kaggle CLI 1.7.x không nhận `--accelerator` → script tự đẩy lại không cờ; GPU mặc định là **T4 ×2**, notebook
  `PARALLEL_GPUS=True` chia shop cho 2 tiến trình predict. Model tải về `/tmp/dm_models` (thư mục working giới hạn 20 GB).
- **Kaggle chỉ cho tải output của version MỚI NHẤT.** Đẩy lần chạy sau trước khi tải xong lần trước = mất kết quả lần trước.
  Xếp hàng nhiều lần chạy: script nền chờ dòng "DONE/FETCHED" của lần trước rồi mới đẩy. Cần version cũ thì dùng
  kagglesdk `ApiDownloadKernelOutputRequest(owner_slug, kernel_slug, version_number, file_path)` (Python310 có module `kaggle`).
- **Đẩy lại cùng một kernel khi lần trước đang chạy KHÔNG huỷ lần trước** (15/11: v2 và v3 của `datamate-public-auto`
  cùng chạy ~5 giờ, chiếm hết 2 phiên GPU → lần đẩy thứ ba và kernel khác bị từ chối "Maximum batch GPU session count of
  2 reached"). CLI/kagglesdk không có lệnh huỷ; phải huỷ trên web. Kiểm tra notebook kỹ TRƯỚC khi đẩy; lần chạy chỉ có
  bộ test (`baseline=0`) từng lỗi ở ô calibration.
- **TaskStop chỉ giết vỏ bash, không giết tiến trình python con** → `kaggle_cycle.py` mồ côi vẫn đẩy kernel (đã làm lần 4
  bị đẩy sớm). Sau khi dừng phải kiểm tra và giết: PowerShell
  `Get-CimInstance Win32_Process -Filter "name='python.exe'" | ? CommandLine -match kaggle_cycle` → `taskkill /PID <pid> /F`.
- Đổi model (`--hf-model`) phải xác nhận trong log kernel là model mới thật sự được nạp (dòng "bỏ qua … khác kiến trúc",
  kích thước hidden 4B=2560 / 9B=4096). Lần đầu chạy 9B notebook vẫn lấy model 4B từ `kernel_sources` → mất ~2.7 giờ GPU.
- Colab: phiên rớt khoảng ~1 giờ, hết quota GPU nhanh, upload bundle lớn lỗi SSL (đã chia khối 8 MB). Chỉ dùng cho smoke
  test/vài shop; chạy 30 shop hoặc LoRA dùng Kaggle.
- Số đo để ước lượng (4B, T4): 300 câu không LoRA ≈ 1,5 giờ với 2 GPU (≈ 3 giờ 1 GPU); 9B chậm hơn ~25% và KHÔNG hơn
  điểm (184 = 184) → giữ 4B. `causal_conv1d` biên dịch > 15 phút → notebook tự bỏ qua. sqlvote trên T4: OOM ở prefill
  (prompt ~8–10k token) hoặc ~3 phút/câu → không dùng nữa trừ khi rút gọn prompt.
- Khi người dùng vắng (vd đi ngủ) và đã cho phép "tự sửa rồi chạy lại": quyền đó chỉ áp cho lần đó; lần sau vẫn hỏi.

## Môi trường Windows (máy local)
- Luôn đặt `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` khi chạy python trong Bash (không thì lỗi cp1252 khi in tiếng Việt).
- Không viết code Python có regex `\b`, `\d`… qua heredoc/`python - <<EOF` rồi sửa file bằng chuỗi: đã từng ghi ký tự
  backspace (`\x08`) vào regex. Sửa file bằng công cụ Edit; script dài thì ghi ra file trong scratchpad rồi chạy.
- Không có torch/GPU local: train_lora, XLM-R, Qwen chỉ thử được trên Kaggle/Colab; local chỉ test, scripted, replay,
  perturb.

## Dùng model nào (tiết kiệm lượt dùng)
- Phiên chính: Opus hoặc Sonnet — sửa code, chạy test, replay.
- Việc khó cần suy nghĩ sâu → giao subagent `planner` (model Fable, tốn gấp đôi lượt): thiết kế bước lớn,
  phân tích nhiều câu sai, shop kiểu mới, rà soát trước khi nộp. Planner chỉ viết docs/plan.md;
  phiên chính đọc plan rồi làm. Không dùng planner cho việc nhỏ.
- Chạy/chờ Kaggle → `kaggle-runner` (Haiku). Phân nhóm lỗi thường → `error-analyst` (Sonnet).
- Nếu subagent báo không nhận model "fable", sửa dòng `model:` trong .claude/agents/planner.md thành `opus`.

## Cấu trúc
- `datamate/` code chính · `tests/` (scripted_intent.py CHỈ dùng để test/tạo nhãn SFT, không nằm trong bài nộp)
- `notebooks/datamate_v6_kaggle.ipynb` notebook Kaggle, **sinh từ** `notebooks/build_notebook.py` — sửa file .py rồi
  chạy `python notebooks/build_notebook.py`, không sửa tay .ipynb. Đổi tên biến ô cấu hình thì sửa
  `SCALAR_VARS/DICT_VARS` trong `kaggle/kaggle_cycle.py` (script dừng báo lỗi nếu biến không còn).
- `docker/` gói nộp theo hướng dẫn BTC (`zac2026_DataMate_docker_guideline_final.pdf`, đọc `docker/HUONG_DAN.md`):
  máy chấm 2×RTX 5090, 6 giờ, `/data` chỉ đọc, không mạng, log bắt buộc id/answer/elapsed_ms/thinking/code/output.
  Đổi `predict.py`/`launch.py`/`predict.sh` thì chạy lại `test_launch_two_processes_logs_follow_the_docker_guide`.
  Hạn: Test Solution 23:59 15/11, nộp chính thức 23:59 16/11.
- Đường rulebook (`docs/plan.md`): `datamate/rulebook.py` đọc `<data>/rulebook.md` lúc chạy, so với
  `rulebook_base.json` (ảnh chụp train, `rulebook_cover.py` ghi mục nào có code); `Gate` cho câu dùng luật mới/chưa phủ
  bỏ trống. Sửa rulebook_cover → `python -m datamate.rulebook snapshot data/train/rulebook.md`. Đo: `tests/rulebook_eval.py
  --results <run_shops dir> [--loro]`, `tests/run_shops.py --rule-gate`.

## Public test (từ 15/11: ĐƯỢC đọc nội dung, dùng có giới hạn)
- Được đọc câu hỏi/dữ liệu/log public và phân tích lỗi bằng tham chiếu ChatGPT (`runs/tham_chieu_gpt/`, chấm bằng
  `kaggle/score_public_ref.py --policy`). Tham chiếu đúng ~95%, KHÔNG phải đáp án: "khớp tham chiếu" ≠ đúng.
- **4 shop public giữ kín: dev_001, dev_007, dev_009, dev_010** — không đọc câu sai/log của 4 shop này khi tìm lỗi; chỉ
  báo điểm tổng. Sửa mà chỉ tăng ở shop đã đọc, không tăng ở 4 shop này → nghi học thuộc.
- Chỉ sửa theo CỤM lệch (≥ vài câu, ở ≥ 2 shop), thành luật chung (từ vựng tiếng Việt, rulebook, khuôn đầu ra model);
  không sửa để khớp từng câu, không gắn với tên shop/mã câu. Mỗi sửa vẫn phải: test fixture + 24 shop train không tụt.
- KHÔNG: train LoRA/XLM-R trên public, học ngưỡng/calibration trên public, đưa public hay tham chiếu vào Docker, nộp
  tham chiếu dưới nhãn SLM. Ngưỡng (vd luật chặn 20%) đặt từ train.
- Điểm public sau khi sửa từ lỗi public là ước lượng LẠC QUAN cho private — ghi rõ khi báo điểm.
- `kaggle/` script tự động · `runs/<stamp>/` kết quả tải về: `state/run_<tên>/logs/<biz>/<id>.json` (log từng câu:
  llm_raw, sql_raw, agree, p_answerable...), `state/results_<tên>/` (v5, lora, lora_sql, lora_sql_ans, ...),
  `state/report_*.md`, `<kernel>.log`
- Dữ liệu train local: `data/train/` (data/, questions.jsonl, answers.jsonl, calendar.csv, rulebook.md)
- `sqlvote/` đường tham khảo độc lập (xem mục dưới) · `docs/sqlvote_goi_y.md` tài liệu của nó

## Đường tham khảo `sqlvote/` (viết ở một phiên nghiên cứu khác)
**Trạng thái 2026-11-14:** đã thử trên T4 (lần 4, lần 5) — OOM ở prefill vì prompt chứa nguyên rulebook + README, câu chạy
được mất ~3 phút; 20 câu: 1 đúng / 3 sai / 16 bỏ trống, ghép với v6 không tăng điểm. Tạm dừng; chỉ thử lại nếu prompt
chỉ giữ mục rulebook liên quan. Phần sửa tiền viết tắt (`25k`, `1,39tr`) đã đưa vào `datamate/values.py`.
`sqlvote/` = làm sạch bảng thô vào DuckDB → prompt chứa NGUYÊN rulebook của split + README + schema → K bản nháp
SQL → bỏ phiếu theo cách chấm → trả lời / unanswerable / bỏ trống. Không import `datamate/` (trừ `sqlvote/adapters.py`).
Đọc `docs/sqlvote_goi_y.md` trước khi đụng tới nó. Luật làm việc:
- Mục tiêu là ĐỐI CHIẾU rồi mới quyết định đưa gì vào `datamate/`. Không chép nguyên `sqlvote/` vào `datamate/`,
  không thay đường metric bằng nó khi chưa có số đo trên shop val.
- Việc đầu tiên, không cần GPU: mục 0 và mục 7 của `docs/sqlvote_goi_y.md` — `datamate/values.py` đọc `25k`, `1,45tr`
  thành 25, 1,45 (đã đo: doanh thu sai ở biz_105, biz_129; nghi ngờ thêm biz_117, biz_127). Đo bằng
  `python sqlvote/scan_v6_money.py . data/train`, sửa, chạy lại lệnh đó + `python -m pytest -q tests` + `kaggle/replay.py`.
- So sánh luôn trên CÙNG tập câu: chạy sqlvote với `--questions state/questions_val.jsonl` của lần chạy v6, rồi
  `python -m sqlvote.compare --answers data/train/answers.jsonl --questions data/train/questions.jsonl
  --run v6=runs/<stamp>/state/run_<tên> --run sqlvote=runs/<stamp>/state/sqlvote --out runs/<stamp>/compare.md`.
  Báo cáo cho điểm từng bên, theo loại/shop, bảng chéo, PA của 3 cách ghép cố định và danh sách câu khác nhau.
- Một thay đổi lấy ý từ sqlvote chỉ được giữ khi PA trên shop val tăng (hoặc không giảm mà bớt câu sai); ghi số trước/
  sau vào `docs/datamate_v6_handoff.md`. Luật "không gắn logic với ID câu hỏi / business_id" áp dụng cho cả `sqlvote/`.
- Test của sqlvote: `python -m pytest -q sqlvote/tests` (cùng biến `DATAMATE_TRAIN`), smoke không cần GPU:
  `python -m sqlvote.smoke_test data/train .cache/sqlvote`. `kaggle_cycle.py` và `colab_cycle.py` đã đóng gói
  thêm `sqlvote/`; notebook có ô 5b `RUN['sqlvote']` (mặc định tắt; bật: `--step sqlvote=1`, tham số
  `SQLVOTE = dict(k, max_tokens, time_budget)`, ghi `state/sqlvote/`, chạy sau baseline trên cùng `questions_val.jsonl`).
