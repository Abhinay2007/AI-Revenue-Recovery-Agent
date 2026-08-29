# Recovery Experiment Report

## Executive Summary

ALL RESULTS ARE SIMULATED USING SYNTHETIC DATA AND SYNTHETIC INTERVENTION ASSUMPTIONS.

- Baseline net recovery: 0.00
- Treatment net recovery: 9170.52
- Incremental net revenue recovered: 9170.52
- Intervention rate: 0.4479
- Recovery rate: 0.2421

## Dataset

- Number of evaluated orders: 1094
- COD orders: 1094
- RTO orders: 318
- RTO rate: 0.2907
- Total order value: 2006482.22

## Experimental Design

Baseline is `NO RECOVERY AGENT`: no intervention, no intervention cost, and no recovered revenue from intervention.

Treatment is `RTO predictor -> revenue at risk -> decision engine -> selected intervention -> simulated outcome`.

Both strategies use the same COD held-out evaluation population. Decision generation uses order features, predicted RTO probability, merchant policy, and recovery assumptions. It does not use actual `rto_outcome`; that field is used only afterward for evaluation. Random intervention outcomes use fixed seed `42`.

## Economic Results

| Metric | Baseline | Recovery Policy | Increment |
| --- | --- | --- | --- |
| Gross recovery | 0.0000 | 20996.1600 | 20996.1600 |
| Intervention cost | 0.0000 | 11825.6400 | 11825.6400 |
| Net recovery | 0.0000 | 9170.5200 | 9170.5200 |

Primary metric: **INCREMENTAL NET REVENUE RECOVERED = treatment_net_recovery - baseline_net_recovery**.

## Revenue-at-Risk Coverage

- Total predicted revenue at risk: 624088.81
- Targeted revenue at risk: 388875.52
- Targeting rate: 0.6231

## Action Distribution

| action | count | percentage | gross_recovery | intervention_cost | net_recovery |
| --- | --- | --- | --- | --- | --- |
| NO_ACTION | 604 | 0.5521 | 0.0000 | 0.0000 | 0.0000 |
| ADDRESS_OTP | 0 | 0.0000 | 0 | 0 | 0 |
| PARTIAL_PREPAY | 462 | 0.4223 | 20083.7700 | 9240.0000 | 10843.7700 |
| PREPAID_INCENTIVE | 28 | 0.0256 | 912.3900 | 2585.6400 | -1673.2500 |
| MANUAL_REVIEW | 0 | 0.0000 | 0 | 0 | 0 |

## Risk-band Analysis

Recovery rate denominator is actual RTO orders. Intervention success rate denominator is attempted interventions.

| risk_band | orders | actual_rto_rate | average_predicted_rto_probability | interventions | successful_recoveries | net_recovery |
| --- | --- | --- | --- | --- | --- | --- |
| LOW | 781 | 0.2254 | 0.2472 | 177 | 22 | 1055.3100 |
| MEDIUM | 298 | 0.4564 | 0.4296 | 298 | 54 | 7508.2200 |
| HIGH | 15 | 0.4000 | 0.5749 | 15 | 1 | 606.9900 |

## Order-value Analysis

| order_value_bucket | orders | rto_rate | revenue_at_risk | interventions | net_recovery |
| --- | --- | --- | --- | --- | --- |
| < Rs 1000 | 312 | 0.2500 | 55474.6200 | 119 | 257.6700 |
| Rs 1000-Rs 2500 | 555 | 0.3135 | 286410.8800 | 254 | 5407.2900 |
| Rs 2500-Rs 5000 | 186 | 0.3011 | 193016.3500 | 93 | 5133.1300 |
| Rs 5000-Rs 10000 | 39 | 0.2051 | 48481.3600 | 23 | -1468.2400 |
| > Rs 10000 | 2 | 1.0000 | 20240.7400 | 1 | -159.3300 |

## False Intervention Analysis

False intervention count means interventions on orders that would have been delivered. False intervention rate denominator is attempted interventions.

- Interventions on orders that would have been delivered: 287
- Interventions on actual RTO orders: 203
- False intervention rate: 0.5857

## Guardrail Results

- Policy blocked actions: 2929
- Guardrail trigger count: 3549
- Orders sent to manual review: 0
- Orders with no action: 604

## Sensitivity Analysis

| scenario | gross_recovery | intervention_cost | net_recovery | incremental_net_recovery |
| --- | --- | --- | --- | --- |
| CONSERVATIVE | 12985.0600 | 11193.6400 | 1791.4200 | 1791.4200 |
| BASE | 20996.1600 | 11825.6400 | 9170.5200 | 9170.5200 |
| OPTIMISTIC | 32289.1300 | 12429.5100 | 19859.6200 | 19859.6200 |

## Threshold Analysis

| threshold | intervention_rate | successful_recoveries | gross_recovery | cost | net_recovery | false_intervention_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 0.2000 | 0.8126 | 110 | 27164.4200 | 20588.8200 | 6575.6000 | 0.6670 |
| 0.3000 | 0.4479 | 77 | 20996.1600 | 11825.6400 | 9170.5200 | 0.5857 |
| 0.4000 | 0.1974 | 39 | 13673.7100 | 5670.6400 | 8003.0700 | 0.5556 |
| 0.5000 | 0.0484 | 10 | 3927.0000 | 1488.5500 | 2438.4500 | 0.5283 |
| 0.6000 | 0.0018 | 1 | 320.4100 | 40.0000 | 280.4100 | 0.0000 |
| 0.7000 | 0.0000 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Limitations

- Synthetic dataset
- Synthetic intervention probabilities
- Synthetic intervention costs
- Simulated recovery outcomes
- No real merchant data
- No real customer behavior measurement
- No real payment execution
- No real messaging
- ML model has moderate predictive performance
- Recovery estimates are not real-world revenue claims
