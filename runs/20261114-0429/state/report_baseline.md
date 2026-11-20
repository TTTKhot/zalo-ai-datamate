| run | shops | n | raw | v5 | +agree | +ans | +ans+rescue | all | intent EM |
|---|---|---|---|---|---|---|---|---|---|
| v5 | 6 | 60 | 41 (49✓ 8✗ 3–) | 41 (49✓ 8✗ 3–) | · | · | · | · | · |
| v5_sql | 6 | 60 | 40 (50✓ 10✗ 0–) | 40 (50✓ 10✗ 0–) | 39 (47✓ 8✗ 5–) | · | · | · | · |

```json
[
 {
  "run": "v5",
  "shops": 6,
  "n": 60,
  "raw": {
   "n": 60,
   "correct": 49,
   "wrong": 8,
   "abstain": 3,
   "score": 41
  },
  "v5": {
   "n": 60,
   "correct": 49,
   "wrong": 8,
   "abstain": 3,
   "score": 41
  },
  "by_metric": {
   "revenue": {
    "wrong": 5,
    "correct": 16
   },
   "order_count": {
    "correct": 5,
    "abstain": 1
   },
   "cancel_rate": {
    "correct": 6
   },
   "avg_order_value": {
    "correct": 5
   },
   "quantity": {
    "correct": 4
   },
   "unit_price": {
    "correct": 3,
    "wrong": 1
   },
   "cancelled_count": {
    "correct": 2,
    "wrong": 1
   },
   "avg_purchase_price": {
    "correct": 2
   },
   "?": {
    "abstain": 2
   },
   "price_effect": {
    "correct": 2
   },
   "best_day": {
    "correct": 1
   },
   "debt_table": {
    "correct": 1
   },
   "unsold_products": {
    "correct": 1
   },
   "stock": {
    "wrong": 1
   },
   "debt_total": {
    "correct": 1
   }
  }
 },
 {
  "run": "v5_sql",
  "shops": 6,
  "n": 60,
  "raw": {
   "n": 60,
   "correct": 50,
   "wrong": 10,
   "abstain": 0,
   "score": 40
  },
  "v5": {
   "n": 60,
   "correct": 50,
   "wrong": 10,
   "abstain": 0,
   "score": 40
  },
  "+agree": {
   "n": 60,
   "correct": 47,
   "wrong": 8,
   "abstain": 5,
   "score": 39
  },
  "by_metric": {
   "revenue": {
    "wrong": 5,
    "correct": 16
   },
   "order_count": {
    "correct": 6
   },
   "cancel_rate": {
    "correct": 6
   },
   "avg_order_value": {
    "correct": 5
   },
   "quantity": {
    "correct": 4
   },
   "unit_price": {
    "correct": 3,
    "wrong": 1
   },
   "cancelled_count": {
    "correct": 2,
    "wrong": 1
   },
   "avg_purchase_price": {
    "correct": 2
   },
   "?": {
    "wrong": 2
   },
   "price_effect": {
    "correct": 2
   },
   "best_day": {
    "correct": 1
   },
   "debt_table": {
    "correct": 1
   },
   "unsold_products": {
    "correct": 1
   },
   "stock": {
    "wrong": 1
   },
   "debt_total": {
    "correct": 1
   }
  }
 }
]
```
