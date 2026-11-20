# Run 20261116-0934

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_v5 (5 shop): đúng 94 sai 6 bỏ trống 0 → 88  ← chi tiết bên dưới

## results_v5 theo shop

- biz_101: đúng 20 sai 0 bỏ trống 0 → 20
- biz_107: đúng 19 sai 1 bỏ trống 0 → 18
- biz_108: đúng 19 sai 1 bỏ trống 0 → 18
- biz_120: đúng 17 sai 3 bỏ trống 0 → 14
- biz_128: đúng 19 sai 1 bỏ trống 0 → 18

**Tổng results_v5: đúng 94 sai 6 bỏ trống 0 → 88**

## Theo metric

- stock: {'wrong': 3, 'correct': 1}
- revenue: {'correct': 44, 'wrong': 2}
- top_customers: {'wrong': 1, 'correct': 2}
- order_count: {'correct': 9}
- unit_price: {'correct': 3}
- best_day: {'correct': 9}
- top_products: {'correct': 3}
- quantity: {'correct': 8}
- avg_order_value: {'correct': 3}
- cancelled_count: {'correct': 2}
- avg_purchase_price: {'correct': 4}
- cancel_rate: {'correct': 2}
- purchase_total: {'correct': 3}
- stock_value: {'correct': 1}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 5 | 100 | 88 (94✓ 6✗ 0–) | 87 (93✓ 6✗ 1–) | · | · | · | · | 83.2% of 95 |


## Câu sai / bỏ trống

- [biz_107] wrong | q_43bd8e35df66 | xem giup hqua cua hang ban duoc bao nhiu tien
  intent: {"metric": "revenue", "periods": [{"type": "yesterday"}], "filters": {"staff": "hang ban duoc"}, "answerable": true}
  answer: {'type': 'unanswerable', 'reason': 'no staff column'} | gold: 3823800 | reason: no staff column | fixes: ['dropped output diff without compare']
- [biz_108] wrong | q_230963509814 | Nhân viên bán giỏi nhất tháng 12/2025 là ai?
  intent: {"metric": "top_customers", "periods": [{"type": "month", "month": 12, "year": 2025}], "params": {"by": "revenue"}}
  answer: {'type': 'string', 'answer': 'Phùng Nam Bích'} | gold: NV001 | reason: None | fixes: []
- [biz_120] wrong | q_0946f3145fb4 | Tồn kho Bisolvon 8mg hộp 3 vỉ x 10 viên cuối ngày hôm nay là bao nhiêu viên ạ?
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Bisolvon 8mg hộp 3 vỉ x 10 viên"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: {'type': 'list', 'answer': [0, 23]} | gold: 23 | reason: None | fixes: []
- [biz_120] wrong | q_15401db964f7 | Cuối ngày hôm nay Fugacar 500mg hộp 1 viên còn bao nhiêu viên?
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Fugacar 500mg hộp 1 viên"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: {'type': 'list', 'answer': [94, 0]} | gold: 94 | reason: None | fixes: []
- [biz_120] wrong | q_2033f8c99c05 | ton kho nuoc muoi sinh ly natri clorid 0,9% vinh phuc chai 500ml cuoi ngay hom nay la bnhiu chai
  intent: {"metric": "stock", "periods": [{"type": "today"}], "filters": {"product": "Nước muối sinh lý Natri clorid 0,9% Vĩnh Phúc chai 500ml"}, "params": {"split_big_unit": true}, "answerable": true}
  answer: {'type': 'list', 'answer': [34, 0]} | gold: 34 | reason: None | fixes: []
- [biz_128] wrong | q_049799837470 | trong tong doanh thu thang nay, phan cua khach nhom than thiet la may %
  intent: {"metric": "revenue", "periods": [{"type": "this_month"}], "share_of_total": true, "answerable": true}
  answer: {'type': 'percent', 'answer': 100.0} | gold: 16.76 | reason: None | fixes: ["dropped customer 'Bùi Cường Hạnh' (not in the question)"]