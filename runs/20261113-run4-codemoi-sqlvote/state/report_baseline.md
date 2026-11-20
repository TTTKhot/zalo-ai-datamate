| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 184 (234✓ 50✗ 16–) | 181 (227✓ 46✗ 27–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 183 (236✓ 53✗ 11–) | 180 (229✓ 49✗ 22–) | 184 (223✓ 39✗ 38–) | · | · | · | · |

```json
[
 {
  "run": "v5",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 234,
   "wrong": 50,
   "abstain": 16,
   "score": 184
  },
  "v5": {
   "n": 300,
   "correct": 227,
   "wrong": 46,
   "abstain": 27,
   "score": 181
  },
  "by_metric": {
   "revenue": {
    "wrong": 21,
    "correct": 102,
    "abstain": 5
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
    "correct": 16,
    "wrong": 2
   },
   "cancel_rate": {
    "correct": 14,
    "wrong": 4
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
    "wrong": 3,
    "correct": 3
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
   "correct": 236,
   "wrong": 53,
   "abstain": 11,
   "score": 183
  },
  "v5": {
   "n": 300,
   "correct": 229,
   "wrong": 49,
   "abstain": 22,
   "score": 180
  },
  "+agree": {
   "n": 300,
   "correct": 223,
   "wrong": 39,
   "abstain": 38,
   "score": 184
  },
  "by_metric": {
   "revenue": {
    "wrong": 21,
    "correct": 103,
    "abstain": 4
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
    "correct": 16,
    "wrong": 2
   },
   "cancel_rate": {
    "correct": 14,
    "wrong": 4
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
    "wrong": 3,
    "correct": 3
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
    "wrong": 2
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
   },
   "customer_count": {
    "wrong": 1
   }
  }
 }
]
```
