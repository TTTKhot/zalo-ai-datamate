| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| lora_sql | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | · | · | · | 92.0% of 239 |
| lora_sql_ans | 6 | 240 | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 240 (240✓ 0✗ 0–) | 92.0% of 239 |

```json
[
 {
  "run": "lora_sql",
  "shops": 6,
  "n": 240,
  "raw": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "v5": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "+agree": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "intent_em": 0.9205,
  "intent_n": 239,
  "by_metric": {
   "revenue": {
    "correct": 108
   },
   "order_count": {
    "correct": 29
   },
   "best_day": {
    "correct": 19
   },
   "quantity": {
    "correct": 17
   },
   "top_products": {
    "correct": 13
   },
   "cancel_rate": {
    "correct": 7
   },
   "unit_price": {
    "correct": 7
   },
   "avg_purchase_price": {
    "correct": 6
   },
   "cancelled_count": {
    "correct": 5
   },
   "avg_order_value": {
    "correct": 5
   },
   "top_customers": {
    "correct": 4
   },
   "purchase_total": {
    "correct": 4
   },
   "debt_total": {
    "correct": 3
   },
   "debt_table": {
    "correct": 3
   },
   "stock": {
    "correct": 2
   },
   "stock_value": {
    "correct": 1
   },
   "price_effect": {
    "correct": 1
   },
   "customers_min_orders": {
    "correct": 1
   },
   "debt_aging": {
    "correct": 1
   },
   "expiring": {
    "correct": 1
   },
   "products_min_orders": {
    "correct": 1
   },
   "new_debt_and_repaid": {
    "correct": 1
   },
   "gross_profit": {
    "correct": 1
   }
  }
 },
 {
  "run": "lora_sql_ans",
  "shops": 6,
  "n": 240,
  "raw": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "v5": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "+agree": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "+ans": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "+ans+rescue": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "all": {
   "n": 240,
   "correct": 240,
   "wrong": 0,
   "abstain": 0,
   "score": 240
  },
  "intent_em": 0.9205,
  "intent_n": 239,
  "by_metric": {
   "revenue": {
    "correct": 108
   },
   "order_count": {
    "correct": 29
   },
   "best_day": {
    "correct": 19
   },
   "quantity": {
    "correct": 17
   },
   "top_products": {
    "correct": 13
   },
   "cancel_rate": {
    "correct": 7
   },
   "unit_price": {
    "correct": 7
   },
   "avg_purchase_price": {
    "correct": 6
   },
   "cancelled_count": {
    "correct": 5
   },
   "avg_order_value": {
    "correct": 5
   },
   "top_customers": {
    "correct": 4
   },
   "purchase_total": {
    "correct": 4
   },
   "debt_total": {
    "correct": 3
   },
   "debt_table": {
    "correct": 3
   },
   "stock": {
    "correct": 2
   },
   "stock_value": {
    "correct": 1
   },
   "price_effect": {
    "correct": 1
   },
   "customers_min_orders": {
    "correct": 1
   },
   "debt_aging": {
    "correct": 1
   },
   "expiring": {
    "correct": 1
   },
   "products_min_orders": {
    "correct": 1
   },
   "new_debt_and_repaid": {
    "correct": 1
   },
   "gross_profit": {
    "correct": 1
   }
  }
 }
]
```
