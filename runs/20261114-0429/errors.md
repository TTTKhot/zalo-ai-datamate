# Run 20261114-0429

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_v5 (6 shop): đúng 49 sai 8 bỏ trống 3 → 41  ← chi tiết bên dưới
- results_v5_sql (6 shop): đúng 50 sai 10 bỏ trống 0 → 40

## results_v5 theo shop

- biz_101: đúng 9 sai 1 bỏ trống 0 → 8
- biz_105: đúng 10 sai 0 bỏ trống 0 → 10
- biz_116: đúng 9 sai 1 bỏ trống 0 → 8
- biz_117: đúng 8 sai 0 bỏ trống 2 → 8
- biz_122: đúng 5 sai 4 bỏ trống 1 → 1
- biz_129: đúng 8 sai 2 bỏ trống 0 → 6

**Tổng results_v5: đúng 49 sai 8 bỏ trống 3 → 41**

## Theo metric

- revenue: {'wrong': 5, 'correct': 16}
- None: {'abstain': 2}
- order_count: {'correct': 5, 'abstain': 1}
- unit_price: {'correct': 3, 'wrong': 1}
- cancelled_count: {'correct': 2, 'wrong': 1}
- stock: {'wrong': 1}
- quantity: {'correct': 4}
- best_day: {'correct': 1}
- cancel_rate: {'correct': 6}
- avg_purchase_price: {'correct': 2}
- debt_table: {'correct': 1}
- avg_order_value: {'correct': 5}
- unsold_products: {'correct': 1}
- price_effect: {'correct': 2}
- debt_total: {'correct': 1}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 6 | 60 | 41 (49✓ 8✗ 3–) | 41 (49✓ 8✗ 3–) | · | · | · | · | · |
| v5_sql | 6 | 60 | 40 (50✓ 10✗ 0–) | 40 (50✓ 10✗ 0–) | 39 (47✓ 8✗ 5–) | · | · | · | · |


## Câu sai / bỏ trống

- [biz_101] wrong | q_eccd1eb5d9ff | cho tôi bieets dthu tháng 5/2026
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 5, "year": 2026}], "filters": {"product": "Bia Heineken 330ml"}}
  answer: 4510000 | gold: 236600600 | reason: None | fixes: ['dropped output pct without compare']
- [biz_116] wrong | q_fcdacd705ef0 | thang 12/2025 nhom hoan thien chiem bnhiu % dthu z
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 12, "year": 2025}], "filters": {"group": "hoàn thiện"}, "share_of_total": true}
  answer: 0.0 | gold: 3.45 | reason: None | fixes: []
- [biz_117] abstain | q_f07d1a553011 | Tháng 8/2025 có bao nhiêu đơn có doanh thu từ 3.300.000 đồng trở lên?
  intent: {"metric": "order_count", "periods": [{"type": "month", "month": 8, "year": 2025}], "filters": {"min_value": 3300000, "strict": true}}
  answer: None | gold: 88 | reason: unknown filter min_value; unknown filter strict | fixes: []
- [biz_117] abstain | q_f895c5de92bd | Có bao nhiêu khách hàng ở đường Trần Não?
  intent: {}
  answer: None | gold: UNANSWERABLE | reason: no intent | fixes: []
- [biz_122] abstain | q_f120d0f5e7d0 | có bnhiu khách hàng ở đường hậu giang
  intent: {}
  answer: None | gold: UNANSWERABLE | reason: no intent | fixes: []
- [biz_122] wrong | q_fbb2dfbdae61 | thuốc có hoạt chất vitamin c tháng 10/2025 bán được tổng cộng bao nhiêu tiền
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 10, "year": 2025}], "filters": {"product": "Vitamin C 500mg Quapharco hộp 10 vỉ x 10 viên"}}
  answer: 431500 | gold: 2281500 | reason: None | fixes: []
- [biz_122] wrong | q_fe14e521d3e0 | ton kho strepsils cool hop 2 vi x 12 vien cuoi ngay hom nay dc may hop chan va may vien le
  intent: {"metric": "stock", "periods": [{"type": "as_of", "date": "2026-07-17"}], "filters": {"product": "Strepsils Cool hộp 2 vỉ x 12 viên"}, "params": {"split_big_unit": true}}
  answer: None | gold: [8, 9] | reason: no stock report | fixes: []
- [biz_122] wrong | q_fe7efca0973e | Trừ thuốc kê đơn ra, tháng 2/2026 các mặt hàng còn lại bán được bao nhiêu tiền?
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2026}], "filters": {"group": "tiêu hoá"}}
  answer: 0 | gold: 238810400 | reason: None | fixes: ['dropped output diff without compare']
- [biz_122] wrong | q_fefc6fe34685 | Trong tổng dthu tháng 2/2025, phần của thuốc kê đơn là bao nhiêu phần trăm
  intent: {"metric": "revenue", "periods": [{"type": "month", "month": 2, "year": 2025}], "filters": {"group": "dùng ngoài"}, "share_of_total": true}
  answer: 0.0 | gold: 4.76 | reason: None | fixes: []
- [biz_129] wrong | q_f6a1f1419974 | gia ban mot phan Ngheu hap sa vao ngay 16/11/2025 la bao nhieu
  intent: {"metric": "unit_price", "periods": [{"type": "day", "date": "2025-11-16"}], "filters": {"product": "Mì xào hải sản"}}
  answer: 79000 | gold: 69000 | reason: None | fixes: []
- [biz_129] wrong | q_ff4cd475782d | Cho hỏi trong tháng 3/2025, cửa hàng có mấy đơn ở trạng thái huỷ?
  intent: {"metric": "cancelled_count", "periods": [{"type": "month", "month": 3, "year": 2025}], "filters": {"status": "cancelled"}}
  answer: 0 | gold: 50 | reason: None | fixes: []