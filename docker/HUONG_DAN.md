# Hướng dẫn build và nộp Docker (theo `zac2026_DataMate_docker_guideline_final.pdf`)

Hạn: **Test Solution 23:59 15/11** (1 lượt/ngày, BTC chạy thử trên máy thật) · **nộp chính thức 23:59 16/11**.

## Đã làm sẵn trong code
| Yêu cầu của đề | Cách đáp ứng |
|---|---|
| `bash /code/predict.sh`, không tham số, cấu hình cố định | `predict.sh` (gốc repo) → `datamate/launch.py` |
| 2 × RTX 5090, CUDA ≥ 12.8 | base `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime`; Qwen chạy **fp16** (không cần bitsandbytes); mỗi GPU một tiến trình, chia shop theo số câu (không dùng NCCL) |
| Ghi đáp án ngay, quá 6 giờ chỉ tính câu đã lưu | mỗi tiến trình ghi từng dòng vào `/result/parts/`; `submission.jsonl` được gộp lại mỗi 15 giây; cuối cùng câu thiếu ghi `abstain` |
| Log mỗi câu: `id, answer, elapsed_ms, thinking, code, output` | `datamate/predict.py::log_record` (thinking = null vì tắt chế độ suy nghĩ; output thô của Qwen vẫn lưu ở `llm_raw`) |
| `/data` chỉ đọc, không mạng | không ghi gì vào `/data`; `HF_HUB_OFFLINE=1`; file tạm ở `/tmp` |
| `/code/README.md` khai báo model (nguồn, revision, ngày phát hành, license, số tham số) | `docker/README_code.md` + `docker/make_context.py` điền số tham số đúng từ file weights |
| `/code/training_code/` + `data_manifest.json` (SHA-256) | `docker/make_context.py` chép code, dữ liệu train, dữ liệu SFT, log, cấu hình và băm mọi file |

## Việc của bạn (theo thứ tự)
1. **Cài Docker Desktop** (https://docs.docker.com/desktop/setup/install/windows-install/), chọn backend **WSL 2**
   (cần quyền admin, có thể phải khởi động lại). Mở Docker Desktop → Settings → Resources → Advanced: nếu ổ C còn
   ít chỗ thì chuyển "Disk image location" sang ổ có ≥ 40 GB trống. Kiểm tra: `docker version`.
2. **Tải weights Qwen3.5-4B** (~9,3 GB, đúng revision đã khai báo) — có thể nhờ Claude chạy:
   `hf download Qwen/Qwen3.5-4B --revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a --local-dir E:/models/Qwen3.5-4B`
3. **Chọn thành phần** (sau khi có kết quả lần 7): có dùng LoRA / XLM-R hay không. Lấy `datamate_submit/` và `state/` của
   lần chạy đó (`runs/<stamp>/`).
4. **Dựng thư mục build**:
   `python docker/make_context.py --qwen E:/models/Qwen3.5-4B --submit runs/<stamp>/datamate_submit --state runs/<stamp>/state`
   (thêm `--no-lora` / `--no-xlmr` nếu không dùng).
5. **Build + kiểm tra + xuất file** (Git Bash, ở thư mục repo): `bash docker/build.sh <ten_doi_viet_thuong>`
   → `build/export/zaic2026_datamate_<team>.tar.gz`, file `.md5`, file `.tar.size` (byte chưa nén).
6. **Tải lên Google Drive** (file nén ước ~13–14 GB; Drive miễn phí 15 GB — kiểm tra chỗ trống trước), chia sẻ link
   "bất kỳ ai có link". Tải thử về máy khác / thư mục khác và chạy `md5sum -c <file>.md5` → phải ra `OK`.
7. **Nộp ở Test Solution**: link Drive + MD5 + kích thước .tar chưa nén. Không đổi tên file sau khi tạo MD5.

## Giới hạn của lần kiểm tra ở máy này
Máy local không có GPU NVIDIA và chỉ 16 GB RAM → `build.sh` chỉ chạy được bước 3 với **model giả** (kiểm tra đọc dữ
liệu, log, định dạng, không mạng). Phần GPU thật (nạp Qwen fp16 trên 5090, thời gian, kết quả) chỉ được kiểm tra khi
BTC chạy lượt Test Solution → nên nộp lượt này sớm để còn sửa trước 16/11.

## Lưu ý tái lập (|PA nộp − PA BTC chạy lại| ≤ 0,03)
Giải mã greedy nên cùng phần cứng/phần mềm cho cùng đáp án. File `submission.jsonl` của vòng private nên được tạo bằng
CÙNG cấu hình với image (fp16, cùng weights, cùng calibration); nếu chạy trên Kaggle T4 thay vì Docker thì phải bật
fp16 (không 4-bit) để giống image.
