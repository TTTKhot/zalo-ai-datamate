# Run 20261113-1846

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_v5 (30 shop): đúng 214 sai 69 bỏ trống 17 → 145  ← chi tiết bên dưới
- results_v5_sql (30 shop): đúng 215 sai 74 bỏ trống 11 → 141

## results_v5 theo shop

- biz_101: đúng 9 sai 1 bỏ trống 0 → 8
- biz_102: đúng 8 sai 2 bỏ trống 0 → 6
- biz_103: đúng 8 sai 2 bỏ trống 0 → 6
- biz_104: đúng 9 sai 1 bỏ trống 0 → 8
- biz_105: đúng 7 sai 3 bỏ trống 0 → 4
- biz_106: đúng 9 sai 1 bỏ trống 0 → 8
- biz_107: đúng 9 sai 0 bỏ trống 1 → 9
- biz_108: đúng 9 sai 1 bỏ trống 0 → 8
- biz_109: đúng 8 sai 2 bỏ trống 0 → 6
- biz_110: đúng 9 sai 1 bỏ trống 0 → 8
- biz_111: đúng 8 sai 2 bỏ trống 0 → 6
- biz_112: đúng 6 sai 4 bỏ trống 0 → 2
- biz_113: đúng 9 sai 1 bỏ trống 0 → 8
- biz_114: đúng 10 sai 0 bỏ trống 0 → 10
- biz_115: đúng 9 sai 1 bỏ trống 0 → 8
- biz_116: đúng 9 sai 1 bỏ trống 0 → 8
- biz_117: đúng 1 sai 7 bỏ trống 2 → -6
- biz_118: đúng 5 sai 5 bỏ trống 0 → 0
- biz_119: đúng 9 sai 0 bỏ trống 1 → 9
- biz_120: đúng 6 sai 4 bỏ trống 0 → 2
- biz_121: đúng 7 sai 3 bỏ trống 0 → 4
- biz_122: đúng 2 sai 7 bỏ trống 1 → -5
- biz_123: đúng 0 sai 1 bỏ trống 9 → -1
- biz_124: đúng 5 sai 3 bỏ trống 2 → 2
- biz_125: đúng 10 sai 0 bỏ trống 0 → 10
- biz_126: đúng 10 sai 0 bỏ trống 0 → 10
- biz_127: đúng 3 sai 7 bỏ trống 0 → -4
- biz_128: đúng 10 sai 0 bỏ trống 0 → 10
- biz_129: đúng 4 sai 6 bỏ trống 0 → -2
- biz_130: đúng 6 sai 3 bỏ trống 1 → 3

**Tổng results_v5: đúng 214 sai 69 bỏ trống 17 → 145**

## Theo metric

- revenue: {'wrong': 34, 'correct': 89, 'abstain': 5}
- order_count: {'correct': 13, 'wrong': 4, 'abstain': 4}
- avg_order_value: {'correct': 12, 'wrong': 6}
- quantity: {'correct': 28, 'wrong': 3, 'abstain': 2}
- top_customers: {'wrong': 4, 'correct': 2}
- stock: {'wrong': 3, 'abstain': 1}
- unit_price: {'correct': 9, 'wrong': 3}
- None: {'abstain': 3}
- unsold_products: {'wrong': 2, 'correct': 1}
- price_effect: {'wrong': 2, 'correct': 3}
- debt_total: {'correct': 3, 'wrong': 1, 'abstain': 1}
- cancelled_count: {'correct': 5, 'wrong': 2}
- customers_min_orders: {'wrong': 2}
- best_day: {'correct': 16, 'wrong': 1}
- top_products: {'correct': 5, 'abstain': 1}
- purchase_total: {'correct': 1, 'wrong': 1}
- new_debt_and_repaid: {'correct': 1, 'wrong': 1}
- cancel_rate: {'correct': 18}
- avg_purchase_price: {'correct': 3}
- debt_table: {'correct': 2}
- products_min_orders: {'correct': 1}
- debtor_count: {'correct': 2}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 145 (214✓ 69✗ 17–) | 139 (206✓ 67✗ 27–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 141 (215✓ 74✗ 11–) | 137 (205✓ 68✗ 27–) | 141 (198✓ 57✗ 45–) | · | · | · | · |


## Câu sai / bỏ trống

- [biz_101] wrong | q_eccd1eb5d9ff | cho tôi bieets dthu tháng 5/2026
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2026}], "filters": {"product": "Bia Heineken 330ml"}}
  answer: 4510000 | gold: 236600600 | reason: None | fixes: ['dropped output pct without compare']
- [biz_102] wrong | q_d55269aa2f36 | cho hỏi top 3 khách mua nhiều tieenf nhaats tháng 12/2025 là ai
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"k": 3, "by": "revenue"}}
  answer: ['kl', 'Trương Dương Hằng', 'Trịnh Khoa An'] | gold: ['Trương Dương Hằng', 'Trịnh Khoa An', 'Cao Loan Hiếu'] | reason: None | fixes: []
- [biz_102] wrong | q_f14c7c3cd8ad | 3 khach co tong tien mua cao nhat thang 4/2025 la ai ha
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 4, "year": 2025}], "params": {"k": 3, "by": "revenue"}}
  answer: ['kl', 'Giang Hải Linh', 'Quách An Ngân'] | gold: ['Giang Hải Linh', 'Quách An Ngân', 'Trịnh Khoa An'] | reason: None | fixes: []
- [biz_103] wrong | q_e079351d24aa | dem giup toi so mon ban cham den muc trong 7 ngay gan nhat khong ban dc lan nao
  intent: {"metric": "unsold_products", "periods": [{"type": "last_n_days", "n": 7}], "filters": {"product": "món bán chậm"}, "params": {"threshold": 0}}
  answer: None | gold: 1 | reason: intent marked unanswerable | fixes: []
- [biz_103] wrong | q_e69dcf0740d1 | check gium so so goi snack lay's vi tu nhien 56g ban ra trong 30 ngay ke tu ngay 18/12/2025, ngay tang gia len 13.500đ, vs 30 ngay ngay truoc ngay do: tang hay giam bao nhieu %
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-12-18"}], "filters": {"product": "Snack Lay's vị tự nhiên 56g"}, "params": {"days": 30, "new_price": 13500, "date": "2025-11-19"}, "answerable": true}
  answer: -50.33 | gold: 26.39 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2025-12-18', 'end_date': '2026-01-17'}] -> [{'type': 'day', 'date': '2025-12-18'}] (date tagger)", 'price_effect date from periods', 'dropped output pct without compare']
- [biz_104] wrong | q_f0a9c2c89441 | tháng 2/2026 bán ra nhiêu phần topping thạch cà phê
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"product": "Topping Thạch cà phê"}, "share_of_total": true}
  answer: 0.3 | gold: 58 | reason: None | fixes: []
- [biz_105] wrong | q_ece3c46e24d3 | dthu tu dau thang nay den het hom nay tang hay giam bao nhieu % so voi cung ky thang roi do
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "compare": "previous", "output": "pct"}
  answer: 4.3 | gold: 2.83 | reason: None | fixes: ['compare same_period_last_year -> previous']
- [biz_105] wrong | q_f1c5c01b78e0 | Tháng 2/2026 có mấy đơn có dthu từ 130.000 đồng trở lên?
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 2, "year": 2026}], "params": {"strict": false, "min_value": 130000}}
  answer: 234 | gold: 385 | reason: None | fixes: ['moved filters.params -> params', 'strict -> False']
- [biz_105] wrong | q_fe699a7dc387 | giá trị trung bình một đơn tháng 3/2025 là bao nhiêu ta
  intent: {"metric": "avg_order_value", "periods": [{"type": "month", "month": 3, "year": 2025}]}
  answer: 54139 | gold: 70888 | reason: None | fixes: ['dropped output diff without compare']
- [biz_106] wrong | q_f24714cccf9d | trong tháng 5/2025, tiền khách trả bớt nợ các đơn mua chịu được bao nhiêu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2025}], "filters": {"payment_method": "Ghi nợ"}}
  answer: 3463000 | gold: 2842173 | reason: None | fixes: ['dropped output diff without compare']
- [biz_107] abstain | q_c1c2d4383a19 | hôm nay cuwar hangf bán đươc bao nhiu tiền z
  intent: {"metric": "revenue", "periods": [{"type": "today"}], "filters": {"product": "Cua hàng bán được"}, "answerable": true}
  answer: None | gold: 4152200 | reason: product 'Cua hàng bán được' not in shop data | fixes: ['dropped compare previous (no comparison words)', 'dropped compare previous (no comparison words)']
- [biz_108] wrong | q_f1bfb1c1ea00 | trong tong dthu thang 12/2025, doanh thu cac don ban qua Zalo OA chiem bn phan tram
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"payment_method": "Zalo OA"}, "share_of_total": true}
  answer: None | gold: 4.23 | reason: no payment method column | fixes: []
- [biz_109] wrong | q_f519b57113e1 | check giumf dthu tết năm nay so vs tết năm trc thay đổi mấy phần trăm
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "compare": "same_period_last_year", "output": "pct"}
  answer: -10.31 | gold: -26.22 | reason: None | fixes: []
- [biz_109] wrong | q_fbef1e31ad7a | e thang 8/2025 khach tra no cho cac don da mua chiu total bao nhieu tien
  intent: {"metric": "debt_total", "periods": [{"type": "month", "month": 8, "year": 2025}], "params": {"min_age": null}}
  answer: 18147933 | gold: 23368734 | reason: None | fixes: []
- [biz_110] wrong | q_f19c4e273491 | quý 4/2025 cuwar hàng có bn order ddos
  intent: {"metric": "order_count", "periods": [{"type": "quarter", "quarter": 4, "year": 2025}], "filters": {"status": "ddos"}}
  answer: 0 | gold: 6236 | reason: None | fixes: []
- [biz_111] wrong | q_f0859c5b2adb | Tháng 8/2025 cửa hàng thu được bao nhiêu tiền khách trả nợ?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"payment_method": "debt"}}
  answer: 2306000 | gold: 1476503 | reason: None | fixes: []
- [biz_111] wrong | q_fee5b1d42b55 | thang 7/2026, dthu cac don tra bang tm chiem bao nhieu phan tram tong doanh thu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2026}], "filters": {"payment_method": "transfer"}, "share_of_total": true}
  answer: 34.56 | gold: 40.3 | reason: None | fixes: []
- [biz_112] wrong | q_ee530fc682e1 | dthu nhóm hàng bánh chiếm bao nhiêu phần trăm tổng doanh thu tháng 2 năm 2026?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"group": "bánh"}, "share_of_total": true}
  answer: 0.0 | gold: 3.23 | reason: None | fixes: ['dropped output pct without compare']
- [biz_112] wrong | q_f3d30bcd1487 | So số ly Sinh tố xoài (L) bán ra trong 30 ngày kể từ ngày 04/09/2025, ngày tăng giá lên 50.500đ, với 30 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu % nhỉ?
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-09-04"}], "filters": {"product": "Sinh tố xoài (L)"}, "params": {"date": "2025-09-04"}}
  answer: 87.5 | gold: 7.04 | reason: None | fixes: ["periods [{'type': 'range', 'days': 30, 'date': '2025-09-04'}] -> [{'type': 'day', 'date': '2025-09-04'}] (date tagger)", 'price_effect date from periods', 'dropped output pct without compare']
- [biz_112] wrong | q_f42871042dc7 | thang 9/2025 nhom banh chiem bn % dthu z
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"group": "bánh"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 3.63 | reason: None | fixes: ['dropped output pct without compare']
- [biz_112] wrong | q_fe680ecf01d9 | ngay 10/09/2025 soda chanh day (m) tang gia tu 35.000đ len 37.000đ. so ly ban duoc trong 14 ngay ke tu ngay do so vs 14 ngay truoc do thay doi bao nhieu %
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-09-10"}], "compare": "previous", "output": "pct", "filters": {"product": "Soda chanh dây (M)"}, "params": {"days": 14}, "answerable": true}
  answer: 200.0 | gold: -29.73 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2025-09-26', 'end_date': '2025-10-10'}] -> [{'type': 'day', 'date': '2025-09-10'}] (date tagger)"]
- [biz_113] wrong | q_e24f4eb5442a | Doanh thu hôm qua của cửa hàng là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "yesterday"}]}
  answer: 42473400 | gold: 45552900 | reason: None | fixes: []
- [biz_115] wrong | q_ed929e98cc18 | tháng 1/2026 ai mua hàng nhìu tiền nhất
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 1, "year": 2026}], "params": {"by": "revenue"}}
  answer: kl | gold: Vương Phúc Dương | reason: None | fixes: []
- [biz_116] wrong | q_fcdacd705ef0 | thang 12/2025 nhom hoan thien chiem bnhiu % dthu z
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"group": "hoàn thiện"}, "share_of_total": true}
  answer: 0.0 | gold: 3.45 | reason: None | fixes: []
- [biz_117] wrong | q_f06ff238b76c | gia ban mot m3 Cat san lap vao ngay 21/06/2025 la bao nhieu z
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-06-21"}], "filters": {"product": "Cát san lấp"}}
  answer: None | gold: 240000 | reason: product not sold that day | fixes: []
- [biz_117] abstain | q_f07d1a553011 | Tháng 8/2025 có bao nhiêu đơn có doanh thu từ 3.300.000 đồng trở lên?
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"min_value": 3300000, "strict": true}}
  answer: None | gold: 88 | reason: unknown filter min_value; unknown filter strict | fixes: []
- [biz_117] wrong | q_f3d26f111d55 | xem giúp tuần rồi, số ddown ca chiều tăng hay giảm bao nhiu % so vs ca sáng
  intent: {"metric": "order_count", "periods": [{"type": "last_week"}], "output": "pct", "shift_compare": true}
  answer: None | gold: -55.17 | reason: no morning sales | fixes: ['compare same_period_last_year -> previous', 'shift_compare from cue']
- [biz_117] wrong | q_f4c328691e9b | dthu tu dau thang nay den het hom nay tang hay giam bn % so voi cung ky thang trc
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "compare": "previous", "output": "pct"}
  answer: None | gold: -32.31 | reason: comparison base is zero | fixes: []
- [biz_117] wrong | q_f7a67bc6eecd | Có bao nhiêu mặt hàng vẫn đang bán mà trong 7 ngày gần nhất không bán ra được cái nào?
  intent: {"metric": "unsold_products", "periods": [{"type": "last_n_days", "n": 7}], "filters": {"status": "active"}, "params": {"threshold": 0}, "answerable": true}
  answer: 0 | gold: 1 | reason: None | fixes: []
- [biz_117] wrong | q_f7eb4c1dfb74 | tuan nay dthu duoc bao nhiu
  intent: {"metric": "revenue", "periods": [{"type": "this_week"}]}
  answer: 0 | gold: 200921900 | reason: None | fixes: []
- [biz_117] abstain | q_f895c5de92bd | Có bao nhiêu khách hàng ở đường Trần Não?
  intent: {}
  answer: None | gold: UNANSWERABLE | reason: no intent | fixes: []
- [biz_117] wrong | q_fb33573520e0 | doanh thu cua son dulux weathershield powerflexx 5L trong thang 8 nam 2025 la bn
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"product": "Sơn Dulux Weathershield Powerflexx 5L"}}
  answer: 0 | gold: 80600000 | reason: None | fixes: []
- [biz_117] wrong | q_fca74e8bad45 | doanh thu 30 ngày gần nhất của cửa hàng là bao nhiêu
  intent: {"metric": "revenue", "periods": [{"type": "last_n_days", "n": 30}]}
  answer: 0 | gold: 1190996400 | reason: None | fixes: ['dropped output diff without compare']
- [biz_118] wrong | q_ec5c0d7eed96 | thang 3/2026 co bnhiu don bi huy vi giao tre
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2026}], "filters": {"status": "giao tre"}}
  answer: 0 | gold: UNANSWERABLE | reason: None | fixes: []
- [biz_118] wrong | q_ed21efdd6942 | bn khách mua ít nhất 3 đơn trong tháng 12 năm 2025 vậy
  intent: {"metric": "customers_min_orders", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"threshold": 3}}
  answer: 118 | gold: 117 | reason: None | fixes: []
- [biz_118] wrong | q_ed3ef76aa90c | dthu nhóm hàng cát đá tháng 7 năm 2026 là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2026}], "filters": {"group": "cát đá"}}
  answer: 0 | gold: 188137000 | reason: None | fixes: []
- [biz_118] wrong | q_f2fa231f8444 | Trong số khách có mua tháng 1 năm 2026, tỉ lệ khách mua ít nhất 4 đơn là bao nhiêu %?
  intent: {"metric": "customers_min_orders", "periods": [{"type": "month", "month": 1, "year": 2026}], "params": {"as_percent": true, "threshold": 4}}
  answer: 28.07 | gold: 27.75 | reason: None | fixes: []
- [biz_118] wrong | q_fdca3d13b254 | tháng 2/2025 nhóm điện chiếm bnhiu % doanh thu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "điện"}, "share_of_total": true}
  answer: 0.0 | gold: 25.99 | reason: None | fixes: []
- [biz_119] abstain | q_ef1a03f3f07b | thuoc co hoat chat loratadin thang nay ban duoc tong cong bao nhieu tien ta
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "filters": {"product": "Thuốc có hoạt chất Loratadin"}}
  answer: None | gold: 812300 | reason: product 'Thuốc có hoạt chất Loratadin' not in shop data | fixes: ["periods [{'type': 'month', 'month': 7, 'year': 2026}] -> [{'type': 'this_month'}] (date tagger)", 'dropped output diff without compare', "periods [{'type': 'month', 'month': 7, 'year': 2026}] -> [{'type': 'this_month'}] (date tagger)", 'dropped output diff without compare']
- [biz_120] wrong | q_f448394fcfee | thang 9/2025, dthu cac don ban qua dien thoai la bao nhieu, doanh thu cac don ban qua zalo oa la bao nhieu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"payment_method": "điện thoại"}, "answerable": true}
  answer: None | gold: [13759000, 16074900] | reason: no payment method column | fixes: ['dropped output diff without compare']
- [biz_120] wrong | q_f963fc3db789 | ton kho Otrivin 0,1% xit mui chai 10ml cuoi ngay hom nay la bao nhieu chai vay
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Otrivin 0,1% xịt mũi chai 10ml"}}
  answer: 2278 | gold: 150 | reason: None | fixes: []
- [biz_120] wrong | q_fa4e465d2ea1 | Cho mình hỏi tuần trước ca sáng có bao nhiêu đơn hàng?
  intent: {"metric": "order_count", "periods": [{"type": "last_week"}], "filters": {"shift": "ca_sang"}}
  answer: 380 | gold: 268 | reason: None | fixes: []
- [biz_120] wrong | q_fdc6c8321774 | ton kho gofen 400 hop 5 vi x 10 vien nang cuoi ngay hom nay la bao nhieu vien
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Gofen 400 hộp 5 vỉ x 10 viên nang"}}
  answer: 11800 | gold: 75 | reason: None | fixes: []
- [biz_121] wrong | q_e6dd8fd4a42a | ê pharmaton essential hộp 30 viên lên giá 231.500đ từ ngày 20/05/2025; so 30 ngày kể từ ngày tăng giá với 30 ngày ngay trc, lượng bán tính theo hộp tăng hay giảm bao nhiu %
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-05-20"}], "filters": {"product": "Pharmaton Essential hộp 30 viên"}, "compare": "previous", "output": "pct"}
  answer: None | gold: 13.95 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2025-06-19', 'end_date': '2025-07-19'}] -> [{'type': 'day', 'date': '2025-05-20'}] (date tagger)"]
- [biz_121] wrong | q_ec33e9c57c6e | thang 2/2026 dthu hang hok ke don la bn do
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"product": "Hàng hok ke đơn"}}
  answer: None | gold: 242427700 | reason: intent marked unanswerable | fixes: ['dropped output pct without compare', 'dropped output pct without compare']
- [biz_121] wrong | q_f26d33760e59 | So số viên UPSA-C 1g viên sủi tuýp 10 viên bán ra trong 14 ngày kể từ ngày 22/03/2026, ngày tăng giá lên 3.900đ, với 14 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu %?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2026-03-22"}], "filters": {"product": "UPSA-C 1g viên sủi tuýp 10 viên"}, "compare": "previous", "output": "pct"}
  answer: 66.67 | gold: -0.64 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2026-03-08', 'end_date': '2026-03-22'}] -> [{'type': 'day', 'date': '2026-03-22'}] (date tagger)"]
- [biz_122] abstain | q_f120d0f5e7d0 | có bnhiu khách hàng ở đường hậu giang
  intent: {}
  answer: None | gold: UNANSWERABLE | reason: no intent | fixes: []
- [biz_122] wrong | q_f1f68541c1b6 | So với tháng liền trước, doanh thu tháng 8 năm 2025 thay đổi bao nhiêu %?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "compare": "previous", "output": "pct"}
  answer: -15.36 | gold: -10.35 | reason: None | fixes: []
- [biz_122] wrong | q_f1fad9500cbd | Trung bình mỗi đơn tuần trước mang về bao nhiêu doanh thu?
  intent: {"metric": "avg_order_value", "periods": [{"type": "last_week"}]}
  answer: 43195 | gold: 85165 | reason: None | fixes: ['dropped output pct without compare']
- [biz_122] wrong | q_f5a2e8472196 | cho toi biet doanh thu thang 1/2026
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 1, "year": 2026}], "answerable": true}
  answer: 127099772 | gold: 256542200 | reason: None | fixes: []
- [biz_122] wrong | q_fbb2dfbdae61 | thuốc có hoạt chất vitamin c tháng 10/2025 bán được tổng cộng bao nhiêu tiền
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 10, "year": 2025}], "filters": {"product": "Vitamin C 500mg Quapharco hộp 10 vỉ x 10 viên"}}
  answer: 236695 | gold: 2281500 | reason: None | fixes: []
- [biz_122] wrong | q_fe14e521d3e0 | ton kho strepsils cool hop 2 vi x 12 vien cuoi ngay hom nay dc may hop chan va may vien le
  intent: {"metric": "stock", "periods": [{"type": "as_of", "date": "2026-07-17"}], "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"split_big_unit": true}}
  answer: None | gold: [8, 9] | reason: no stock report | fixes: []
- [biz_122] wrong | q_fe7efca0973e | Trừ thuốc kê đơn ra, tháng 2/2026 các mặt hàng còn lại bán được bao nhiêu tiền?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"group": "tiêu hoá"}}
  answer: 0 | gold: 238810400 | reason: None | fixes: ['dropped output diff without compare']
- [biz_122] wrong | q_fefc6fe34685 | Trong tổng dthu tháng 2/2025, phần của thuốc kê đơn là bao nhiêu phần trăm
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "dùng ngoài"}, "share_of_total": true}
  answer: 0.0 | gold: 4.76 | reason: None | fixes: []
- [biz_123] abstain | q_d70531d80ed2 | thuoc co hoat chat ibuprofen thang 12/2025 ban dc tong cong bn tien
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"product": "thuoc co hoat chat ibuprofen"}}
  answer: None | gold: 6720000 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_d775b67b6a46 | Năm nay, tính từ đầu năm đến hết hôm nay, doanh thu của cửa hàng là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "answerable": true}
  answer: None | gold: 587647900 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_e07c3a1669e0 | cuoi ngay hom nay Yumangel hop 20 goi con bao nhieu goi
  intent: {"metric": "stock", "periods": [{"type": "as_of", "date": "2025-12-10"}], "filters": {"product": "Yumangel", "size": "hop 20"}}
  answer: None | gold: 162 | reason: AttributeError: 'NoneType' object has no attribute 'drop_duplicates' | fixes: []
- [biz_123] abstain | q_e5e5818472dc | tu ngay 24/09/2025, panadol cam cum hop 15 vi x 12 vien tang gia len 1.300đ. so 14 ngay ke tu ngay 24/09/2025 vs 14 ngay ngay trc do, so vien ban ra thay doi bao nhiu phan tram
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-09-24"}], "compare": "previous", "output": "pct", "filters": {"product": "Panadol Cam Combo 15vi x 12vi"}, "params": {"days": 14}}
  answer: None | gold: -82.86 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: ["periods [{'type': 'range', 'start_date': '2025-10-08', 'end_date': '2025-10-17'}] -> [{'type': 'day', 'date': '2025-09-24'}] (date tagger)"]
- [biz_123] abstain | q_e69a268b201f | tháng 12/2025 có bao nhiu đơn có doanh thu từ 290.000 đồng trở lên hả
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"min_value": 290000, "strict": true}}
  answer: None | gold: 185 | reason: unknown filter min_value; unknown filter strict | fixes: []
- [biz_123] abstain | q_ec7f47250481 | tháng này, dthu từ khách nhóm sỉ chiếm bn % tổng doanh thu của cửa hàng
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "filters": {"customer_group": "sỉ"}, "share_of_total": true}
  answer: None | gold: 7.47 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] wrong | q_eeb3077183e1 | tong tien nhap hang thang 1/2026 la bao nhieu
  intent: {"metric": "purchase_total", "periods": [{"type": "month", "month": 1, "year": 2026}]}
  answer: None | gold: 166510800 | reason: shop has no purchase records | fixes: []
- [biz_123] abstain | q_f0ba4122749b | tong cong no khach hang chua thu den het ngay 24/08/2025 la bao nhieu
  intent: {"metric": "debt_total", "periods": [{"type": "as_of", "date": "2025-08-24"}]}
  answer: None | gold: 1240050 | reason: TypeError: argument of type 'NoneType' is not iterable | fixes: []
- [biz_123] abstain | q_fa48e43bff04 | 5 mặt hàng bán chạy nhất tháng 6/2025 là những mặt hàng nào
  intent: {"metric": "top_products", "periods": [{"type": "month", "month": 6, "year": 2025}], "params": {"k": 5}}
  answer: None | gold: ['Panadol Extra hộp 15 vỉ x 12 viên', 'Enervon hộp 10 vỉ x 10 viên', 'Panadol 500mg hộp 10 vỉ x 12 v | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_ffbb247c3151 | Tuần trước ca chiều bán được mấy đơn?
  intent: {"metric": "order_count", "periods": [{"type": "last_week"}], "filters": {"shift": "chiều"}}
  answer: None | gold: 256 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_124] wrong | q_eaf0d3e319f0 | e gia ban mot chai Siro an ngon Ich Nhi Plus chai 100ml vao ngay 09/08/2025 la bao nhieu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-08-09"}], "filters": {"product": "SP0001"}}
  answer: 1400 | gold: 65000 | reason: None | fixes: []
- [biz_124] abstain | q_eb86182b21dd | Kể từ khi Decolgen Forte hộp 30 vỉ x 4 viên lên giá 1.400 đồng/viên, 14 ngày đầu bán được nhiều hay ít hơn 14 ngày liền trước đó bao nhiêu phần trăm, tính theo số viên?
  intent: {"metric": "quantity", "periods": [{"type": "range", "start_date": "2026-05-11", "end_date": "2026-05-24"}], "filters": {"product": "SP0001", "unit": "viên"}, "compare": "previous", "output": "pct"}
  answer: None | gold: 40.23 | reason: KeyError: 'start' | fixes: []
- [biz_124] wrong | q_ee0f5dce73bd | cho hoi thang 6/2025, dthu tu khach nhom than thiet chiem bao nhiu phan tram tong doanh thu cua cua hang
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 6, "year": 2025}], "filters": {"customer_group": "than thiết"}, "share_of_total": true}
  answer: None | gold: 14.37 | reason: no customer groups | fixes: ['dropped output pct without compare']
- [biz_124] wrong | q_eef55227353d | doanh thu tet nam nay so vs tet nam truoc thay doi may phan tram ha
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "compare": "same_period_last_year", "output": "pct"}
  answer: 22.1 | gold: 23.02 | reason: None | fixes: []
- [biz_124] abstain | q_fe8f9e79f8b5 | Trừ thuốc kê đơn ra, tháng 4/2026 các mặt hàng còn lại bán đc bao nhiêu tiền
  intent: {}
  answer: None | gold: 356487300 | reason: no intent | fixes: []
- [biz_127] wrong | q_e9e0024a7378 | Cho mình 3 khách mua nhiều tiền nhất tháng 8/2025.
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 8, "year": 2025}], "params": {"k": 3}}
  answer: ['La Hương Đức', 'Từ Anh Mai', 'Tô Hương Phương'] | gold: ['Võ Hải Minh', 'Từ Anh Mai', 'Tống Hạnh Trang'] | reason: None | fixes: []
- [biz_127] wrong | q_ecad7ca9cd8b | Cho mình hỏi giá trị trung bình một đơn tháng 5/2025 là bao nhiêu?
  intent: {"metric": "avg_order_value", "periods": [{"type": "month", "month": 5, "year": 2025}]}
  answer: 470493 | gold: 512901 | reason: None | fixes: []
- [biz_127] wrong | q_ef810b14835c | Doanh thu tháng 4/2025 bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 4, "year": 2025}], "answerable": true}
  answer: 888145074 | gold: 985537000 | reason: None | fixes: []
- [biz_127] wrong | q_ef9ec0a860f8 | Tháng 6/2026 thu hồi được bao nhiêu tiền công nợ từ khách mua chịu?
  intent: {"metric": "new_debt_and_repaid", "periods": [{"type": "month", "month": 6, "year": 2026}], "filters": {"payment_method": "debt"}, "params": {"part": "new"}}
  answer: 6250500 | gold: 9792001 | reason: None | fixes: []
- [biz_127] wrong | q_f01a6c708329 | doanh thu thang 1/2026 bao nhieu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 1, "year": 2026}], "answerable": true}
  answer: 991050081 | gold: 1102424000 | reason: None | fixes: []
- [biz_127] wrong | q_f0cecf7f7696 | Trung bình mỗi đơn tháng 11/2025 mang về bao nhiêu dthu
  intent: {"metric": "avg_order_value", "periods": [{"type": "month", "month": 11, "year": 2025}]}
  answer: 471350 | gold: 521049 | reason: None | fixes: ['dropped output pct without compare']
- [biz_127] wrong | q_f4cba6071b48 | check gium thang 9/2025 dthu binh quan moi don la bn
  intent: {"metric": "avg_order_value", "periods": [{"type": "month", "month": 9, "year": 2025}]}
  answer: 487015 | gold: 541323 | reason: None | fixes: ['dropped output diff without compare']
- [biz_129] wrong | q_ea88d1f6dcfd | check gium cho toi biet dthu thang 9/2025
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}]}
  answer: 986115794 | gold: 1096349500 | reason: None | fixes: []
- [biz_129] wrong | q_f6a1f1419974 | gia ban mot phan Ngheu hap sa vao ngay 16/11/2025 la bao nhieu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-11-16"}], "filters": {"product": "Mì xào hải sản"}}
  answer: 79000 | gold: 69000 | reason: None | fixes: []
- [biz_129] wrong | q_f750d1f1110c | dthu tháng 5 năm 2026 tăng trưởng bao nhiêu % so với tháng 5 năm 2025?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2026}, {"type": "month", "month": 5, "year": 2025}], "compare": "same_period_last_year", "output": "pct"}
  answer: -11.24 | gold: -12.94 | reason: None | fixes: []
- [biz_129] wrong | q_fe67932c2f2e | coi giùm tháng 3/2025 doanh thu bình quân mỗi đơn là bao nhiu z
  intent: {"metric": "avg_order_value", "periods": [{"type": "month", "month": 3, "year": 2025}]}
  answer: 475826 | gold: 529641 | reason: None | fixes: ['dropped output diff without compare']
- [biz_129] wrong | q_ff04cc0fa5a6 | thang 2/2025 nhom chien xao ban dc bn tien
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "chiên xào"}}
  answer: 149084510 | gold: 159004500 | reason: None | fixes: []
- [biz_129] wrong | q_ff4cd475782d | Cho hỏi trong tháng 3/2025, cửa hàng có mấy đơn ở trạng thái huỷ?
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2025}], "filters": {"status": "cancelled"}}
  answer: 0 | gold: 50 | reason: None | fixes: []
- [biz_130] wrong | q_e9a29330a629 | ê tháng 4/2026 nhóm hải sản chiếm bnhiu % dthu vậy
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 4, "year": 2026}], "filters": {"group": "hải sản"}, "share_of_total": true}
  answer: 0.0 | gold: 8.41 | reason: None | fixes: ['dropped output pct without compare']
- [biz_130] abstain | q_f1d3c9b81e5f | tháng 9/2025 có mấy đơn có doanh thu từ 430.000 đồng trở lên
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"min_value": 430000, "strict": true}}
  answer: None | gold: 1215 | reason: unknown filter min_value; unknown filter strict | fixes: []
- [biz_130] wrong | q_f7b8eb9ecf98 | dthu thangs 7/2026 hơn hay kém th trước bao nhiu % ta
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2026}], "compare": "previous", "output": "pct"}
  answer: 6.09 | gold: 6.98 | reason: None | fixes: []
- [biz_130] wrong | q_ffcc4f2ebca1 | tháng 3/2026 ngày nào cửa hàng bán được nhìu tiền nhất
  intent: {"metric": "best_day", "periods": [{"type": "month", "month": 3, "year": 2026}]}
  answer: 2026-03-31 | gold: 2026-03-09 | reason: None | fixes: []