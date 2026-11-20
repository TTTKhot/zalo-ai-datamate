| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 145 (214✓ 69✗ 17–) | 139 (206✓ 67✗ 27–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 141 (215✓ 74✗ 11–) | 137 (205✓ 68✗ 27–) | 141 (198✓ 57✗ 45–) | · | · | · | · |

```json
[
 {
  "run": "v5",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 214,
   "wrong": 69,
   "abstain": 17,
   "score": 145
  },
  "v5": {
   "n": 300,
   "correct": 206,
   "wrong": 67,
   "abstain": 27,
   "score": 139
  },
  "by_metric": {
   "revenue": {
    "wrong": 34,
    "correct": 89,
    "abstain": 5
   },
   "quantity": {
    "correct": 28,
    "wrong": 3,
    "abstain": 2
   },
   "order_count": {
    "correct": 13,
    "wrong": 4,
    "abstain": 4
   },
   "avg_order_value": {
    "correct": 12,
    "wrong": 6
   },
   "cancel_rate": {
    "correct": 18
   },
   "best_day": {
    "correct": 16,
    "wrong": 1
   },
   "unit_price": {
    "correct": 9,
    "wrong": 3
   },
   "cancelled_count": {
    "correct": 5,
    "wrong": 2
   },
   "top_customers": {
    "wrong": 4,
    "correct": 2
   },
   "top_products": {
    "correct": 5,
    "abstain": 1
   },
   "price_effect": {
    "wrong": 2,
    "correct": 3
   },
   "debt_total": {
    "correct": 3,
    "wrong": 1,
    "abstain": 1
   },
   "stock": {
    "wrong": 3,
    "abstain": 1
   },
   "unsold_products": {
    "wrong": 2,
    "correct": 1
   },
   "avg_purchase_price": {
    "correct": 3
   },
   "?": {
    "abstain": 3
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "customers_min_orders": {
    "wrong": 2
   },
   "purchase_total": {
    "correct": 1,
    "wrong": 1
   },
   "new_debt_and_repaid": {
    "correct": 1,
    "wrong": 1
   },
   "products_min_orders": {
    "correct": 1
   }
  }
 },
 {
  "run": "v5_sql",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 215,
   "wrong": 74,
   "abstain": 11,
   "score": 141
  },
  "v5": {
   "n": 300,
   "correct": 205,
   "wrong": 68,
   "abstain": 27,
   "score": 137
  },
  "+agree": {
   "n": 300,
   "correct": 198,
   "wrong": 57,
   "abstain": 45,
   "score": 141
  },
  "by_metric": {
   "revenue": {
    "wrong": 34,
    "correct": 90,
    "abstain": 4
   },
   "quantity": {
    "correct": 28,
    "wrong": 3,
    "abstain": 2
   },
   "order_count": {
    "correct": 13,
    "wrong": 6,
    "abstain": 2
   },
   "avg_order_value": {
    "correct": 12,
    "wrong": 6
   },
   "cancel_rate": {
    "correct": 18
   },
   "best_day": {
    "correct": 16,
    "wrong": 1
   },
   "unit_price": {
    "correct": 9,
    "wrong": 3
   },
   "cancelled_count": {
    "correct": 5,
    "wrong": 2
   },
   "top_customers": {
    "wrong": 4,
    "correct": 2
   },
   "top_products": {
    "correct": 5,
    "abstain": 1
   },
   "price_effect": {
    "wrong": 2,
    "correct": 3
   },
   "debt_total": {
    "correct": 3,
    "wrong": 1,
    "abstain": 1
   },
   "stock": {
    "wrong": 3,
    "abstain": 1
   },
   "unsold_products": {
    "wrong": 2,
    "correct": 1
   },
   "avg_purchase_price": {
    "correct": 3
   },
   "?": {
    "wrong": 3
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "customers_min_orders": {
    "wrong": 2
   },
   "purchase_total": {
    "correct": 1,
    "wrong": 1
   },
   "new_debt_and_repaid": {
    "correct": 1,
    "wrong": 1
   },
   "products_min_orders": {
    "correct": 1
   }
  }
 }
]
```
