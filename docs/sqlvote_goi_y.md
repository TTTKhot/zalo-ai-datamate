# Gợi ý cho DataMate v6: đường SQL-vote độc lập (`sqlvote/`)

Tài liệu này dành cho phiên làm việc ở `E:\ZaloAI\datamate-ws`. Code nằm ở `sqlvote/` (cạnh `datamate/`), viết ở một
phiên nghiên cứu khác. `sqlvote/` không import gì từ `datamate/`, trừ `sqlvote/adapters.py` (chỉ khi được gọi).
Phụ thuộc: pandas, duckdb, openpyxl (sqlglot, python-calamine là tuỳ chọn; đều đã có trong `requirements.txt` của v6).
Không có gì gắn với id câu hỏi hay id shop.

`kaggle/kaggle_cycle.py` và `colab/colab_cycle.py` đã được sửa để đóng gói thêm thư mục `sqlvote` (trước đây chỉ
`datamate` và `tests`). Notebook (`notebooks/build_notebook.py`) CHƯA có bước nào gọi `sqlvote`.

## Quy trình đối chiếu v6 với gợi ý này
Mục tiêu: chỉ đưa vào `datamate/` những gì làm PA tăng trên shop val, đo trên đúng cùng một tập câu.
1. Không cần GPU — kiểm tra sqlvote chạy được ở đây:
   `python -m pytest -q sqlvote/tests` (cần `DATAMATE_TRAIN`), `python -m sqlvote.smoke_test data/train .cache/sqlvote`.
2. Không cần GPU — đo lỗi đọc tiền của v6 (mục 0, mục 7): `python sqlvote/scan_v6_money.py . data/train`.
   Sửa `datamate/values.py`, chạy lại lệnh này và `python -m pytest -q tests`, rồi `kaggle/replay.py` trên log cũ.
3. Có GPU — chạy sqlvote trên ĐÚNG tập câu mà v6 vừa được chấm (`state/questions_val.jsonl` của notebook), ghi vào
   `state/sqlvote/` (đoạn code notebook ở mục 3).
4. Đối chiếu, không cần GPU, sau khi tải `state/` về:
   ```
   python -m sqlvote.compare --answers data/train/answers.jsonl --questions data/train/questions.jsonl \
       --run v6=runs/<stamp>/state/run_<tên> --run sqlvote=runs/<stamp>/state/sqlvote --out runs/<stamp>/compare.md
   ```
   `--run` nhận file `submission.jsonl`, thư mục chứa nó (`state/run_<tên>/`), hoặc thư mục `state/results_<tên>/`.
   Báo cáo gồm PA trên các câu chung, theo loại đáp án, theo shop, bảng chéo đúng/sai/bỏ trống, PA ước lượng của
   3 cách ghép cố định (A rồi B, B rồi A, chỉ trả lời khi trùng), và danh sách câu khác nhau để phân tích lỗi.
5. Phân lỗi theo `compare.md` (mỗi câu có log chi tiết: v6 ở `state/run_<tên>/logs/`, sqlvote ở
   `state/sqlvote/logs/<biz>/<id>.json` với SQL từng bản nháp, lỗi, phiếu bầu). Sửa ở `datamate/` theo luật của
   CLAUDE.md; chỉ chọn cách ghép trên shop val.

## 0. Việc cần làm trước tiên: lỗi đọc tiền trong view chuẩn của v6
`datamate/values.py::parse_number_value` coi `tr` / `k` sau con số là "đơn vị đi kèm" và trả về phần số trần:
`"1,45tr"` → `1.45` thay vì `1450000`.

Đã kiểm chứng trên biz_129 (mapper heuristic, không LLM): 872 dòng `sales_lines.line_total` không còn là số nguyên,
tổng `line_total` là 18.567.109.384 trong khi tổng cột gốc "Tiền bán" là 20.463.325.500 (thiếu ~9%).
Câu "doanh thu tháng 3/2026" có gold 1.016.912.500; `SUM(revenue)` trên `v_orders` của v6 ra 908.855.175,49.
Trên biz_105, `"25k"` → `25`: 30.337 / 138.023 dòng `sales_lines` có `unit_price` và `line_total` dưới 1000
(vd Cà phê đen (M): 25,0 thay vì 25.000).

Hệ quả: đường metric và đường SQL của v6 cùng đọc view này nên cùng sai giống nhau, và `agree` báo "trùng nhau".
Sửa trong `values.py` (nhân hệ số k = 1e3, tr/triệu = 1e6, tỷ = 1e9; có hệ số thì dấu `,`/`.` là dấu thập phân;
`1tr2` = 1.200.000; nhân xong `round(x, 6)` vì `2.825 * 1e6` ra `2825000.0000000005`), rồi chạy lại test của v6.
Cách làm tham khảo: `sqlvote/clean.py::parse_number`. Kết quả quét cả 30 shop train: xem mục 7.

## 1. Trạng thái thật của code này
- Đã chạy: nạp + làm sạch cả 30 shop train (1–15 giây/shop). 26 test qua (`python -m pytest -q sqlvote/tests`).
- Đã chạy: `sqlvote.smoke_test` — 8 câu train (biz_105: sổ Excel mỗi tháng một sheet; biz_129: nhiều file CSV) bằng SQL
  viết tay ra đúng gold qua toàn bộ đường prompt → SQL → vote → scorer; cổng "kỳ ngoài dữ liệu" hoạt động.
- Đã chạy: `adapters.canonical_tables` với package `datamate` thật trên biz_129 (view v6 nạp được vào cùng DuckDB).
- CHƯA chạy: bất kỳ model nào (máy viết code này không có GPU) → chưa có điểm. `adapters.HFSamplingBackend` chưa
  được chạy thử lần nào. Chưa đụng tới public test.

## 2. Khác v6 ở đâu
| | v6 hiện tại | sqlvote |
|---|---|---|
| Rulebook | tóm tắt cứng bằng tiếng Anh trong `sqlpath.RULES` | đọc nguyên `rulebook.md` của split lúc chạy |
| Bảng cho SQL | 7 view chuẩn | mọi bảng thô đã làm sạch định dạng (lô, giao hàng, hạn nợ, chi phí...) + view chuẩn nếu muốn |
| Số bản nháp | 1 SQL greedy | K bản nháp (1 greedy + K−1 lấy mẫu, 2 biến thể prompt), bỏ phiếu theo khoá của scorer |
| Độ tin cậy | `agree` metric/SQL + XLM-R | tỉ lệ phiếu của nhóm thắng trên TẤT CẢ bản nháp (nháp lỗi làm giảm độ tin) |
| Few-shot | không | ngân hàng câu train có SQL đã ra đúng gold (rejection sampling) |
| Ngày tháng | timex → periods | mốc lịch tính sẵn bằng code đưa vào prompt (`dates.py`) |

Lý do đáng thử: rulebook public dài hơn train (177 so với 143 dòng), có ngành mới (mẹ và bé, sửa xe, điện thoại) và
khái niệm mới (khách sộp nhất, giờ cao điểm). Từ vựng ý định cố định + `RULES` cứng không theo kịp; 7 view chuẩn
không chứa sổ sửa xe, lô, đợt giao.

## 3. Chạy thử
Không cần model:
```bash
python -m sqlvote.run ingest --split data/train --show biz_105
```
```bash
python -m sqlvote.smoke_test data/train state/sqlvote_cache
```
Có server OpenAI-compatible chạy offline (vLLM / llama.cpp server):
```bash
python -m sqlvote.run predict --split data/train --out state/sqlvote_val --answers data/train/answers.jsonl --shops <shop val> --limit-per-shop 40 --k 8 --no-thinking --save-bank state/bank.jsonl
```
```bash
python -m sqlvote.run calib --logs state/sqlvote_val/logs
```
`calib` in PA theo từng ngưỡng, tỉ lệ greedy đúng và tỉ lệ "có ít nhất một bản nháp đúng" (trần của bỏ phiếu).

Trong notebook Kaggle/Colab: notebook gọi `datamate.predict` bằng tiến trình con qua hàm `sh(...)`, nên bước sqlvote
cũng nên là một tiến trình con (nạp Qwen bằng chính `datamate.llm.QwenBackend`, chạy SAU khi bước v6 đã xong để
không chiếm VRAM cùng lúc). Thêm vào `notebooks/build_notebook.py` một ô kiểu:
```python
if RUN.get('sqlvote'):
    qf = STATE / 'questions_val.jsonl'                    # đúng tập câu v6 vừa được chấm
    sh('-u', '-m', 'sqlvote.run', 'predict', '--split', str(TRAIN_ROOT), '--questions', str(qf),
       '--answers', str(ANSWERS), '--out', str(STATE / 'sqlvote'), '--cache', '/tmp/sqlvote_cache',
       '--hf-model', str(MODEL_DIR), '--quantize-4bit', '--k', '4', '--max-tokens', '500',
       '--time-budget', '7200', '--save-bank', str(STATE / 'sqlvote_bank.jsonl'), stream=True)
    sh('-m', 'sqlvote.run', 'calib', '--logs', str(STATE / 'sqlvote' / 'logs'), stream=True)
```
rồi thêm khoá `sqlvote` vào `RUN` (và vào `SCALAR_VARS/DICT_VARS` của `kaggle/kaggle_cycle.py` nếu cần), chạy
`python notebooks/build_notebook.py`. `state/sqlvote/` được nén cùng `state/` nên tải về như các kết quả khác.

Dùng trong Python (nếu đã có sẵn một `QwenBackend` tên `qwen`):
```python
from sqlvote.adapters import HFSamplingBackend
from sqlvote.run import Config, predict
result = predict(TRAIN_ROOT, STATE / 'sqlvote', HFSamplingBackend(qwen), Config(k=4, workers=1, max_tokens=500),
                 answers=ANSWERS, questions_path=STATE / 'questions_val.jsonl', cache_dir='/tmp/sqlvote_cache')
```
Lưu ý: `extra_tables_fn` chỉ nên bật SAU khi sửa lỗi ở mục 0, nếu không model sẽ được chỉ vào view sai.

## 4. Thứ tự việc nên làm (hạn đóng băng 23:59 16/11)
1. Sửa lỗi mục 0, chạy lại `pytest tests` và `kaggle/replay.py` của v6 để xem điểm cũ → mới.
2. Đo sqlvote trên shop val (`state/sft/split.json`), 40 câu/shop, so với `lora_sql` của v6 trên cùng câu.
   Giữ sqlvote chỉ khi PA trên shop val cao hơn, hoặc khi nó trả lời đúng những câu v6 bỏ trống.
3. Ghép thay vì thay thế: đưa kết quả sqlvote vào `calibration.py` như đường thứ ba (đặc trưng `vote_conf`,
   `agree3` = sqlvote trùng đường metric / trùng SQL cũ). Ba đường trùng thì trả lời; đường metric bỏ trống mà
   `vote_conf ≥ 0.75` thì lấy sqlvote. Ngưỡng lấy từ bảng `calib`, không đoán.
4. Dựng ngân hàng few-shot bằng `--save-bank` trên shop TRAIN (không phải val), chạy lại với `--bank`.
   File này cũng là dữ liệu SFT nếu sau này muốn LoRA cho đường SQL.
5. Docker: `predict.sh` gọi thêm `python -m sqlvote.run predict --split /data --out /result/sqlvote ...` hoặc gọi
   `predict()` trong `datamate/predict.py`; log từng câu đã có sẵn ở `logs/<biz>/<id>.json` (id, đáp án, thời gian,
   SQL từng bản nháp, kết quả bỏ phiếu) — đúng yêu cầu log của BTC.

## 5. Tham số, tốc độ, luật thi
- Qwen3.5-4B 4-bit còn dư nhiều quota 15B. Máy chấm có 2×RTX 5090: đáng thử Qwen3.5-9B bf16 cho đường SQL
  (4B + 9B vẫn dưới 15B, nhưng phải cộng cả XLM-R và ViT5 nếu dùng). Kiểm tra bản vLLM trong Docker guideline có
  chạy được Qwen3.5 không trước khi chốt.
- Prompt mỗi shop khoảng 22.000 ký tự (rulebook ~18.500). Với `generate` tuần tự trên T4, K=8 sẽ chậm: bắt đầu
  bằng K=4–6, `max_tokens=500`, và luôn đặt `Config.time_budget` (giây) để phần chưa kịp tự thành abstain.
- Lấy mẫu có seed cố định (crc32 của câu hỏi + as_of_date) nhưng trên GPU không tái lập từng bit. Ngưỡng tái lập của
  BTC là 0,03: chạy 2 lần trên cùng shop val và so PA trước khi tin.

## 6. Những chỗ trong `clean.py` nên mang sang `ingest.py` / `values.py` / `rules.py` của v6
Đều đã gặp trên dữ liệu train:
- Dòng chân trang `Cộng` / `Ghi chú: ...` ở cuối mỗi sheet tháng (biz_105: 17 dòng tổng, mỗi dòng ~300 triệu).
  Trong v6, 40 dòng này vẫn nằm trong `sales_lines` của biz_105 (cột `product` = "Cộng" / "Ghi chú: ..."), nhưng
  `line_total` của chúng đang là 0 nên không làm sai tổng tiền; chúng vẫn có thể lọt vào phép đếm dòng / đếm mặt hàng.
- Ngày `10 thg 6 2025`, serial Excel `45689`, `01/02/2025`, ISO lẫn trong cùng một cột.
- Tiền `55.000đ`, `25k`, `2,825tr`, `1,500.0000` (xem mục 0).
- Số lượng kèm đơn vị `1 hộp`, `2 m3`, `1 xe 4m3` → cột số + cột `_dv`.
- Tên file lỗi mã khi giải nén zip trên Windows (`Danh s├ích h├áng h├│a.xlsx`) → `clean.fix_name` để khớp README.
- Điền mã đơn xuống trước rồi mới bỏ dòng trùng trong cùng đơn; chỉ điền xuống cột chữ/ngày, không điền cột số.

## 7. Mức ảnh hưởng của lỗi tiền (mục 0) đã đo được
Đo bằng `load_shop(..., mapper_backend=None)` của v6 (mapper heuristic), so với gold:
| Shop | Câu | v6 (view chuẩn) | Gold |
|---|---|---|---|
| biz_129 | doanh thu tháng 3/2026 | 908.855.175,49 | 1.016.912.500 |
| biz_105 | doanh thu tháng 1/2026 | 306.282.619 | 389.514.000 |

Quét cả 30 shop train bằng `sqlvote/scan_v6_money.py` (mapper heuristic, chưa sửa `values.py`):
| Shop | Dòng bán | Dòng nghi mất hệ số | Ghi chú |
|---|---|---|---|
| biz_105 | 138.023 | 30.337 (22,0%) | đã xác nhận: `25k` → 25 |
| biz_117 | 33.332 | 5.155 (15,5%) | 2.545 dòng có thành tiền < 1% của số lượng × đơn giá |
| biz_119 | 63.823 | 5.056 (7,9%) | chỉ theo tiêu chí "dưới 1000đ": nhà thuốc, có thể là giá thật của thuốc bán lẻ — cần xem tay |
| biz_120 | 90.706 | 6.707 (7,4%) | như biz_119 |
| biz_127 | 128.293 | 1.127 (0,9%) | thành tiền < 1% của số lượng × đơn giá |
| biz_129 | 145.479 | 1.327 (0,9%) | đã xác nhận: `1,45tr` → 1,45 |

14 shop còn lại có `line_total` thì không có dòng nghi ngờ nào.

Cũng trong lần quét này, với mapper heuristic (không LLM) có 11 shop v6 không dựng được `sales_lines.line_total`:
- không có cột `line_total`: biz_107, biz_110, biz_113, biz_123, biz_126;
- `load_shop` ném `KeyError` về `line_total`: biz_115, biz_116, biz_118, biz_121, biz_122;
- `load_shop` ném `KeyError: 'purchase_id'`: biz_124.

Chưa kiểm tra các shop này khi bật mapper LLM trên Kaggle (`use_llm_mapper: true`); nếu ở đó cũng vậy thì đường metric
của v6 bỏ trống toàn bộ câu doanh thu của các shop này.

Chạy lại sau khi sửa `values.py` (từ thư mục `datamate-ws`), số dòng nghi ngờ phải về gần 0:
```bash
python sqlvote/scan_v6_money.py . data/train
```

Cả hai shop này `sqlvote` ra đúng gold trên bảng thô đã làm sạch (xem `smoke_test.py`), nên chênh lệch nằm ở bước đọc
giá trị của v6 chứ không phải ở luật doanh thu.

## 8. Điểm chưa chắc, cần đo bằng gold
- Bỏ dòng trùng đang so trên giá trị đã chuẩn hoá, sau khi điền mã đơn nhưng trước khi điền các cột khác.
- `zero_threshold=1.01`: không bao giờ trả lời 0/rỗng (train chỉ có 4/2462 đáp án số bằng 0). Xem bảng `calib` rồi quyết.
- Số không nguyên có trị tuyệt đối ≥ 1000 được làm tròn về đồng (mọi đáp án `number` trong train đều là số nguyên).
- Cột `_4tt` suy trạng thái bằng từ điển chung; shop ghi kiểu lạ thì model phải theo README.
- Cổng "kỳ nằm ngoài dữ liệu" chỉ đổi bản nháp thành unanswerable khi bản nháp đó không có kết quả khác 0.
