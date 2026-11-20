# Run 20261114-0313

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_v5 (30 shop): đúng 236 sai 52 bỏ trống 12 → 184  ← chi tiết bên dưới
- results_v5_sql (30 shop): đúng 236 sai 53 bỏ trống 11 → 183

## results_v5 theo shop

- biz_101: đúng 10 sai 0 bỏ trống 0 → 10
- biz_102: đúng 8 sai 2 bỏ trống 0 → 6
- biz_103: đúng 9 sai 1 bỏ trống 0 → 8
- biz_104: đúng 10 sai 0 bỏ trống 0 → 10
- biz_105: đúng 9 sai 1 bỏ trống 0 → 8
- biz_106: đúng 10 sai 0 bỏ trống 0 → 10
- biz_107: đúng 10 sai 0 bỏ trống 0 → 10
- biz_108: đúng 9 sai 1 bỏ trống 0 → 8
- biz_109: đúng 9 sai 1 bỏ trống 0 → 8
- biz_110: đúng 9 sai 1 bỏ trống 0 → 8
- biz_111: đúng 7 sai 3 bỏ trống 0 → 4
- biz_112: đúng 6 sai 3 bỏ trống 1 → 3
- biz_113: đúng 9 sai 1 bỏ trống 0 → 8
- biz_114: đúng 8 sai 2 bỏ trống 0 → 6
- biz_115: đúng 9 sai 1 bỏ trống 0 → 8
- biz_116: đúng 9 sai 1 bỏ trống 0 → 8
- biz_117: đúng 7 sai 3 bỏ trống 0 → 4
- biz_118: đúng 5 sai 5 bỏ trống 0 → 0
- biz_119: đúng 9 sai 1 bỏ trống 0 → 8
- biz_120: đúng 7 sai 3 bỏ trống 0 → 4
- biz_121: đúng 6 sai 4 bỏ trống 0 → 2
- biz_122: đúng 4 sai 6 bỏ trống 0 → -2
- biz_123: đúng 0 sai 1 bỏ trống 9 → -1
- biz_124: đúng 4 sai 4 bỏ trống 2 → 0
- biz_125: đúng 10 sai 0 bỏ trống 0 → 10
- biz_126: đúng 9 sai 1 bỏ trống 0 → 8
- biz_127: đúng 10 sai 0 bỏ trống 0 → 10
- biz_128: đúng 8 sai 2 bỏ trống 0 → 6
- biz_129: đúng 8 sai 2 bỏ trống 0 → 6
- biz_130: đúng 8 sai 2 bỏ trống 0 → 6

**Tổng results_v5: đúng 236 sai 52 bỏ trống 12 → 184**

## Theo metric

- revenue: {'correct': 100, 'wrong': 24, 'abstain': 3}
- quantity: {'correct': 28, 'wrong': 7, 'abstain': 2}
- unit_price: {'correct': 7, 'wrong': 5}
- order_count: {'correct': 16, 'wrong': 2, 'abstain': 2}
- stock: {'wrong': 3, 'abstain': 1}
- top_customers: {'wrong': 3, 'correct': 3}
- price_effect: {'wrong': 1, 'abstain': 1}
- cancelled_count: {'correct': 5, 'wrong': 2}
- customers_min_orders: {'wrong': 2}
- top_products: {'correct': 5, 'abstain': 1}
- debt_total: {'correct': 3, 'abstain': 1}
- avg_purchase_price: {'correct': 2, 'wrong': 1}
- new_debt_and_repaid: {'correct': 3, 'wrong': 1}
- None: {'correct': 1, 'abstain': 1}
- purchase_total: {'correct': 1, 'wrong': 1}
- best_day: {'correct': 16}
- avg_order_value: {'correct': 18}
- cancel_rate: {'correct': 18}
- unsold_products: {'correct': 3}
- debt_table: {'correct': 2}
- products_min_orders: {'correct': 1}
- debtor_count: {'correct': 2}
- customer_count: {'correct': 2}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 184 (236✓ 52✗ 12–) | 193 (223✓ 30✗ 47–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 183 (236✓ 53✗ 11–) | 192 (223✓ 31✗ 46–) | 192 (224✓ 32✗ 44–) | · | · | · | · |


## Câu sai / bỏ trống

- [biz_102] wrong | q_d55269aa2f36 | cho hỏi top 3 khách mua nhiều tieenf nhaats tháng 12/2025 là ai
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"k": 3}}
  answer: ['kl', 'Trương Dương Hằng', 'Trịnh Khoa An'] | gold: ['Trương Dương Hằng', 'Trịnh Khoa An', 'Cao Loan Hiếu'] | reason: None | fixes: ['dropped output argmax with one period']
- [biz_102] wrong | q_f14c7c3cd8ad | 3 khach co tong tien mua cao nhat thang 4/2025 la ai ha
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 4, "year": 2025}], "params": {"k": 3, "by": "revenue"}}
  answer: ['kl', 'Giang Hải Linh', 'Quách An Ngân'] | gold: ['Giang Hải Linh', 'Quách An Ngân', 'Trịnh Khoa An'] | reason: None | fixes: []
- [biz_103] wrong | q_e69dcf0740d1 | check gium so so goi snack lay's vi tu nhien 56g ban ra trong 30 ngay ke tu ngay 18/12/2025, ngay tang gia len 13.500đ, vs 30 ngay ngay truoc ngay do: tang hay giam bao nhieu %
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-12-18"}], "filters": {"product": "Snack Lay's vị tự nhiên 56g"}, "params": {"days": 30, "new_price": 13500, "date": "2025-12-18"}, "compare": "previous", "output": "pct", "answerable": true}
  answer: 0.0 | gold: 26.39 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2025-12-18', 'end_date': '2026-01-17'}] -> [{'type': 'day', 'date': '2025-12-18'}] (date tagger)", 'price_effect date from periods']
- [biz_105] wrong | q_f321dd447d00 | cho hoir giá bán một ly cà phê sữa (l) vào ngày 10/06/2025 laf bnhiu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-06-10"}], "filters": {"product": "Cà phê sữa (L)"}, "params": {"unit": "ly"}}
  answer: None | gold: 35000 | reason: intent marked unanswerable | fixes: []
- [biz_108] wrong | q_f1bfb1c1ea00 | trong tong dthu thang 12/2025, doanh thu cac don ban qua Zalo OA chiem bn phan tram
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"payment_method": "Zalo OA"}, "share_of_total": true, "answerable": true}
  answer: None | gold: 4.23 | reason: no payment method column | fixes: []
- [biz_109] wrong | q_f519b57113e1 | check giumf dthu tết năm nay so vs tết năm trc thay đổi mấy phần trăm
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "compare": "same_period_last_year", "output": "pct", "answerable": true}
  answer: -10.31 | gold: -26.22 | reason: None | fixes: ["periods [{'type': 'tet', 'year': 2026}] -> [{'type': 'year_to_date'}] (date tagger)"]
- [biz_110] wrong | q_f19c4e273491 | quý 4/2025 cuwar hàng có bn order ddos
  intent: {"metric": "order_count", "periods": [{"type": "quarter", "quarter": 4, "year": 2025}], "filters": {"product": "cua hang"}, "params": {"min_value": 0}}
  answer: None | gold: 6236 | reason: intent marked unanswerable | fixes: []
- [biz_111] wrong | q_f0859c5b2adb | Tháng 8/2025 cửa hàng thu được bao nhiêu tiền khách trả nợ?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"payment_method": "debt"}, "answerable": true}
  answer: 2306000 | gold: 1476503 | reason: None | fixes: []
- [biz_111] wrong | q_f0adbb2db8ff | Tháng 7/2025 quán bán ra tổng cộng mấy ly size M, cộng tất cả các món ạ?
  intent: {"metric": "quantity", "periods": [{"type": "month", "month": 7, "year": 2025}], "filters": {"size": "M"}, "share_of_total": true, "answerable": true}
  answer: 57.9 | gold: 3584 | reason: None | fixes: []
- [biz_111] wrong | q_fee5b1d42b55 | thang 7/2026, dthu cac don tra bang tm chiem bao nhieu phan tram tong doanh thu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2026}], "filters": {"payment_method": "transfer"}, "share_of_total": true, "answerable": true}
  answer: 34.56 | gold: 40.3 | reason: None | fixes: []
- [biz_112] wrong | q_ee530fc682e1 | dthu nhóm hàng bánh chiếm bao nhiêu phần trăm tổng doanh thu tháng 2 năm 2026?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"group": "bánh"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 3.23 | reason: None | fixes: []
- [biz_112] wrong | q_f3d30bcd1487 | So số ly Sinh tố xoài (L) bán ra trong 30 ngày kể từ ngày 04/09/2025, ngày tăng giá lên 50.500đ, với 30 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu % nhỉ?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-09-04"}], "compare": "explicit", "output": "pct", "filters": {"product": "Sinh tố xoài (L)"}, "params": {"new_price": 50500}, "answerable": true}
  answer: None | gold: 7.04 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2025-09-04', 'end_date': '2025-09-04', 'days': 30}, {'type': 'range', 'start_date': '2025-08-06', 'end_date': '2025-09-03', 'days': 30}] -> [{'type': 'day', 'date': '2025-09-04'}] (date tagger)"]
- [biz_112] wrong | q_f42871042dc7 | thang 9/2025 nhom banh chiem bn % dthu z
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"group": "bánh"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 3.63 | reason: None | fixes: []
- [biz_112] abstain | q_fe680ecf01d9 | ngay 10/09/2025 soda chanh day (m) tang gia tu 35.000đ len 37.000đ. so ly ban duoc trong 14 ngay ke tu ngay do so vs 14 ngay truoc do thay doi bao nhieu %
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-09-10"}], "params": {"days": 14, "new_price": 37000, "product": "Soda chanh dây (M)", "date": "2025-09-10"}, "compare": "previous", "output": "pct"}
  answer: None | gold: -29.73 | reason: unknown product None | fixes: ['price_effect date from periods']
- [biz_113] wrong | q_e24f4eb5442a | Doanh thu hôm qua của cửa hàng là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "yesterday"}], "answerable": true}
  answer: 42473400 | gold: 45552900 | reason: None | fixes: []
- [biz_114] wrong | q_d5e6651d3fb6 | Cho hỏi hôm 02/07/2025, Gạch thẻ đặc 4x8x18 bán ra với đơn giá bao nhiêu tiền một viên?
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-07-02"}], "filters": {"product": "Gạch thẻ đặc 4x8x18"}, "params": {"unit": "viên"}}
  answer: None | gold: 1600 | reason: intent marked unanswerable | fixes: []
- [biz_114] wrong | q_f7b5101e0899 | cho hỏi dthu tháng 7/2025 bao nhiêu đó
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2025}]}
  answer: None | gold: 974738600 | reason: intent marked unanswerable | fixes: []
- [biz_115] wrong | q_ed929e98cc18 | tháng 1/2026 ai mua hàng nhìu tiền nhất
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 1, "year": 2026}], "params": {"by": "revenue"}}
  answer: kl | gold: Vương Phúc Dương | reason: None | fixes: []
- [biz_116] wrong | q_fcdacd705ef0 | thang 12/2025 nhom hoan thien chiem bnhiu % dthu z
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"group": "hoàn thiện"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 3.45 | reason: None | fixes: []
- [biz_117] wrong | q_f06ff238b76c | gia ban mot m3 Cat san lap vao ngay 21/06/2025 la bao nhieu z
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-06-21"}], "filters": {"product": "Cát san lấp"}, "params": {"unit": "m3"}}
  answer: None | gold: 240000 | reason: intent marked unanswerable | fixes: []
- [biz_117] wrong | q_f3d26f111d55 | xem giúp tuần rồi, số ddown ca chiều tăng hay giảm bao nhiu % so vs ca sáng
  intent: {"metric": "revenue", "periods": [{"type": "last_week"}], "output": "pct", "shift_compare": true, "answerable": true}
  answer: -60.16 | gold: -55.17 | reason: None | fixes: ['shift_compare: dropped period compare / shift filter']
- [biz_117] wrong | q_fb33573520e0 | doanh thu cua son dulux weathershield powerflexx 5L trong thang 8 nam 2025 la bn
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"product": "Sơn Dulux Weathershield Powerflexx 5L"}}
  answer: None | gold: 80600000 | reason: intent marked unanswerable | fixes: []
- [biz_118] wrong | q_ec5c0d7eed96 | thang 3/2026 co bnhiu don bi huy vi giao tre
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2026}], "filters": {"status": "cancelled"}, "answerable": true}
  answer: 0 | gold: UNANSWERABLE | reason: None | fixes: []
- [biz_118] wrong | q_ed21efdd6942 | bn khách mua ít nhất 3 đơn trong tháng 12 năm 2025 vậy
  intent: {"metric": "customers_min_orders", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"threshold": 3}, "answerable": true}
  answer: 118 | gold: 117 | reason: None | fixes: []
- [biz_118] wrong | q_ed3ef76aa90c | dthu nhóm hàng cát đá tháng 7 năm 2026 là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2026}], "filters": {"group": "cát đá"}, "answerable": true}
  answer: 0 | gold: 188137000 | reason: None | fixes: []
- [biz_118] wrong | q_f2fa231f8444 | Trong số khách có mua tháng 1 năm 2026, tỉ lệ khách mua ít nhất 4 đơn là bao nhiêu %?
  intent: {"metric": "customers_min_orders", "periods": [{"type": "month", "month": 1, "year": 2026}], "params": {"threshold": 4, "as_percent": true}, "share_of_total": true, "answerable": true}
  answer: 100.0 | gold: 27.75 | reason: None | fixes: []
- [biz_118] wrong | q_fdca3d13b254 | tháng 2/2025 nhóm điện chiếm bnhiu % doanh thu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "điện"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 25.99 | reason: None | fixes: []
- [biz_119] wrong | q_ef1a03f3f07b | thuoc co hoat chat loratadin thang nay ban duoc tong cong bao nhieu tien ta
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "filters": {"product": "Telfast HD 180mg hộp 3 vỉ x 10 viên"}, "answerable": true}
  answer: 1299400 | gold: 812300 | reason: None | fixes: ["periods [{'type': 'month', 'month': 7, 'year': 2026}] -> [{'type': 'this_month'}] (date tagger)", "periods [{'type': 'month', 'month': 7, 'year': 2026}] -> [{'type': 'this_month'}] (date tagger)"]
- [biz_120] wrong | q_f448394fcfee | thang 9/2025, dthu cac don ban qua dien thoai la bao nhieu, doanh thu cac don ban qua zalo oa la bao nhieu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"payment_method": "zalo oa"}}
  answer: None | gold: [13759000, 16074900] | reason: intent marked unanswerable | fixes: ['dropped output diff without compare']
- [biz_120] wrong | q_f963fc3db789 | ton kho Otrivin 0,1% xit mui chai 10ml cuoi ngay hom nay la bao nhieu chai vay
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Otrivin 0,1% xịt mũi chai 10ml"}, "params": {"split_big_unit": false}, "answerable": true}
  answer: 2278 | gold: 150 | reason: None | fixes: []
- [biz_120] wrong | q_fdc6c8321774 | ton kho gofen 400 hop 5 vi x 10 vien nang cuoi ngay hom nay la bao nhieu vien
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Gofen 400 hộp 5 vỉ x 10 viên nang"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: [236, 0] | gold: 75 | reason: None | fixes: []
- [biz_121] wrong | q_e6dd8fd4a42a | ê pharmaton essential hộp 30 viên lên giá 231.500đ từ ngày 20/05/2025; so 30 ngày kể từ ngày tăng giá với 30 ngày ngay trc, lượng bán tính theo hộp tăng hay giảm bao nhiu %
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-05-20"}], "compare": "previous", "output": "pct", "filters": {"product": "Pharmaton Essential hộp 30 viên"}, "params": {"days": 30}, "answerable": true}
  answer: None | gold: 13.95 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2025-05-20', 'end_date': '2025-06-18'}, {'type': 'range', 'start_date': '2025-04-21', 'end_date': '2025-05-19'}] -> [{'type': 'day', 'date': '2025-05-20'}] (date tagger)", 'compare same_period_last_year -> previous']
- [biz_121] wrong | q_ec33e9c57c6e | thang 2/2026 dthu hang hok ke don la bn do
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"product": "Hoka", "exclude_cancelled": true}}
  answer: None | gold: 242427700 | reason: intent marked unanswerable | fixes: []
- [biz_121] wrong | q_f26d33760e59 | So số viên UPSA-C 1g viên sủi tuýp 10 viên bán ra trong 14 ngày kể từ ngày 22/03/2026, ngày tăng giá lên 3.900đ, với 14 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu %?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2026-03-22"}], "compare": "previous", "output": "diff", "filters": {"product": "UPSA-C 1g viên sủi tuýp 10 viên"}, "params": {"days": 14, "new_price": 3900}, "answerable": true}
  answer: 2 | gold: -0.64 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2026-03-09', 'end_date': '2026-03-22'}, {'type': 'range', 'start_date': '2026-03-22', 'end_date': '2026-04-05'}] -> [{'type': 'day', 'date': '2026-03-22'}] (date tagger)", 'compare same_period_last_year -> previous']
- [biz_121] wrong | q_ffcb6868973c | Strepsils Cool hop 2 vi x 12 vien doi gia tu 1.600đ len 1.700đ vao ngay 24/07/2026. 7 ngay ke tu ngay do ban duoc nhiu hay it hon 7 ngay lien trc bao nhiu %, tinh theo vien
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2026-07-24"}], "compare": "previous", "output": "pct", "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"days": 7}, "answerable": true}
  answer: None | gold: 149.43 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2026-07-24', 'end_date': '2026-07-30'}] -> [{'type': 'day', 'date': '2026-07-24'}] (date tagger)"]
- [biz_122] wrong | q_f87f57532f37 | Cho mình hỏi so số tuýp Plusssz Max Multivitamin viên sủi tuýp 20 viên bán ra trong 30 ngày kể từ ngày 29/10/2025, ngày tăng giá lên 42.000đ, với 30 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu %?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-10-29"}], "compare": "explicit", "output": "pct", "filters": {"product": "Plusssz Max Multivitamin viên sủi tuýp 20 viên"}, "params": {"new_price": 42000}, "answerable": true}
  answer: None | gold: -2.3 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2025-10-29', 'end_date': '2025-11-28'}, {'type': 'range', 'start_date': '2025-10-28', 'end_date': '2025-11-27'}] -> [{'type': 'day', 'date': '2025-10-29'}] (date tagger)"]
- [biz_122] wrong | q_f95fc735e3bc | So số viên Strepsils Cool hộp 2 vỉ x 12 viên bán ra trong 30 ngày kể từ ngày 05/03/2026, ngày tăng giá lên 1.800đ, với 30 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu %?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2026-03-05"}], "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"days": 30, "new_price": 1800}, "compare": "previous", "output": "pct", "answerable": true}
  answer: -94.05 | gold: -36.41 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2026-03-05', 'end_date': '2026-03-31'}, {'type': 'range', 'start_date': '2026-02-25', 'end_date': '2026-03-04'}] -> [{'type': 'day', 'date': '2026-03-05'}] (date tagger)", 'compare same_period_last_year -> previous']
- [biz_122] wrong | q_fbb2dfbdae61 | thuốc có hoạt chất vitamin c tháng 10/2025 bán được tổng cộng bao nhiêu tiền
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 10, "year": 2025}], "filters": {"product": "Vitamin C 500mg Quapharco hộp 10 vỉ x 10 viên"}, "answerable": true}
  answer: 431500 | gold: 2281500 | reason: None | fixes: []
- [biz_122] wrong | q_fe14e521d3e0 | ton kho strepsils cool hop 2 vi x 12 vien cuoi ngay hom nay dc may hop chan va may vien le
  intent: {"metric": "stock", "periods": [{"type": "today", "as_of_date": "2026-07-17"}], "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: None | gold: [8, 9] | reason: no stock report | fixes: []
- [biz_122] wrong | q_fe7efca0973e | Trừ thuốc kê đơn ra, tháng 2/2026 các mặt hàng còn lại bán được bao nhiêu tiền?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"payment_method": "cash", "shift": "day"}, "answerable": true}
  answer: None | gold: 238810400 | reason: no payment method column | fixes: []
- [biz_122] wrong | q_fefc6fe34685 | Trong tổng dthu tháng 2/2025, phần của thuốc kê đơn là bao nhiêu phần trăm
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "kháng sinh"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 4.76 | reason: None | fixes: []
- [biz_123] abstain | q_d70531d80ed2 | thuoc co hoat chat ibuprofen thang 12/2025 ban dc tong cong bn tien
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"product": "thuoc co hoat chat ibuprofen"}, "answerable": true}
  answer: None | gold: 6720000 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_d775b67b6a46 | Năm nay, tính từ đầu năm đến hết hôm nay, doanh thu của cửa hàng là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "answerable": true}
  answer: None | gold: 587647900 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_e07c3a1669e0 | cuoi ngay hom nay Yumangel hop 20 goi con bao nhieu goi
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Yumangel hop 20 goi"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: None | gold: 162 | reason: AttributeError: 'NoneType' object has no attribute 'drop_duplicates' | fixes: []
- [biz_123] abstain | q_e5e5818472dc | tu ngay 24/09/2025, panadol cam cum hop 15 vi x 12 vien tang gia len 1.300đ. so 14 ngay ke tu ngay 24/09/2025 vs 14 ngay ngay trc do, so vien ban ra thay doi bao nhiu phan tram
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-09-24"}], "filters": {"product": "Panadol cam cốm hộp 15 vỉ x 12 viên"}, "compare": "explicit", "output": "pct", "params": {"days": 14}, "answerable": true}
  answer: None | gold: -82.86 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: ["periods [{'type': 'range', 'start_date': '2025-09-24', 'end_date': '2025-10-07'}, {'type': 'range', 'start_date': '2025-09-10', 'end_date': '2025-09-23'}] -> [{'type': 'day', 'date': '2025-09-24'}] (date tagger)"]
- [biz_123] abstain | q_e69a268b201f | tháng 12/2025 có bao nhiu đơn có doanh thu từ 290.000 đồng trở lên hả
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"min_value": 290000}, "answerable": true}
  answer: None | gold: 185 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_ec7f47250481 | tháng này, dthu từ khách nhóm sỉ chiếm bn % tổng doanh thu của cửa hàng
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "filters": {"customer_group": "sỉ"}, "share_of_total": true, "answerable": true}
  answer: None | gold: 7.47 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] wrong | q_eeb3077183e1 | tong tien nhap hang thang 1/2026 la bao nhieu
  intent: {"metric": "purchase_total", "periods": [{"type": "month", "month": 1, "year": 2026}]}
  answer: None | gold: 166510800 | reason: shop has no purchase records | fixes: []
- [biz_123] abstain | q_f0ba4122749b | tong cong no khach hang chua thu den het ngay 24/08/2025 la bao nhieu
  intent: {"metric": "debt_total", "periods": [{"type": "as_of", "date": "2025-08-24"}], "params": {"min_age": 0}, "answerable": true}
  answer: None | gold: 1240050 | reason: TypeError: argument of type 'NoneType' is not iterable | fixes: []
- [biz_123] abstain | q_fa48e43bff04 | 5 mặt hàng bán chạy nhất tháng 6/2025 là những mặt hàng nào
  intent: {"metric": "top_products", "periods": [{"type": "month", "month": 6, "year": 2025}], "params": {"k": 5, "by": "qty"}}
  answer: None | gold: ['Panadol Extra hộp 15 vỉ x 12 viên', 'Enervon hộp 10 vỉ x 10 viên', 'Panadol 500mg hộp 10 vỉ x 12 v | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_123] abstain | q_ffbb247c3151 | Tuần trước ca chiều bán được mấy đơn?
  intent: {"metric": "order_count", "periods": [{"type": "last_week"}], "filters": {"shift": "chiều"}}
  answer: None | gold: 256 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: []
- [biz_124] wrong | q_eaf0d3e319f0 | e gia ban mot chai Siro an ngon Ich Nhi Plus chai 100ml vao ngay 09/08/2025 la bao nhieu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-08-09"}], "filters": {"product": "Siro an ngon Ich Nhi Plus chai 100ml"}, "params": {"unit": "chai"}}
  answer: None | gold: 65000 | reason: intent marked unanswerable | fixes: []
- [biz_124] abstain | q_eb86182b21dd | Kể từ khi Decolgen Forte hộp 30 vỉ x 4 viên lên giá 1.400 đồng/viên, 14 ngày đầu bán được nhiều hay ít hơn 14 ngày liền trước đó bao nhiêu phần trăm, tính theo số viên?
  intent: {"metric": "quantity", "periods": [{"type": "range", "start_date": "2026-05-11", "end_date": "2026-05-24"}], "compare": "previous", "output": "pct", "filters": {"product": "SP0001"}, "params": {"days": 14}, "answerable": true}
  answer: None | gold: 40.23 | reason: KeyError: 'start' | fixes: []
- [biz_124] wrong | q_ee0f5dce73bd | cho hoi thang 6/2025, dthu tu khach nhom than thiet chiem bao nhiu phan tram tong doanh thu cua cua hang
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 6, "year": 2025}], "filters": {"customer_group": "thanh thiet"}, "share_of_total": true, "answerable": true}
  answer: None | gold: 14.37 | reason: no customer groups | fixes: []
- [biz_124] wrong | q_eef55227353d | doanh thu tet nam nay so vs tet nam truoc thay doi may phan tram ha
  intent: {"metric": "revenue", "periods": [{"type": "year_to_date"}], "compare": "same_period_last_year", "output": "pct", "answerable": true}
  answer: 22.1 | gold: 23.02 | reason: None | fixes: ["periods [{'type': 'tet', 'year': 2026}] -> [{'type': 'year_to_date'}] (date tagger)"]
- [biz_124] wrong | q_f9c1c1549f63 | trong tháng này, khách huỳnh nhung đức mua chịu thêm nhiêu và trả bớt nợ đc bao nhieeu? trả lời hai số: nợ thêm, trả được
  intent: {"metric": "new_debt_and_repaid", "periods": [{"type": "this_month"}], "filters": {"customer": "Huỳnh Nhung Đức"}, "params": {"part": "new"}, "answerable": true}
  answer: 530000 | gold: [530000, 530000] | reason: None | fixes: []
- [biz_124] abstain | q_fe8f9e79f8b5 | Trừ thuốc kê đơn ra, tháng 4/2026 các mặt hàng còn lại bán đc bao nhiêu tiền
  intent: {}
  answer: None | gold: 356487300 | reason: no intent | fixes: []
- [biz_126] wrong | q_eff8c82894a7 | Tổng doanh thu tháng 7 năm 2025 là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 7, "year": 2025}]}
  answer: None | gold: 566827500 | reason: intent marked unanswerable | fixes: []
- [biz_128] wrong | q_f2f2c2bbf231 | Giá bán một đĩa Trứng chiên thịt bằm vào ngày 10/10/2025 là bao nhiêu?
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-10-10"}], "filters": {"product": "Trứng chiên thịt bằm"}, "params": {"unit": "đĩa"}}
  answer: None | gold: 45000 | reason: intent marked unanswerable | fixes: []
- [biz_128] wrong | q_f512a1665ff9 | Xem giúp trong tháng 4/2025, Bia Heineken lon nhập vào giá bình quân một thùng là bao nhiêu?
  intent: {"metric": "avg_purchase_price", "periods": [{"type": "month", "month": 4, "year": 2025}], "filters": {"product": "Bia Heineken lon"}, "params": {"unit": "thùng"}}
  answer: None | gold: 496800 | reason: intent marked unanswerable | fixes: []
- [biz_129] wrong | q_ebfba62ad2d4 | cua hang ban dc bao nhieu don trong quy 3 nam 2025
  intent: {"metric": "order_count", "periods": [{"type": "quarter", "quarter": 3, "year": 2025}], "filters": {"customer": "cua hang"}}
  answer: None | gold: 6178 | reason: intent marked unanswerable | fixes: []
- [biz_129] wrong | q_ff4cd475782d | Cho hỏi trong tháng 3/2025, cửa hàng có mấy đơn ở trạng thái huỷ?
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2025}], "filters": {"status": "cancelled"}, "answerable": true}
  answer: 0 | gold: 50 | reason: None | fixes: []
- [biz_130] wrong | q_e9a29330a629 | ê tháng 4/2026 nhóm hải sản chiếm bnhiu % dthu vậy
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 4, "year": 2026}], "filters": {"group": "hải sản"}, "share_of_total": true, "answerable": true}
  answer: 0.0 | gold: 8.41 | reason: None | fixes: []
- [biz_130] wrong | q_ffd121a26711 | thang 8/2025 ban Cha ca chien dc bao nhieu tien
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"product": "Chả cá chiên"}}
  answer: None | gold: 5717000 | reason: intent marked unanswerable | fixes: []