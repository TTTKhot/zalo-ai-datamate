# Thống kê lỗi public (16/11) — cho Fable nghiên cứu kiến trúc

**Nguồn.** Replay log Qwen public (`runs/20261115-1216` + `runs/20261115-1135`, `run_public/logs`) qua code 16/11
(cổng rulebook TẮT + gộp bảng bán tách theo tháng), áp thứ tự Docker (`datamate.launch.apply_guards`: chặn cả shop
> 20% unanswerable, unanswerable → bỏ trống). Đầu ra: `runs/20261116_kiem/docker_merge.jsonl`; lý do từng câu:
`runs/20261116_kiem/replay_merge.reasons.jsonl`. Tạo lại bảng: `python kaggle/thong_ke_loi.py
runs/20261116_kiem/replay_merge.jsonl runs/20261116_kiem/docker_merge.jsonl`.
**So với** tham chiếu ChatGPT (`runs/tham_chieu_gpt/`, đúng ~95%, KHÔNG phải đáp án); "kind" = loại câu theo
`phan_ra.json`. Ánh xạ bảng dựng lại bằng heuristic (không phải mapper LLM). Điểm public là ước lượng LẠC QUAN
(đã sửa từ lỗi public ở 15/11). 4 shop giữ kín (dev_001/007/009/010): chỉ số tổng.

## Ý chính
- Trả lời 713 câu, **83% khớp** tham chiếu; bỏ trống 287 câu, **265 câu tham chiếu có đáp án** (lấy lại được).
- 197/287 câu bỏ trống nằm ở **4 shop**: 3 shop bị chặn cả shop (dev_011/013/014, ngành điện thoại/mẹ-bé) và dev_012
  (tiệm sửa xe: bảng `sosuaxe` bị nhận là chi phí → không có bảng bán → TypeError ở mọi câu; nguyên nhân chính xác chưa soát).
- Bỏ chặn 3 shop đó với code hiện tại sẽ **mất điểm** (13 khớp / 136 khác): chặn đúng; muốn lấy lại phải đọc đúng
  dữ liệu ngành mới (trả góp, thu máy cũ, bảo hành, dòng máy, hãng) chứ không phải nới ngưỡng.
- Câu sai (86 ở 20 shop không giữ kín) rải đều các tầng; lớn nhất: khuôn đầu ra/danh sách (17), hiểu sai metric (16).

## 1. Tổng
| trả lời | bỏ trống | khớp tc | khác tc | điểm tc | ước LB (tc + 0,05) |
|---|---|---|---|---|---|
| 713 | 287 | 593 | 120 | +0,473 | +0,523 |

Trước/sau các sửa 16/11 (cùng log, cùng cách chấm):
| bản | trả lời | khớp/khác | điểm tc | leaderboard thật / ước |
|---|---|---|---|---|
| code chốt 15/11 có cổng (Docker đã xuất) | — | — | +0,369 | ≈ 0,42 (ước) |
| code chốt, không cổng (= file 21, khớp 1000/1000 dòng) | 591 | 489/102 | +0,387 | **0,443 thật** |
| + gộp bảng bán theo tháng (code 16/11) | 713 | 593/120 | **+0,473** | ≈ 0,52–0,53 (ước) |

## 2. Theo shop
| shop | khớp | khác | bỏ trống | góp điểm | ghi chú |
|---|---|---|---|---|---|
| 4 shop giữ kín | 177 | 34 | 16 | +0,143 | không đổi qua các sửa 16/11 |
| dev_002 | 29 | 8 | 4 | +0,021 | hết bị chặn nhờ gộp tháng |
| dev_003 | 102 | 17 | 10 | +0,085 | |
| dev_004 | 67 | 15 | 14 | +0,052 | |
| dev_005 | 75 | 10 | 2 | +0,065 | hết bị chặn nhờ gộp tháng |
| dev_006 | 77 | 15 | 19 | +0,062 | |
| dev_008 | 66 | 21 | 12 | +0,045 | |
| dev_011 | 0 | 0 | 40 | 0 | chặn cả shop |
| dev_012 | 0 | 0 | 50 | 0 | lỗi code mọi câu |
| dev_013 | 0 | 0 | 57 | 0 | chặn cả shop |
| dev_014 | 0 | 0 | 63 | 0 | chặn cả shop |

## 3. Câu BỎ TRỐNG theo nguyên nhân × shop
| nguyên nhân | câu | tc có đáp án | theo shop |
|---|---|---|---|
| chặn cả shop (> 20% unanswerable) | 149 | 144 | dev_011:38, dev_013:50, dev_014:61 |
| unanswerable → bỏ trống | 51 | 36 | giữ kín:11, 002:4, 003:7, 004:10, 005:2, 006:5, 008:11, 012:1 |
| lỗi code (TypeError, shop không có bảng bán) | 48 | 47 | dev_012:48 |
| giá trị lọc không khớp dữ liệu (sản phẩm/size/trạng thái/ca không tìm thấy) | 23 | 22 | giữ kín:3, 003:2, 004:4, 006:3, 008:1, 011:2, 013:7, 014:1 |
| phép tính / bộ lọc chưa có (tồn theo lô, `unknown filter`) | 14 | 14 | giữ kín:1, 003:1, 006:11, 012:1 |
| không hiểu câu (intent rỗng) | 2 | 2 | giữ kín:1, 014:1 |
| **tổng** | **287** | **265** | |

Chi tiết unanswerable (lý do pipeline, 1000 câu trước guard): không ghi thanh toán/nợ 27 · không có mã đơn 16 ·
intent đánh dấu unanswerable 13 · không có nhóm khách 13 · không có nhóm hàng 9 · không có sổ chi phí 4 · không có
cột NCC 4 · khác ≤ 2 mỗi loại.

Shop bị chặn — nếu bỏ chặn (câu pipeline đã trả lời, so tham chiếu):
| shop | khớp | khác | đổi điểm |
|---|---|---|---|
| dev_011 | 7 | 31 | −0,024 |
| dev_013 | 4 | 46 | −0,042 |
| dev_014 | 2 | 59 | −0,057 |

## 4. Bỏ trống theo loại câu (20 shop không giữ kín, top)
| kind | thư viện | bỏ trống | chặn shop | unans→bỏ | lỗi code | lọc không khớp | chưa có |
|---|---|---|---|---|---|---|---|
| revenue | có | 58 | 45 | 9 | | 4 | |
| service (hoa hồng thợ, phiếu sửa) | KHÔNG | 49 | | 1 | 47 | | 1 |
| quantity | có | 28 | 19 | 1 | | 8 | |
| installment (trả góp) | KHÔNG | 12 | 12 | | | | |
| missing (tc: thiếu dữ liệu) | — | 11 | 4 | 5 | 1 | 1 | |
| debt | có | 10 | 3 | 5 | | | 2 |
| payable (tiền khách phải trả sau bớt/thu máy cũ) | KHÔNG | 9 | 8 | | | | (1 intent rỗng) |
| avg_order | có | 8 | 6 | 2 | | | |
| orders | có | 7 | 6 | 1 | | | |
| adjustment (voucher/giảm giá) | KHÔNG | 7 | 7 | | | | |
| top_products | có | 6 | 4 | 2 | | | |
| trade (thu máy cũ) | KHÔNG | 6 | 5 | | | 1 | |
| deadline (hạn trả nợ) | KHÔNG | 6 | | 4 | | 2 | |
| warranty (bảo hành) | KHÔNG | 6 | 6 | | | | |
| expiry / near_expiry (lô, hạn dùng) | có một phần | 8 | | | | | 8 |
| net_profit | có | 3 | | 3 | | | |
| supplier_amount | có | 3 | | 2 | | | 1 |

## 5. Câu SAI theo tầng (20 shop không giữ kín: 86 câu; giữ kín: 34 câu, không phân loại)
Phân loại tự động theo thứ tự: kind tc không có trong thư viện → metric khác kind → kỳ khác kỳ tc → khoá bộ lọc khác
→ độ lệch số. Là ước lượng.
| tầng | câu | ví dụ (shop, câu rút gọn → ta / tc) |
|---|---|---|
| khuôn đầu ra (danh sách, chuỗi, top-k) | 17 | dev_008 "5 món bán chạy nhất tuần rồi" → danh sách khác thứ tự/món; dev_006 "dthu 3 tháng liền T4–T6" → ta danh sách 3 số, tc 1 số |
| hiểu câu: metric | 16 | dev_002 "đơn hủy chiếm bao nhiêu %" → ta revenue 100 / tc 2,15; dev_008 "đánh hàng về hết bao nhiêu" → ta purchase_total ≠ kind revenue |
| phép tính không có (kind) | 10 | dev_008 "nv nào bán dthu cao nhất" → ta best_day; dev_004 "xe đã giao mấy cuộn" (giao nhiều đợt) → ta quantity 81 / tc 42 |
| hiểu câu: kỳ | 10 | dev_005 price_effect "so 14 ngày … từ ngày đổi giá" → cửa sổ ngày khác (−22,3 / −33,5) |
| đọc dữ liệu/ánh xạ hoặc định nghĩa (lệch > 15%) | 9 | dev_004 "bán ra bao nhiêu cây Ống PVC D50" → 41 / 77 (đơn vị/quy đổi) |
| hiểu câu: bộ lọc | 9 | dev_008 "tuần trước bán mấy đĩa" → ta không lọc đơn vị "đĩa" (8149 / 0) |
| tính/định nghĩa (lệch ≤ 15%) | 8 | dev_003 lãi gộp tháng 6 → 183,8tr / 186,4tr (giá vốn) |
| tc nói không trả lời được, ta trả lời | 7 | dev_005 "đông khách nhất mấy giờ" → ta revenue |

## 6. Loại câu tham chiếu có mà `metrics.py` KHÔNG có (20 shop không giữ kín)
| kind | câu | khớp | khác | bỏ trống | ghi chú |
|---|---|---|---|---|---|
| service | 49 | 0 | 0 | 49 | toàn dev_012 (tiệm sửa xe) |
| installment | 12 | 0 | 0 | 12 | điện thoại |
| payable | 9 | 0 | 0 | 9 | sau bớt + thu máy cũ |
| delivery | 9 | 0 | 8 | 1 | giao nhiều đợt — trả lời sai 8 |
| adjustment | 7 | 0 | 0 | 7 | voucher/giảm |
| trade | 6 | 0 | 0 | 6 | thu máy cũ |
| deadline | 6 | 0 | 0 | 6 | ngày phải trả |
| warranty | 6 | 0 | 0 | 6 | bảo hành |
| brand_share / trade_share / avg_machine | 7 | 0 | 0 | 7 | điện thoại |
| peak_hour, top_staff, cancel_customer, new_members, purchase_qty | 6 | 0 | 3 | 3 | |
| missing (tc: thiếu dữ liệu → unanswerable) | 17 | 0 | 6 | 11 | |
| **tổng (trừ missing)** | **117** | 0 | 11 | 106 | |

Loại có trong thư viện nhưng tỉ lệ khớp thấp: quantity 15 khớp / 12 khác / 28 trống (55 câu), top_products 9/9/6,
stock 0/3/2, price_effect 8/6/3, gross_profit 3/3/0.
