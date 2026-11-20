| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 30 | 300 | 184 (236✓ 52✗ 12–) | 193 (223✓ 30✗ 47–) | · | · | · | · | · |
| v5_sql | 30 | 300 | 183 (236✓ 53✗ 11–) | 192 (223✓ 31✗ 46–) | 192 (224✓ 32✗ 44–) | · | · | · | · |

```json
[
 {
  "run": "v5",
  "shops": 30,
  "n": 300,
  "raw": {
   "n": 300,
   "correct": 236,
   "wrong": 52,
   "abstain": 12,
   "score": 184
  },
  "v5": {
   "n": 300,
   "correct": 223,
   "wrong": 30,
   "abstain": 47,
   "score": 193
  },
  "by_metric": {
   "revenue": {
    "correct": 100,
    "wrong": 24,
    "abstain": 3
   },
   "quantity": {
    "correct": 28,
    "wrong": 7,
    "abstain": 2
   },
   "order_count": {
    "correct": 16,
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
    "correct": 16
   },
   "unit_price": {
    "correct": 7,
    "wrong": 5
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
   "debt_total": {
    "correct": 3,
    "abstain": 1
   },
   "new_debt_and_repaid": {
    "correct": 3,
    "wrong": 1
   },
   "stock": {
    "wrong": 3,
    "abstain": 1
   },
   "unsold_products": {
    "correct": 3
   },
   "avg_purchase_price": {
    "correct": 2,
    "wrong": 1
   },
   "price_effect": {
    "wrong": 1,
    "abstain": 1
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "customer_count": {
    "correct": 2
   },
   "customers_min_orders": {
    "wrong": 2
   },
   "purchase_total": {
    "correct": 1,
    "wrong": 1
   },
   "products_min_orders": {
    "correct": 1
   },
   "null": {
    "correct": 1
   },
   "?": {
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
   "correct": 223,
   "wrong": 31,
   "abstain": 46,
   "score": 192
  },
  "+agree": {
   "n": 300,
   "correct": 224,
   "wrong": 32,
   "abstain": 44,
   "score": 192
  },
  "by_metric": {
   "revenue": {
    "correct": 100,
    "wrong": 24,
    "abstain": 3
   },
   "quantity": {
    "correct": 28,
    "wrong": 7,
    "abstain": 2
   },
   "order_count": {
    "correct": 16,
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
    "correct": 16
   },
   "unit_price": {
    "correct": 7,
    "wrong": 5
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
   "debt_total": {
    "correct": 3,
    "abstain": 1
   },
   "new_debt_and_repaid": {
    "correct": 3,
    "wrong": 1
   },
   "stock": {
    "wrong": 3,
    "abstain": 1
   },
   "unsold_products": {
    "correct": 3
   },
   "avg_purchase_price": {
    "correct": 2,
    "wrong": 1
   },
   "price_effect": {
    "wrong": 1,
    "abstain": 1
   },
   "debt_table": {
    "correct": 2
   },
   "debtor_count": {
    "correct": 2
   },
   "customer_count": {
    "correct": 2
   },
   "customers_min_orders": {
    "wrong": 2
   },
   "purchase_total": {
    "correct": 1,
    "wrong": 1
   },
   "products_min_orders": {
    "correct": 1
   },
   "null": {
    "correct": 1
   },
   "?": {
    "wrong": 1
   }
  }
 }
]
```
