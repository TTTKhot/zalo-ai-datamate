# Run 20261114-0608

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_v5 (30 shop): đúng 261 sai 24 bỏ trống 15 → 237  ← chi tiết bên dưới
- results_v5_sql (30 shop): đúng 263 sai 26 bỏ trống 11 → 237

## results_v5 theo shop

- biz_101: đúng 9 sai 1 bỏ trống 0 → 8
- biz_102: đúng 10 sai 0 bỏ trống 0 → 10
- biz_103: đúng 8 sai 2 bỏ trống 0 → 6
- biz_104: đúng 9 sai 1 bỏ trống 0 → 8
- biz_105: đúng 10 sai 0 bỏ trống 0 → 10
- biz_106: đúng 9 sai 1 bỏ trống 0 → 8
- biz_107: đúng 9 sai 0 bỏ trống 1 → 9
- biz_108: đúng 10 sai 0 bỏ trống 0 → 10
- biz_109: đúng 9 sai 1 bỏ trống 0 → 8
- biz_110: đúng 9 sai 1 bỏ trống 0 → 8
- biz_111: đúng 9 sai 1 bỏ trống 0 → 8
- biz_112: đúng 8 sai 2 bỏ trống 0 → 6
- biz_113: đúng 9 sai 1 bỏ trống 0 → 8
- biz_114: đúng 10 sai 0 bỏ trống 0 → 10
- biz_115: đúng 10 sai 0 bỏ trống 0 → 10
- biz_116: đúng 10 sai 0 bỏ trống 0 → 10
- biz_117: đúng 8 sai 0 bỏ trống 2 → 8
- biz_118: đúng 9 sai 1 bỏ trống 0 → 8
- biz_119: đúng 10 sai 0 bỏ trống 0 → 10
- biz_120: đúng 8 sai 2 bỏ trống 0 → 6
- biz_121: đúng 8 sai 2 bỏ trống 0 → 6
- biz_122: đúng 8 sai 1 bỏ trống 1 → 7
- biz_123: đúng 0 sai 1 bỏ trống 9 → -1
- biz_124: đúng 5 sai 3 bỏ trống 2 → 2
- biz_125: đúng 10 sai 0 bỏ trống 0 → 10
- biz_126: đúng 10 sai 0 bỏ trống 0 → 10
- biz_127: đúng 9 sai 1 bỏ trống 0 → 8
- biz_128: đúng 10 sai 0 bỏ trống 0 → 10
- biz_129: đúng 8 sai 2 bỏ trống 0 → 6
- biz_130: đúng 10 sai 0 bỏ trống 0 → 10

**Tổng results_v5: đúng 261 sai 24 bỏ trống 15 → 237**

## Theo metric

- revenue: {'wrong': 8, 'correct': 116, 'abstain': 4}
- quantity: {'correct': 28, 'wrong': 3, 'abstain': 2}
- order_count: {'correct': 16, 'wrong': 2, 'abstain': 3}
- unit_price: {'correct': 10, 'wrong': 2}
- price_effect: {'wrong': 2, 'correct': 3}
- debt_total: {'correct': 3, 'wrong': 1, 'abstain': 1}
- cancelled_count: {'correct': 5, 'wrong': 2}
- None: {'abstain': 2}
- stock: {'correct': 2, 'wrong': 1, 'abstain': 1}
- top_products: {'correct': 5, 'abstain': 1}
- unsold_products: {'wrong': 1, 'correct': 2}
- purchase_total: {'correct': 1, 'wrong': 1}
- customer_count: {'abstain': 1}
- new_debt_and_repaid: {'correct': 1, 'wrong': 1}
- best_day: {'correct': 17}
- top_customers: {'correct': 6}
- avg_order_value: {'correct': 18}
- cancel_rate: {'correct': 18}
- avg_purchase_price: {'correct': 3}
- debt_table: {'correct': 2}
- products_min_orders: {'correct': 1}
- debtor_count: {'correct': 2}
- customers_min_orders: {'correct': 2}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 237 (261✓ 24✗ 15–) | 237 (261✓ 24✗ 15–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 237 (263✓ 26✗ 11–) | 237 (263✓ 26✗ 11–) | 237 (263✓ 26✗ 11–) | · | · | · | · |


## Câu sai / bỏ trống

- [biz_101] wrong | q_eccd1eb5d9ff | cho tôi bieets dthu tháng 5/2026
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2026}], "filters": {"product": "Bia Heineken 330ml"}}
  answer: 4510000 | gold: 236600600 | reason: None | fixes: ['dropped output diff without compare']
- [biz_103] wrong | q_e079351d24aa | dem giup toi so mon ban cham den muc trong 7 ngay gan nhat khong ban dc lan nao
  intent: {"metric": "unsold_products", "periods": [{"type": "last_n_days", "n": 7}], "filters": {"product": "món bán chậm"}, "params": {"threshold": 0}}
  answer: None | gold: 1 | reason: intent marked unanswerable | fixes: ['dropped output diff without compare', 'dropped output diff without compare']
- [biz_103] wrong | q_e69dcf0740d1 | check gium so so goi snack lay's vi tu nhien 56g ban ra trong 30 ngay ke tu ngay 18/12/2025, ngay tang gia len 13.500đ, vs 30 ngay ngay truoc ngay do: tang hay giam bao nhieu %
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-12-18"}], "filters": {"product": "Snack Lay's vị tự nhiên 56g"}, "params": {"days": 30, "new_price": 13500, "date": "2025-11-19"}, "answerable": true}
  answer: -50.33 | gold: 26.39 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2025-12-18', 'end_date': '2026-01-17'}] -> [{'type': 'day', 'date': '2025-12-18'}] (date tagger)", 'price_effect date from periods', 'dropped output pct without compare']
- [biz_104] wrong | q_f0a9c2c89441 | tháng 2/2026 bán ra nhiêu phần topping thạch cà phê
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"product": "Topping Thạch cà phê"}, "share_of_total": true}
  answer: 0.3 | gold: 58 | reason: None | fixes: []
- [biz_106] wrong | q_f24714cccf9d | trong tháng 5/2025, tiền khách trả bớt nợ các đơn mua chịu được bao nhiêu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2025}], "filters": {"payment_method": "Ghi nợ"}}
  answer: 3463000 | gold: 2842173 | reason: None | fixes: ['dropped output diff without compare']
- [biz_107] abstain | q_c1c2d4383a19 | hôm nay cuwar hangf bán đươc bao nhiu tiền z
  intent: {"metric": "revenue", "periods": [{"type": "today"}], "filters": {"product": "Cua hàng bán được"}, "answerable": true}
  answer: None | gold: 4152200 | reason: product 'Cua hàng bán được' not in shop data | fixes: ['dropped compare previous (no comparison words)', 'dropped compare previous (no comparison words)']
- [biz_109] wrong | q_fbef1e31ad7a | e thang 8/2025 khach tra no cho cac don da mua chiu total bao nhieu tien
  intent: {"metric": "debt_total", "periods": [{"type": "month", "month": 8, "year": 2025}], "params": {"min_age": null}}
  answer: 18147933 | gold: 23368734 | reason: None | fixes: []
- [biz_110] wrong | q_f19c4e273491 | quý 4/2025 cuwar hàng có bn order ddos
  intent: {"metric": "order_count", "periods": [{"type": "quarter", "quarter": 4, "year": 2025}], "filters": {"status": "ddos"}}
  answer: 0 | gold: 6236 | reason: None | fixes: []
- [biz_111] wrong | q_f0859c5b2adb | Tháng 8/2025 cửa hàng thu được bao nhiêu tiền khách trả nợ?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"payment_method": "debt"}}
  answer: 2306000 | gold: 1476503 | reason: None | fixes: []
- [biz_112] wrong | q_f3d30bcd1487 | So số ly Sinh tố xoài (L) bán ra trong 30 ngày kể từ ngày 04/09/2025, ngày tăng giá lên 50.500đ, với 30 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu % nhỉ?
  intent: {"metric": "price_effect", "periods": [{"type": "day", "date": "2025-09-04"}], "filters": {"product": "Sinh tố xoài (L)"}, "params": {"date": "2025-09-04"}}
  answer: 87.5 | gold: 7.04 | reason: None | fixes: ["periods [{'type': 'range', 'days': 30, 'date': '2025-09-04'}] -> [{'type': 'day', 'date': '2025-09-04'}] (date tagger)", 'price_effect date from periods', 'dropped output pct without compare']
- [biz_112] wrong | q_fe680ecf01d9 | ngay 10/09/2025 soda chanh day (m) tang gia tu 35.000đ len 37.000đ. so ly ban duoc trong 14 ngay ke tu ngay do so vs 14 ngay truoc do thay doi bao nhieu %
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-09-10"}], "compare": "previous", "output": "pct", "filters": {"product": "Soda chanh dây (M)"}, "params": {"days": 14}, "answerable": true}
  answer: 200.0 | gold: -29.73 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2025-09-26', 'end_date': '2025-10-10'}] -> [{'type': 'day', 'date': '2025-09-10'}] (date tagger)"]
- [biz_113] wrong | q_e24f4eb5442a | Doanh thu hôm qua của cửa hàng là bao nhiêu?
  intent: {"metric": "revenue", "periods": [{"type": "yesterday"}]}
  answer: 42473400 | gold: 45552900 | reason: None | fixes: []
- [biz_117] abstain | q_f07d1a553011 | Tháng 8/2025 có bao nhiêu đơn có doanh thu từ 3.300.000 đồng trở lên?
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"min_value": 3300000, "strict": true}}
  answer: None | gold: 88 | reason: unknown filter min_value; unknown filter strict | fixes: []
- [biz_117] abstain | q_f895c5de92bd | Có bao nhiêu khách hàng ở đường Trần Não?
  intent: {}
  answer: None | gold: UNANSWERABLE | reason: no intent | fixes: []
- [biz_118] wrong | q_ec5c0d7eed96 | thang 3/2026 co bnhiu don bi huy vi giao tre
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2026}], "filters": {"status": "giao tre"}}
  answer: 0 | gold: UNANSWERABLE | reason: None | fixes: []
- [biz_120] wrong | q_f448394fcfee | thang 9/2025, dthu cac don ban qua dien thoai la bao nhieu, doanh thu cac don ban qua zalo oa la bao nhieu
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 9, "year": 2025}], "filters": {"channel": "zalo"}, "answerable": true}
  answer: 16074900 | gold: [13759000, 16074900] | reason: None | fixes: ['channel -> zalo', "dropped payment_method 'điện thoại' (it named the channel)", 'dropped output diff without compare']
- [biz_120] wrong | q_fa4e465d2ea1 | Cho mình hỏi tuần trước ca sáng có bao nhiêu đơn hàng?
  intent: {"metric": "order_count", "periods": [{"type": "last_week"}], "filters": {"shift": "ca_sang"}}
  answer: 380 | gold: 268 | reason: None | fixes: []
- [biz_121] wrong | q_e6dd8fd4a42a | ê pharmaton essential hộp 30 viên lên giá 231.500đ từ ngày 20/05/2025; so 30 ngày kể từ ngày tăng giá với 30 ngày ngay trc, lượng bán tính theo hộp tăng hay giảm bao nhiu %
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2025-05-20"}], "filters": {"product": "Pharmaton Essential hộp 30 viên"}, "compare": "previous", "output": "pct"}
  answer: None | gold: 13.95 | reason: comparison base is zero | fixes: ["periods [{'type': 'range', 'start_date': '2025-06-19', 'end_date': '2025-07-19'}] -> [{'type': 'day', 'date': '2025-05-20'}] (date tagger)"]
- [biz_121] wrong | q_f26d33760e59 | So số viên UPSA-C 1g viên sủi tuýp 10 viên bán ra trong 14 ngày kể từ ngày 22/03/2026, ngày tăng giá lên 3.900đ, với 14 ngày ngay trước ngày đó: tăng hay giảm bao nhiêu %?
  intent: {"metric": "quantity", "periods": [{"type": "day", "date": "2026-03-22"}], "filters": {"product": "UPSA-C 1g viên sủi tuýp 10 viên"}, "compare": "previous", "output": "pct"}
  answer: 66.67 | gold: -0.64 | reason: None | fixes: ["periods [{'type': 'range', 'start_date': '2026-03-08', 'end_date': '2026-03-22'}] -> [{'type': 'day', 'date': '2026-03-22'}] (date tagger)"]
- [biz_122] abstain | q_f120d0f5e7d0 | có bnhiu khách hàng ở đường hậu giang
  intent: {"metric": "customer_count", "periods": [{"type": "today"}], "filters": {"customer": "Bùi Huy Lan"}, "params": {"address": "đường Hậu Giang"}}
  answer: None | gold: UNANSWERABLE | reason: unknown metric 'customer_count' | fixes: []
- [biz_122] wrong | q_fe14e521d3e0 | ton kho strepsils cool hop 2 vi x 12 vien cuoi ngay hom nay dc may hop chan va may vien le
  intent: {"metric": "stock", "periods": [{"type": "as_of", "date": "2026-07-17"}], "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"split_big_unit": true}}
  answer: None | gold: [8, 9] | reason: no stock report | fixes: []
- [biz_123] abstain | q_d70531d80ed2 | thuoc co hoat chat ibuprofen thang 12/2025 ban dc tong cong bn tien
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"active_ingredient": "ibuprofen"}}
  answer: None | gold: 6720000 | reason: TypeError: 'NoneType' object is not subscriptable | fixes: ["dropped product 'thuoc co hoat chat ibuprofen' (question names a drug attribute)", 'active_ingredient -> ibuprofen']
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
  answer: None | gold: 14.37 | reason: shop does not record customer group 'than thiết' | fixes: ['dropped output pct without compare']
- [biz_124] wrong | q_eef55227353d | doanh thu tet nam nay so vs tet nam truoc thay doi may phan tram ha
  intent: {"metric": "revenue", "periods": [{"type": "tet", "year": 2026}], "compare": "previous", "output": "pct"}
  answer: 5.27 | gold: 23.02 | reason: None | fixes: []
- [biz_124] abstain | q_fe8f9e79f8b5 | Trừ thuốc kê đơn ra, tháng 4/2026 các mặt hàng còn lại bán đc bao nhiêu tiền
  intent: {}
  answer: None | gold: 356487300 | reason: no intent | fixes: []
- [biz_127] wrong | q_ef9ec0a860f8 | Tháng 6/2026 thu hồi được bao nhiêu tiền công nợ từ khách mua chịu?
  intent: {"metric": "new_debt_and_repaid", "periods": [{"type": "month", "month": 6, "year": 2026}], "filters": {"payment_method": "debt"}, "params": {"part": "new"}}
  answer: 6250500 | gold: 9792001 | reason: None | fixes: []
- [biz_129] wrong | q_f6a1f1419974 | gia ban mot phan Ngheu hap sa vao ngay 16/11/2025 la bao nhieu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-11-16"}], "filters": {"product": "Mì xào hải sản"}}
  answer: 79000 | gold: 69000 | reason: None | fixes: []
- [biz_129] wrong | q_ff4cd475782d | Cho hỏi trong tháng 3/2025, cửa hàng có mấy đơn ở trạng thái huỷ?
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2025}], "filters": {"status": "cancelled"}}
  answer: 0 | gold: 50 | reason: None | fixes: []