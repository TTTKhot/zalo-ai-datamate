# Run 20261114-run7

## Mọi bộ kết quả (raw, trước ngưỡng)

- results_lora_sql_ans (6 shop): đúng 240 sai 0 bỏ trống 0 → 240  ← chi tiết bên dưới
- results_lora_sql (6 shop): đúng 240 sai 0 bỏ trống 0 → 240
- results_lora (6 shop): đúng 240 sai 0 bỏ trống 0 → 240
- results_v5 (6 shop): đúng 237 sai 3 bỏ trống 0 → 234
- results_v5_sql (6 shop): đúng 237 sai 3 bỏ trống 0 → 234

## results_lora_sql_ans theo shop

- biz_104: đúng 40 sai 0 bỏ trống 0 → 40
- biz_106: đúng 40 sai 0 bỏ trống 0 → 40
- biz_110: đúng 40 sai 0 bỏ trống 0 → 40
- biz_114: đúng 40 sai 0 bỏ trống 0 → 40
- biz_119: đúng 40 sai 0 bỏ trống 0 → 40
- biz_126: đúng 40 sai 0 bỏ trống 0 → 40

**Tổng results_lora_sql_ans: đúng 240 sai 0 bỏ trống 0 → 240**

## Theo metric

- cancelled_count: {'correct': 5}
- order_count: {'correct': 29}
- cancel_rate: {'correct': 7}
- unit_price: {'correct': 7}
- revenue: {'correct': 108}
- best_day: {'correct': 19}
- top_customers: {'correct': 4}
- quantity: {'correct': 17}
- avg_order_value: {'correct': 5}
- top_products: {'correct': 13}
- avg_purchase_price: {'correct': 6}
- purchase_total: {'correct': 4}
- debt_total: {'correct': 3}
- stock: {'correct': 2}
- stock_value: {'correct': 1}
- price_effect: {'correct': 1}
- debt_table: {'correct': 3}
- customers_min_orders: {'correct': 1}
- debt_aging: {'correct': 1}
- expiring: {'correct': 1}
- products_min_orders: {'correct': 1}
- new_debt_and_repaid: {'correct': 1}
- gross_profit: {'correct': 1}

## Theo khớp metric/SQL (agree)

- agree: {'correct': 136}
- disagree: {'correct': 81}
- nosql: {'correct': 23}

## Báo cáo của notebook (sau ngưỡng, giữ kín theo shop)

### report_baseline

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 6 | 240 | 234 (237✓ 3✗ 0–) | 232 (235✓ 3✗ 2–) | · | · | · | · | 89.5% of 239 |
| v5_sql | 6 | 240 | 234 (237✓ 3✗ 0–) | 232 (235✓ 3✗ 2–) | 232 (235✓ 3✗ 2–) | · | · | · | 89.5% of 239 |

### report_step1+2

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 6 | 240 | 234 (237✓ 3✗ 0–) | 232 (235✓ 3✗ 2–) | · | · | · | · | 89.5% of 239 |
| lora | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | · | · | · | · | 92.0% of 239 |
| lora_sql | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | · | · | · | 92.0% of 239 |

### report_step3

| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| lora_sql | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | · | · | · | 92.0% of 239 |
| lora_sql_ans | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 92.0% of 239 |


## Câu sai / bỏ trống
