## Tổng (docker_merge.jsonl, 1000 câu)

| trả lời | bỏ trống | khớp tc | khác tc | điểm tc | ước LB (tc+0,05) |
|---|---|---|---|---|---|
| 713 | 287 | 593 | 120 | +0.473 | +0.523 |

### Theo shop

| shop | khớp | khác | bỏ trống | góp điểm | ghi chú |
|---|---|---|---|---|---|
| 4 shop giữ kín | 177 | 34 | 16 | +0.143 |  |
| dev_002 | 29 | 8 | 4 | +0.021 |  |
| dev_003 | 102 | 17 | 10 | +0.085 |  |
| dev_004 | 67 | 15 | 14 | +0.052 |  |
| dev_005 | 75 | 10 | 2 | +0.065 |  |
| dev_006 | 77 | 15 | 19 | +0.062 |  |
| dev_008 | 66 | 21 | 12 | +0.045 |  |
| dev_011 | 0 | 0 | 40 | +0.000 | chặn cả shop |
| dev_012 | 0 | 0 | 50 | +0.000 |  |
| dev_013 | 0 | 0 | 57 | +0.000 | chặn cả shop |
| dev_014 | 0 | 0 | 63 | +0.000 | chặn cả shop |

## Câu BỎ TRỐNG theo nguyên nhân × shop

| nguyên nhân | câu | tc có đáp án (lấy lại được) | theo shop |
|---|---|---|---|
| chặn cả shop (guard >20% unanswerable) | 149 | 144 | dev_011:38, dev_013:50, dev_014:61 |
| unanswerable → bỏ trống | 51 | 36 | 4 shop giữ kín:11, dev_002:4, dev_003:7, dev_004:10, dev_005:2, dev_006:5, dev_008:11, dev_012:1 |
| lỗi code (exception) | 48 | 47 | dev_012:48 |
| giá trị lọc không khớp dữ liệu | 23 | 22 | 4 shop giữ kín:3, dev_003:2, dev_004:4, dev_006:3, dev_008:1, dev_011:2, dev_013:7, dev_014:1 |
| phép tính / bộ lọc chưa có | 14 | 14 | 4 shop giữ kín:1, dev_003:1, dev_006:11, dev_012:1 |
| không hiểu câu (intent rỗng/sai) | 2 | 2 | 4 shop giữ kín:1, dev_014:1 |

### Shop bị chặn: nếu bỏ chặn (câu đã có đáp án số của pipeline, so tham chiếu)

| shop | khớp | khác | đổi điểm nếu bỏ chặn |
|---|---|---|---|
| dev_011 | 7 | 31 | -0.024 |
| dev_013 | 4 | 46 | -0.042 |
| dev_014 | 2 | 59 | -0.057 |

### Bỏ trống theo loại câu (kind của tham chiếu), 20 shop không giữ kín — top 25

| kind | thư viện | bỏ trống | chặn cả shop | unanswerable → bỏ trốn | lỗi code | giá trị lọc không khớp | phép tính / bộ lọc chư | không hiểu câu |
|---|---|---|---|---|---|---|---|---|
| revenue | có | 58 | 45 | 9 |  | 4 |  |  |
| service | KHÔNG | 49 |  | 1 | 47 |  | 1 |  |
| quantity | có | 28 | 19 | 1 |  | 8 |  |  |
| installment | KHÔNG | 12 | 12 |  |  |  |  |  |
| missing | KHÔNG | 11 | 4 | 5 | 1 | 1 |  |  |
| debt | có | 10 | 3 | 5 |  |  | 2 |  |
| payable | KHÔNG | 9 | 8 |  |  |  |  | 1 |
| avg_order | có | 8 | 6 | 2 |  |  |  |  |
| orders | có | 7 | 6 | 1 |  |  |  |  |
| adjustment | KHÔNG | 7 | 7 |  |  |  |  |  |
| top_products | có | 6 | 4 | 2 |  |  |  |  |
| trade | KHÔNG | 6 | 5 |  |  | 1 |  |  |
| deadline | KHÔNG | 6 |  | 4 |  | 2 |  |  |
| warranty | KHÔNG | 6 | 6 |  |  |  |  |  |
| expiry | có | 5 |  |  |  |  | 5 |  |
| orders_threshold | có | 4 | 4 |  |  |  |  |  |
| net_profit | có | 3 |  | 3 |  |  |  |  |
| supplier_amount | có | 3 |  | 2 |  |  | 1 |  |
| near_expiry | có | 3 |  |  |  |  | 3 |  |
| days_threshold | có | 3 | 3 |  |  |  |  |  |
| brand_share | KHÔNG | 3 | 3 |  |  |  |  |  |
| price_effect | có | 3 | 2 | 1 |  |  |  |  |
| best_day | có | 2 | 2 |  |  |  |  |  |
| trade_share | KHÔNG | 2 | 2 |  |  |  |  |  |
| model_top | có | 2 | 1 |  |  | 1 |  |  |

## Câu SAI (khác tham chiếu) theo tầng — phân loại tự động

| tầng | câu | ví dụ (shop [kind/metric ta] câu, ta, tc) |
|---|---|---|
| kiểu đáp án / danh sách / chữ khác | 17 | dev_008 [top_products/top_products] «Tuần rồi 5 món bán chạy nhất là những món nàoo?» ta=['Cánh gà chiên nước mắm', 'Bi tc=['Lẩu Thái tôm cá (nhỏ)', 'Can ; dev_006 [revenue/revenue] «Kể giúp dthu 3 tháng liền từ T4/2025 tới T6/2025, theo thứ tự thời gia» ta=[233818700, 248568700, 2371852 tc=233818700 |
| hiểu câu: metric | 16 | dev_002 [cancel_rate/revenue] «T2/2026 don huy chiem bao nhieu phan tram?» ta=100.0 tc=2.15 ; dev_008 [revenue/purchase_total] «Tháng 6/2025 quán đánh hàng về hết bao nhiêu tiền?» ta=414492100 tc=1042106900 |
| phép tính không có trong thư viện (kind) | 10 | dev_008 [top_staff/best_day] «trog th11/2025 nv nào bán đc dthu cao nhứt nhỉ» ta=2025-11-30 tc=NV005 ; dev_004 [delivery/quantity] «Tới hôm nay, xe đã giao tổng cộng mấy cuộn Dây điện Cadivi VCmd 2x2.5 » ta=81 tc=42 |
| hiểu câu: kỳ | 10 | dev_005 [price_effect/price_effect] «Tiffy Dey hộp 25 vỉ x 4 viên lên giá 1.200đ từ ngày 02/06/2025; so 14 » ta=-22.27 tc=-33.51 ; dev_005 [price_effect/price_effect] «Tiffy Dey hộp 25 vỉ x 4 viên đổi giá từ 1.200đ lên 1.300đ vào ngày 16/» ta=176.54 tc=-5.4 |
| đọc dữ liệu/ánh xạ hoặc định nghĩa (lệch > 15%) | 9 | dev_004 [quantity/quantity] «Tháng 5/2026 bán ra bao nhiêu cây Ống PVC Bình Minh D50 cây 4m?» ta=41 tc=77 ; dev_004 [quantity/quantity] «Tháng 3/2026 bán ra bao nhiêu cây Ống PVC Bình Minh D32 cây 4m?» ta=69 tc=123 |
| hiểu câu: bộ lọc | 9 | dev_008 [quantity/quantity] «Tuần trước quán bán được mấy đĩa vậy?» ta=8149 tc=0 ; dev_008 [quantity/quantity] «Tuan nay quan ban dc bnhiu dia?» ta=8232 tc=1581 |
| tính/định nghĩa (lệch ≤ 15%) | 8 | dev_003 [gross_profit/gross_profit] «trog tháng 6 wán mik lãi gộp đc bnhiu dzạ 🤔» ta=183804607 tc=186355417 ; dev_003 [gross_profit/gross_profit] «Lai gop th6/2025 duoc bao nhieu z?» ta=162696382 tc=164406262 |
| tham chiếu: không trả lời được (ta trả lời) | 7 | dev_005 [peak_hour/revenue] «Tiệm mình thường đông khách nhất dào mấy giờ z?» ta=10475600 tc=None ; dev_004 [missing/revenue] «03/2026 khach o duong Mai Chi Tho mua het bao nhieu tien?» ta=1193214000 tc=None |
| 4 shop giữ kín (không phân loại) | 34 |  |

## Loại câu tham chiếu có mà thư viện `metrics.py` KHÔNG có (20 shop không giữ kín, chỉ đếm)

| kind | câu | khớp | khác | bỏ trống |
|---|---|---|---|---|
| service | 49 | 0 | 0 | 49 |
| missing | 17 | 0 | 6 | 11 |
| installment | 12 | 0 | 0 | 12 |
| payable | 9 | 0 | 0 | 9 |
| delivery | 9 | 0 | 8 | 1 |
| adjustment | 7 | 0 | 0 | 7 |
| trade | 6 | 0 | 0 | 6 |
| deadline | 6 | 0 | 0 | 6 |
| warranty | 6 | 0 | 0 | 6 |
| brand_share | 3 | 0 | 0 | 3 |
| peak_hour | 2 | 0 | 1 | 1 |
| trade_share | 2 | 0 | 0 | 2 |
| avg_machine | 2 | 0 | 0 | 2 |
| top_staff | 1 | 0 | 1 | 0 |
| cancel_customer | 1 | 0 | 0 | 1 |
| new_members | 1 | 0 | 0 | 1 |
| purchase_qty | 1 | 0 | 1 | 0 |

## Mọi loại câu (20 shop không giữ kín): khớp / khác / bỏ trống

| kind | thư viện | câu | khớp | khác | bỏ trống |
|---|---|---|---|---|---|
| revenue | có | 255 | 176 | 21 | 58 |
| quantity | có | 55 | 15 | 12 | 28 |
| service | KHÔNG | 49 | 0 | 0 | 49 |
| orders | có | 46 | 39 | 0 | 7 |
| avg_order | có | 36 | 28 | 0 | 8 |
| debt | có | 29 | 16 | 3 | 10 |
| customers_threshold | có | 28 | 27 | 0 | 1 |
| top_products | có | 24 | 9 | 9 | 6 |
| orders_threshold | có | 17 | 12 | 1 | 4 |
| price_effect | có | 17 | 8 | 6 | 3 |
| days_threshold | có | 17 | 12 | 2 | 3 |
| missing | KHÔNG | 17 | 0 | 6 | 11 |
| installment | KHÔNG | 12 | 0 | 0 | 12 |
| cancel_rate | có | 12 | 10 | 2 | 0 |
| cancel_count | có | 12 | 12 | 0 | 0 |
| best_day | có | 10 | 8 | 0 | 2 |
| top_customer_orders | có | 9 | 7 | 2 | 0 |
| payable | KHÔNG | 9 | 0 | 0 | 9 |
| delivery | KHÔNG | 9 | 0 | 8 | 1 |
| top_profit | có | 7 | 6 | 0 | 1 |
| adjustment | KHÔNG | 7 | 0 | 0 | 7 |
| trade | KHÔNG | 6 | 0 | 0 | 6 |
| gross_profit | có | 6 | 3 | 3 | 0 |
| deadline | KHÔNG | 6 | 0 | 0 | 6 |
| warranty | KHÔNG | 6 | 0 | 0 | 6 |
| top_customers | có | 6 | 4 | 1 | 1 |
| products_orders_threshold | có | 5 | 5 | 0 | 0 |
| new_and_repaid | có | 5 | 5 | 0 | 0 |
| expiry | có | 5 | 0 | 0 | 5 |
| repaid | có | 5 | 5 | 0 | 0 |
| stock | có | 5 | 0 | 3 | 2 |
| purchase_minus_sales | có | 5 | 3 | 2 | 0 |
| purchase | có | 4 | 3 | 0 | 1 |
| idle | có | 4 | 3 | 0 | 1 |
| net_profit | có | 3 | 0 | 0 | 3 |
| supplier_amount | có | 3 | 0 | 0 | 3 |
| near_expiry | có | 3 | 0 | 0 | 3 |
| brand_share | KHÔNG | 3 | 0 | 0 | 3 |
| peak_hour | KHÔNG | 2 | 0 | 1 | 1 |
| trade_share | KHÔNG | 2 | 0 | 0 | 2 |
| model_top | có | 2 | 0 | 0 | 2 |
| avg_machine | KHÔNG | 2 | 0 | 0 | 2 |
| supplier_count | có | 1 | 0 | 0 | 1 |
| top_brand | có | 1 | 0 | 0 | 1 |
| top_staff | KHÔNG | 1 | 0 | 1 | 0 |
| loyal | có | 1 | 0 | 1 | 0 |
| vip | có | 1 | 0 | 1 | 0 |
| cancel_customer | KHÔNG | 1 | 0 | 0 | 1 |
| new_members | KHÔNG | 1 | 0 | 0 | 1 |
| purchase_qty | KHÔNG | 1 | 0 | 1 | 0 |
