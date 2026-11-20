# DataMate v6 — Zalo AI Challenge (bảng Data Mate)

Trả lời câu hỏi tiếng Việt về dữ liệu bán hàng của từng cửa hàng. Chạy offline hoàn toàn, không
gắn logic với id câu hỏi hay id shop. Sai bị −1 nên hệ thống ưu tiên bỏ trống khi không chắc.

## Chạy (bên trong container)
```
bash /code/predict.sh       # đọc /data, ghi /result/submission.jsonl và /result/logs/<biz>/<id>.json
```
Biến môi trường: `MODELS=/models`, `QUANTIZE_4BIT=1` (cùng độ chính xác với lúc học ngưỡng),
`USE_SQL=1`. Thư mục model nào có mặt thì bước tương ứng được bật.
Log mỗi câu có: id, đáp án cuối, thời gian (`elapsed_s`), JSON ý định, SQL sinh ra và kết quả,
`agree`, `p_answerable`, `p_correct`, lý do bỏ trống.

## Kiến trúc
```
ingest → profile → mapper (heuristic + Qwen JSON + kiểm tra cố định) → rules (view chuẩn theo rulebook)
  → ý định: Qwen3.5-4B + LoRA (bước 1) → timex → slots → validate → metric library ─┐
  → SQL: Qwen viết SQL trên view chuẩn → sqlglot → duckdb (bước 2) ────────────────┴→ agree?
  → XLM-R P(trả lời được | câu hỏi, khái niệm shop có) (bước 3)
  → calibration: trả lời / bỏ trống / unanswerable
```

| Model | Tham số | Vai trò |
|---|---|---|
| Qwen3.5-4B (4-bit) + LoRA r=16 | ~4–5 B | ý định JSON, SQL, ánh xạ bảng |
| XLM-RoBERTa base | 0.28 B | phân loại trả lời được / không |
| ViT5 base (tuỳ chọn) | 0.23 B | gợi ý chuẩn hoá câu hỏi (khoá số và tên hàng) |

Tổng < 6 B (giới hạn 15 B).

## Huấn luyện
Toàn bộ trong `notebooks/datamate_v6_kaggle.ipynb` (Kaggle T4). Các lệnh:
```
python -m datamate.sft_data      --train-root T --answers A --out sft            # bước 1: nhãn ý định đã kiểm chứng
python -m datamate.train_lora    --model QWEN --train sft/train.jsonl --val sft/val.jsonl --out models/intent_lora
python -m datamate.answerability build|train|predict ...                       # bước 3
python -m datamate.neural_norm   make-pairs|train|demo ...                      # bước 4 (tuỳ chọn)
python -m datamate.score_run / eval_grouped / report / calibration              # chấm, giữ kín theo shop, ngưỡng
```
Test không cần GPU: `pytest tests` và `python tests/smoke_predict.py --train-root T --out /tmp/s --sql`.

## Build image (nộp bài)
Theo hướng dẫn của BTC (`zac2026_DataMate_docker_guideline_final.pdf`): xem `docker/HUONG_DAN.md`.
`python docker/make_context.py --qwen <Qwen3.5-4B> --submit runs/<stamp>/datamate_submit --state runs/<stamp>/state`
→ `build/docker_context/` (bố cục `/code`), rồi `bash docker/build.sh <team>` (build, kiểm tra, xuất .tar.gz + MD5).
