| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 237 (261✓ 24✗ 15–) | 237 (261✓ 24✗ 15–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 237 (263✓ 26✗ 11–) | 237 (263✓ 26✗ 11–) | 237 (263✓ 26✗ 11–) | · | · | · | · |

```json
[
 {
  "run": "v5",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 261,
   "wrong": 24,
   "abstain": 15,
   "score": 237
  },
  "v5": {
   "n": 300,
   "correct": 261,
   "wrong": 24,
   "abstain": 15,
   "score": 237
  },
  "by_metric": {
   "revenue": {
    "wrong": 8,
    "correct": 116,
    "abstain": 4
   },
   "quantity": {
    "correct": 28,
    "wrong": 3,
    "abstain": 2
   },
   "order_count": {
    "correct": 16,
    "wrong": 2,
    "abstain": 3
   },
   "avg_order_value": {
    "correct": 18
   },
   "cancel_rate": {
    "correct": 18
   },
   "best_day": {
    "correct": 17
   },
   "unit_price": {
    "correct": 10,
    "wrong": 2
   },
   "cancelled_count": {
    "correct": 5,
    "wrong": 2
   },
   "top_customers": {
    "correct": 6
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
    "correct": 2,
    "wrong": 1,
    "abstain": 1
   },
   "unsold_products": {
    "wrong": 1,
    "correct": 2
   },
   "avg_purchase_price": {
    "correct": 3
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "?": {
    "abstain": 2
   },
   "customers_min_orders": {
    "correct": 2
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
   },
   "customer_count": {
    "abstain": 1
   }
  }
 },
 {
  "run": "v5_sql",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 263,
   "wrong": 26,
   "abstain": 11,
   "score": 237
  },
  "v5": {
   "n": 300,
   "correct": 263,
   "wrong": 26,
   "abstain": 11,
   "score": 237
  },
  "+agree": {
   "n": 300,
   "correct": 263,
   "wrong": 26,
   "abstain": 11,
   "score": 237
  },
  "by_metric": {
   "revenue": {
    "wrong": 8,
    "correct": 117,
    "abstain": 3
   },
   "quantity": {
    "correct": 28,
    "wrong": 3,
    "abstain": 2
   },
   "order_count": {
    "correct": 17,
    "wrong": 2,
    "abstain": 2
   },
   "avg_order_value": {
    "correct": 18
   },
   "cancel_rate": {
    "correct": 18
   },
   "best_day": {
    "correct": 17
   },
   "unit_price": {
    "correct": 10,
    "wrong": 2
   },
   "cancelled_count": {
    "correct": 5,
    "wrong": 2
   },
   "top_customers": {
    "correct": 6
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
    "correct": 2,
    "wrong": 1,
    "abstain": 1
   },
   "unsold_products": {
    "wrong": 1,
    "correct": 2
   },
   "avg_purchase_price": {
    "correct": 3
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "?": {
    "wrong": 1,
    "abstain": 1
   },
   "customers_min_orders": {
    "correct": 2
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
   },
   "customer_count": {
    "wrong": 1
   }
  }
 }
]
```
