# Recovery Decision Engine

## Why RTO Prediction Alone Is Not Enough

An RTO model answers one question: how likely is this COD order to return to origin?

The product needs a second deterministic layer: given that risk and the merchant economics, what bounded intervention has the highest expected net recovery? A high-risk order is not automatically worth intervening on if the expected recovery is low, the intervention cost is high, or merchant policy blocks the action.

## Conceptual Architecture

```text
RTO Risk
    ↓
Revenue at Risk
    ↓
Candidate Interventions
    ↓
Expected Recovery
    ↓
Intervention Cost
    ↓
Expected Net Recovery
    ↓
Policy / Guardrails
    ↓
Best Permitted Action
    ↓
Audit Trail
```

## Revenue At Risk

The revenue-at-risk estimate is:

```text
expected_revenue_at_risk = order_amount × rto_probability
```

This is an expected-value estimate, not a guaranteed loss.

Example:

```text
Rs 5000 × 0.70 = Rs 3500
```

## Intervention Options

The current bounded synthetic interventions are:

- `NO_ACTION`
- `ADDRESS_OTP`
- `PARTIAL_PREPAY`
- `PREPAID_INCENTIVE`
- `MANUAL_REVIEW`

Each intervention has configurable synthetic assumptions such as success probability, fixed cost, partial prepayment percentage, or prepaid incentive discount.

These are demo assumptions, not Razorpay statistics and not real merchant performance claims.

## Economic Decision Logic

For each candidate intervention:

```text
expected_recovered_revenue = expected_revenue_at_risk × intervention_success_probability
expected_net_recovery = expected_recovered_revenue - expected_intervention_cost
```

The engine chooses the permitted intervention with the highest positive expected net recovery. If no permitted intervention has positive expected net recovery, it chooses `NO_ACTION`.

## Merchant Policies

Demo default policy:

- `max_partial_prepay_amount = Rs 500`
- `max_discount_percent = 10%`
- `max_intervention_attempts = 2`
- `manual_review_order_value_threshold = Rs 10000`
- `minimum_rto_probability_for_intervention = 0.30`

Policies are deterministic inputs to the decision engine. The API does not accept arbitrary client-provided assumptions or policies for this milestone.

## Guardrails

Implemented checks include:

- Partial prepayment fails when requested amount exceeds the merchant maximum.
- Prepaid incentive fails when discount percent exceeds the merchant maximum.
- Interventions fail when prior attempt count is at or above the merchant maximum.
- Manual review is eligible only for orders at or above the configured high-value threshold.
- Interventions fail when RTO probability is below the configured minimum.

The engine records policy checks and does not silently bypass them.

## Audit Trail

Every decision includes a JSON-serializable audit event with:

- timestamp
- order ID
- RTO probability
- revenue at risk
- candidate actions
- selected action
- decision reasons
- policy checks
- assumption source

Database persistence is intentionally deferred to a later milestone.

## Synthetic Assumptions

Every decision returns:

```text
assumption_source = synthetic_demo_assumption
```

This marks intervention success probabilities and costs as synthetic benchmark assumptions. Future versions should learn these values from merchant outcome data.

## Simulator

The simulator compares:

```text
NO RECOVERY AGENT
```

against:

```text
RISK → DECISION → SIMULATED OUTCOME
```

It tracks orders, RTO orders, revenue at risk, interventions attempted, successful recoveries, gross recovered revenue, intervention cost, net recovered revenue, recovery rate, intervention rate, cost per recovered order, and false intervention rate.

All simulator outcomes are synthetic and should not be presented as real merchant results.

## Experiment Layer

The recovery experiment compares a no-intervention baseline against the deterministic recovery policy on the same held-out COD evaluation population. It uses the saved RTO model artifact for predicted probabilities, sends only prediction-time order data and risk probability into the decision engine, simulates intervention success with a fixed seed, and uses actual `rto_outcome` only after decisions are made for evaluation.

The primary metric is:

```text
incremental_net_revenue_recovered =
treatment_net_recovery - baseline_net_recovery
```

The experiment also reports action distribution, risk-band analysis, order-value analysis, false intervention metrics, guardrail counts, sensitivity analysis, and threshold analysis.

## Deterministic Calculation Boundary

The following must remain deterministic Python:

- RTO probability inputs
- revenue at risk
- expected recovered revenue
- intervention cost
- expected net recovery
- policy checks
- action selection
- audit values

A future LLM may orchestrate tools or draft natural-language communication, but it must not invent financial numbers.

## Limitations

- This is decision support and recovery simulation only.
- It does not charge customers.
- It does not create payment authorization.
- It does not cancel orders.
- It does not claim customer consent.
- It does not send WhatsApp, voice, email, or SMS messages.
- It does not use real customer data.
- It does not integrate with Razorpay APIs.
