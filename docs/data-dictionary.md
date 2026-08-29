# Data Dictionary

The current dataset is synthetic. Prediction-time fields represent information assumed to be available before fulfillment.

| Field | Meaning | Prediction-time available? | ML usage |
| --- | --- | --- | --- |
| order_id | Synthetic order identifier | yes | excluded identifier |
| customer_id | Synthetic customer identifier | yes | excluded identifier |
| amount | Order value | yes | feature |
| payment_method | COD or prepaid payment method | yes | filtered to COD |
| order_status | Final observed order status in the synthetic dataset | no | excluded leakage |
| customer_account_age_days | Customer account age before current order | yes | feature |
| previous_cod_orders | Historical COD orders before current order | yes | feature |
| previous_cod_refusals | Historical COD refusals before current order | yes | feature |
| previous_successful_deliveries | Historical successful deliveries before current order | yes | feature |
| pincode | Delivery pincode | yes | excluded initially |
| pincode_risk_group | Synthetic historical pincode risk bucket | yes | feature |
| pincode_rto_rate | Synthetic historical pincode RTO statistic | yes, as historical statistic | feature |
| product_category | Product category | yes | feature |
| is_first_order | Whether the customer has no prior order history | yes | feature |
| created_at | Order creation timestamp | yes | temporal split only |
| rto_outcome | Observed final RTO outcome | no | target |

## Derived Features

| Field | Definition | Prediction-time available? | ML usage |
| --- | --- | --- | --- |
| refusal_rate | `previous_cod_refusals / previous_cod_orders`, or `0` when previous COD orders are `0` | yes | feature |
| delivery_success_rate | `previous_successful_deliveries / previous_cod_orders`, or `0` when previous COD orders are `0` | yes | feature |
| order_history_depth | `previous_cod_orders + previous_successful_deliveries` | yes | feature |
| log_amount | `log1p(amount)` | yes | feature |

## Target

The RTO model encodes:

```text
RTO -> 1
DELIVERED -> 0
```

## Leakage Rules

The model must never use `rto_outcome` or `order_status` as features. It also excludes raw IDs, raw `pincode`, `payment_method`, and `created_at` from the feature matrix for the current COD-only model.
