# RTO Feature Analysis

Dataset is synthetic and filtered to COD orders only.

- COD rows: 7285
- COD RTO rate: 0.2924

## Pearson Correlation

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

## Spearman Correlation

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

## Pincode RTO Rate Buckets

| bucket | orders | rto_rate |
| --- | --- | --- |
| (0.079, 0.15] | 2382 | 0.2284 |
| (0.15, 0.22] | 1544 | 0.2694 |
| (0.22, 0.3] | 1538 | 0.3062 |
| (0.3, 0.38] | 976 | 0.3555 |
| (0.38, 0.46] | 845 | 0.4166 |

## Pincode Risk Group

| pincode_risk_group | orders | rto_rate |
| --- | --- | --- |
| HIGH | 1821 | 0.3839 |
| LOW | 2852 | 0.2360 |
| MEDIUM | 2612 | 0.2902 |

## Previous COD Refusals

| previous_cod_refusals | orders | rto_rate |
| --- | --- | --- |
| 0.0000 | 5099.0000 | 0.2787 |
| 1.0000 | 1274.0000 | 0.2739 |
| 2.0000 | 595.0000 | 0.3832 |
| 3.0000 | 233.0000 | 0.4077 |
| 4.0000 | 84.0000 | 0.4405 |

## Refusal Rate Buckets

| bucket | orders | rto_rate |
| --- | --- | --- |
| (-0.001, 0.001] | 5099 | 0.2787 |
| (0.001, 0.15] | 1185 | 0.2329 |
| (0.15, 0.3] | 602 | 0.4203 |
| (0.3, 0.5] | 285 | 0.4386 |
| (0.5, 1.0] | 114 | 0.4825 |

## Previous Successful Deliveries

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

## Delivery Success Rate Buckets

| bucket | orders | rto_rate |
| --- | --- | --- |
| (-0.001, 0.001] | 2308 | 0.3986 |
| (0.001, 0.25] | 229 | 0.3843 |
| (0.25, 0.5] | 737 | 0.3433 |
| (0.5, 0.75] | 1767 | 0.2377 |
| (0.75, 1.0] | 2244 | 0.2001 |

## Amount Buckets

| bucket | orders | rto_rate |
| --- | --- | --- |
| (-0.001, 750.0] | 1159 | 0.2718 |
| (750.0, 1500.0] | 2631 | 0.2877 |
| (1500.0, 3000.0] | 2495 | 0.3046 |
| (3000.0, 5000.0] | 771 | 0.2853 |
| (5000.0, 10000.0] | 223 | 0.3318 |
| (10000.0, 25000.0] | 6 | 0.6667 |

## First Order

| is_first_order | orders | rto_rate |
| --- | --- | --- |
| False | 5243 | 0.2514 |
| True | 2042 | 0.3976 |

## Product Category

| product_category | orders | rto_rate |
| --- | --- | --- |
| apparel | 1668 | 0.3237 |
| beauty | 1034 | 0.2785 |
| electronics | 867 | 0.2999 |
| footwear | 961 | 0.3049 |
| grocery | 956 | 0.2573 |
| home | 1234 | 0.2796 |
| jewellery | 565 | 0.2796 |
