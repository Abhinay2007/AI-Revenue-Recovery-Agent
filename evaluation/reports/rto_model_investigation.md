# RTO Model Investigation

## A. Current Result

The current COD-only synthetic model has moderate ranking power and weak recall at threshold 0.50. This investigation does not alter labels, tune on the test set, or change the held-out test split.

- COD rows: 7285
- Train rows: 5099
- Validation rows: 1092
- Test rows: 1094
- Train boundary: 2026-01-01T00:00:00+00:00 to 2026-02-04T05:34:00+00:00
- Validation boundary: 2026-02-04T05:41:00+00:00 to 2026-02-11T11:45:00+00:00
- Test boundary: 2026-02-11T11:59:00+00:00 to 2026-02-18T14:26:00+00:00

## B. Feature Behavior

Pearson correlations with RTO:

| feature | pearson_rto |
| --- | --- |
| amount | 0.0206 |
| customer_account_age_days | -0.1132 |
| previous_cod_orders | -0.2075 |
| previous_cod_refusals | 0.0752 |
| previous_successful_deliveries | -0.2154 |
| pincode_rto_rate | 0.1356 |
| refusal_rate | 0.1045 |
| delivery_success_rate | -0.1839 |
| order_history_depth | -0.2134 |
| log_amount | 0.0211 |

Spearman correlations with RTO:

| feature | spearman_rto |
| --- | --- |
| amount | 0.0200 |
| customer_account_age_days | -0.1282 |
| previous_cod_orders | -0.2075 |
| previous_cod_refusals | 0.0583 |
| previous_successful_deliveries | -0.2158 |
| pincode_rto_rate | 0.1312 |
| refusal_rate | 0.0723 |
| delivery_success_rate | -0.1785 |
| order_history_depth | -0.2126 |
| log_amount | 0.0200 |

Monotonic checks:

- pincode_rto_rate expected increasing: generally_aligned
- previous_cod_refusals expected increasing: generally_aligned
- previous_successful_deliveries expected decreasing: generally_aligned

## C. Model Comparison

Train performance:

| Model | ROC-AUC | PR-AUC | Brier | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy prevalence | 0.5000 | 0.2897 | 0.2058 | 0.0000 | 0.0000 | 0.0000 |
| Logistic regression | 0.6833 | 0.4454 | 0.1887 | 0.5572 | 0.1253 | 0.2045 |
| Random forest | 0.7446 | 0.5376 | 0.2072 | 0.4357 | 0.7299 | 0.5457 |
| Gradient boosting | 0.7421 | 0.5459 | 0.1757 | 0.7034 | 0.1943 | 0.3045 |

Validation performance:

| Model | ROC-AUC | PR-AUC | Brier | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy prevalence | 0.5000 | 0.3068 | 0.2130 | 0.0000 | 0.0000 | 0.0000 |
| Logistic regression | 0.6981 | 0.4861 | 0.1920 | 0.5750 | 0.1373 | 0.2217 |
| Random forest | 0.6929 | 0.4779 | 0.2205 | 0.4237 | 0.7045 | 0.5291 |
| Gradient boosting | 0.6815 | 0.4580 | 0.1951 | 0.5658 | 0.1284 | 0.2092 |

Held-out test performance:

| Model | ROC-AUC | PR-AUC | Brier | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy prevalence | 0.5000 | 0.2907 | 0.2062 | 0.0000 | 0.0000 | 0.0000 |
| Logistic regression | 0.6899 | 0.4512 | 0.1879 | 0.4923 | 0.1006 | 0.1671 |
| Random forest | 0.6932 | 0.4382 | 0.2176 | 0.4133 | 0.6824 | 0.5148 |
| Gradient boosting | 0.6796 | 0.4333 | 0.1904 | 0.5309 | 0.1352 | 0.2155 |

The model selected by validation ROC-AUC is: **Logistic regression**.
The strongest held-out test ROC-AUC in this single comparison is: **Random forest**.

## D. Pincode Investigation

Pincode RTO buckets:

| bucket | orders | rto_rate |
| --- | --- | --- |
| (0.079, 0.15] | 2382 | 0.2284 |
| (0.15, 0.22] | 1544 | 0.2694 |
| (0.22, 0.3] | 1538 | 0.3062 |
| (0.3, 0.38] | 976 | 0.3555 |
| (0.38, 0.46] | 845 | 0.4166 |

- Pearson correlation(pincode_rto_rate, RTO): 0.1356
- Mean pincode_rto_rate for DELIVERED: 0.2138
- Mean pincode_rto_rate for RTO: 0.2455

The global pincode relationship is directionally correct in the data. A local explanation can still show `pincode_rto_rate` as decreasing risk for an individual order when that order's pincode rate is below the train-set reference value.

## E. Customer-History Investigation

Previous COD refusals:

| previous_cod_refusals | orders | rto_rate |
| --- | --- | --- |
| 0.0000 | 5099.0000 | 0.2787 |
| 1.0000 | 1274.0000 | 0.2739 |
| 2.0000 | 595.0000 | 0.3832 |
| 3.0000 | 233.0000 | 0.4077 |
| 4.0000 | 84.0000 | 0.4405 |

Refusal rate buckets:

| bucket | orders | rto_rate |
| --- | --- | --- |
| (-0.001, 0.001] | 5099 | 0.2787 |
| (0.001, 0.15] | 1185 | 0.2329 |
| (0.15, 0.3] | 602 | 0.4203 |
| (0.3, 0.5] | 285 | 0.4386 |
| (0.5, 1.0] | 114 | 0.4825 |

Previous successful deliveries:

| previous_successful_deliveries | orders | rto_rate |
| --- | --- | --- |
| 0.0000 | 2308.0000 | 0.3986 |
| 1.0000 | 310.0000 | 0.3677 |
| 2.0000 | 312.0000 | 0.4231 |
| 3.0000 | 307.0000 | 0.3453 |
| 4.0000 | 352.0000 | 0.3040 |
| 5.0000 | 382.0000 | 0.3194 |
| 6.0000 | 325.0000 | 0.2646 |
| 7.0000 | 334.0000 | 0.2635 |
| 8.0000 | 322.0000 | 0.2143 |
| 9.0000 | 290.0000 | 0.1862 |
| 10.0000 | 286.0000 | 0.1818 |
| 11.0000 | 255.0000 | 0.1647 |
| 12.0000 | 249.0000 | 0.1807 |
| 13.0000 | 247.0000 | 0.1660 |
| 14.0000 | 238.0000 | 0.1681 |
| 15.0000 | 230.0000 | 0.1435 |
| 16.0000 | 197.0000 | 0.1472 |
| 17.0000 | 174.0000 | 0.1897 |
| 18.0000 | 167.0000 | 0.1018 |

Delivery success rate buckets:

| bucket | orders | rto_rate |
| --- | --- | --- |
| (-0.001, 0.001] | 2308 | 0.3986 |
| (0.001, 0.25] | 229 | 0.3843 |
| (0.25, 0.5] | 737 | 0.3433 |
| (0.5, 0.75] | 1767 | 0.2377 |
| (0.75, 1.0] | 2244 | 0.2001 |

## F. Probability Separation

Probability summary for **Logistic regression** on held-out test:

| actual | mean | median | p25 | p75 | p90 |
| --- | --- | --- | --- | --- | --- |
| DELIVERED | 0.2653 | 0.2600 | 0.1596 | 0.3480 | 0.4431 |
| RTO | 0.3486 | 0.3328 | 0.2800 | 0.4279 | 0.4986 |

## G. Threshold Analysis

Synthetic cost assumptions: false_positive_cost=25.00, false_negative_cost=150.00.

| threshold | precision | recall | false_positive_rate | false_negative_rate | predicted_high_risk_count | false_positives | false_negatives | synthetic_total_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2000 | 0.3590 | 0.8931 | 0.6534 | 0.1069 | 791.0000 | 507.0000 | 34.0000 | 17775.0000 |
| 0.2500 | 0.3906 | 0.8082 | 0.5168 | 0.1918 | 658.0000 | 401.0000 | 61.0000 | 19175.0000 |
| 0.3000 | 0.4141 | 0.6289 | 0.3647 | 0.3711 | 483.0000 | 283.0000 | 118.0000 | 24775.0000 |
| 0.3500 | 0.4412 | 0.4717 | 0.2448 | 0.5283 | 340.0000 | 190.0000 | 168.0000 | 29950.0000 |
| 0.4000 | 0.4680 | 0.2987 | 0.1392 | 0.7013 | 203.0000 | 108.0000 | 223.0000 | 36150.0000 |
| 0.4500 | 0.4797 | 0.2233 | 0.0992 | 0.7767 | 148.0000 | 77.0000 | 247.0000 | 38975.0000 |
| 0.5000 | 0.4923 | 0.1006 | 0.0425 | 0.8994 | 65.0000 | 33.0000 | 286.0000 | 43725.0000 |
| 0.5500 | 0.5769 | 0.0472 | 0.0142 | 0.9528 | 26.0000 | 11.0000 | 303.0000 | 45725.0000 |
| 0.6000 | 0.8462 | 0.0346 | 0.0026 | 0.9654 | 13.0000 | 2.0000 | 307.0000 | 46100.0000 |
| 0.6500 | 0.6667 | 0.0063 | 0.0013 | 0.9937 | 3.0000 | 1.0000 | 316.0000 | 47425.0000 |
| 0.7000 | 1.0000 | 0.0031 | 0.0000 | 0.9969 | 1.0000 | 0.0000 | 317.0000 | 47550.0000 |

## H. Calibration

Gradient-boosting calibration was fitted on validation only.

| Split | Raw Brier | Calibrated Brier |
| --- | ---: | ---: |
| Validation | 0.1951 | 0.1962 |
| Held-out test | 0.1904 | 0.1915 |

Calibration does not improve Brier score on validation or held-out test for this run. Keep raw model probabilities for now unless a calibration approach demonstrates held-out benefit.

## I. Root Cause

The synthetic signal exists, but it is intentionally noisy and overlapping. Logistic regression performs slightly better than gradient boosting on this generated dataset because much of the signal is smooth and approximately monotonic, while the current gradient boosting configuration appears to trade some ranking quality for nonlinear interactions. Weak recall at 0.50 is mostly a thresholding issue in an imbalanced dataset with a roughly 29% RTO rate, not evidence of a broken target or leakage.

## J. Recommendation

**PROCEED WITH LIMITATIONS**

Proceed only with clear limitations: keep using probabilities rather than hard labels, avoid treating threshold 0.50 as a business rule, prefer validation-selected models, and let the future economic engine combine probability with deterministic costs.

## Global Feature Importance

Feature importance for validation-selected model:

| base_feature | importance |
| --- | --- |
| pincode_risk_group | 0.8111 |
| previous_cod_refusals | 0.3999 |
| product_category | 0.3729 |
| pincode_rto_rate | 0.1127 |
| log_amount | 0.0900 |
| delivery_success_rate | 0.0544 |
| is_first_order | 0.0507 |
| previous_successful_deliveries | 0.0388 |
| order_history_depth | 0.0325 |
| refusal_rate | 0.0248 |
| previous_cod_orders | 0.0063 |
| amount | 0.0001 |
| customer_account_age_days | 0.0000 |
