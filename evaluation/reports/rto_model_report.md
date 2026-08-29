# RTO Model Evaluation Report

This report uses a synthetic dataset. Metrics should not be interpreted as real-world production performance.

## Dataset

- Total rows: 10000
- COD rows: 7285
- Target encoding: RTO = 1, DELIVERED = 0
- COD RTO rate: 0.2924

## Class Distribution

- Train: rows=5099, RTO=1477 (0.2897), DELIVERED=3622
- Validation: rows=1092, RTO=335 (0.3068), DELIVERED=757
- Test: rows=1094, RTO=318 (0.2907), DELIVERED=776

## Temporal Split

- Train rows: 5099
- Validation rows: 1092
- Test rows: 1094
- Train: 2026-01-01T00:00:00+00:00 to 2026-02-04T05:34:00+00:00
- Validation: 2026-02-04T05:41:00+00:00 to 2026-02-11T11:45:00+00:00
- Test: 2026-02-11T11:59:00+00:00 to 2026-02-18T14:26:00+00:00

The held-out test set contains later orders than the training and validation sets and was not used for model selection or calibration fitting.

## Feature List

- amount
- customer_account_age_days
- previous_cod_orders
- previous_cod_refusals
- previous_successful_deliveries
- pincode_rto_rate
- pincode_risk_group
- product_category
- is_first_order
- refusal_rate
- delivery_success_rate
- order_history_depth
- log_amount

## Leakage Exclusions

Excluded from model features:

- created_at
- customer_id
- order_id
- order_status
- payment_method
- pincode
- rto_outcome

## Baseline A: Training Prevalence

- ROC-AUC: 0.5000
- PR-AUC: 0.2907
- Precision: 0.0000
- Recall: 0.0000
- F1: 0.0000
- Accuracy: 0.7093
- Brier score: 0.2062
- Confusion matrix: TN=776, FP=0, FN=318, TP=0

## Baseline B: Logistic Regression

- ROC-AUC: 0.6899
- PR-AUC: 0.4512
- Precision: 0.4923
- Recall: 0.1006
- F1: 0.1671
- Accuracy: 0.7084
- Brier score: 0.1879
- Confusion matrix: TN=743, FP=33, FN=286, TP=32

## Main Model: Gradient Boosting

Raw model on held-out test:

- ROC-AUC: 0.6796
- PR-AUC: 0.4333
- Precision: 0.5309
- Recall: 0.1352
- F1: 0.2155
- Accuracy: 0.7139
- Brier score: 0.1904
- Confusion matrix: TN=738, FP=38, FN=275, TP=43

Calibrated model on held-out test:

- ROC-AUC: 0.6796
- PR-AUC: 0.4333
- Precision: 0.4717
- Recall: 0.0786
- F1: 0.1348
- Accuracy: 0.7066
- Brier score: 0.1915
- Confusion matrix: TN=748, FP=28, FN=293, TP=25

## Threshold Analysis

Thresholds are candidates for analysis only. The future economic decision engine should combine risk probability with deterministic economics and merchant policy.

| Threshold | Precision | Recall | FPR | FNR | FP | FN | Synthetic cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.30 | 0.4143 | 0.6384 | 0.3698 | 0.3616 | 287 | 115 | 24425.00 |
| 0.40 | 0.4444 | 0.3019 | 0.1546 | 0.6981 | 120 | 222 | 36300.00 |
| 0.50 | 0.4717 | 0.0786 | 0.0361 | 0.9214 | 28 | 293 | 44650.00 |
| 0.60 | 1.0000 | 0.0063 | 0.0000 | 0.9937 | 0 | 316 | 47400.00 |
| 0.70 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0 | 318 | 47700.00 |

## Calibration

- Brier score before calibration: 0.1904
- Brier score after calibration: 0.1915
- Calibration method: logistic calibration fitted on the validation split only.

| Bin | Mean predicted | Observed RTO rate | Count |
| --- | ---: | ---: | ---: |
| 0.1-0.2 | 0.1847 | 0.1078 | 204 |
| 0.2-0.3 | 0.2463 | 0.2325 | 400 |
| 0.3-0.4 | 0.3392 | 0.3905 | 274 |
| 0.4-0.5 | 0.4427 | 0.4356 | 163 |
| 0.5-0.6 | 0.5318 | 0.4510 | 51 |
| 0.6-0.7 | 0.6226 | 1.0000 | 2 |

## Explainability Readiness

The saved prediction service returns feature-level explanation metadata for individual predictions. The current implementation uses model-derived single-feature perturbation against train-set reference values and reports the resulting calibrated probability impact.

SHAP is not implemented in this milestone. The explanation output is suitable metadata for debugging and future UI work, but should be validated before production use.

## Synthetic Cost Assumptions

- False-positive cost: 25.00
- False-negative cost: 150.00

These are synthetic evaluation assumptions used to demonstrate methodology, not real merchant costs.

## Limitations

- The dataset is synthetic and generated from known assumptions.
- Pincode risk statistics are synthetic historical signals, not production aggregates.
- The model is trained only for COD orders.
- Raw pincode, identifiers, `order_status`, and `rto_outcome` are excluded from features.
- The model estimates RTO probability only; it does not decide recovery actions.
