# Architecture

This document separates the current foundation from planned product capabilities.

## Currently Implemented

### Data Layer

The current data layer includes a PostgreSQL-ready SQLAlchemy setup and an initial `orders` table model. The model captures order identity, customer history, payment method, product category, pincode, order amount, and nullable `rto_outcome` for future supervised learning.

The repository also includes a deterministic synthetic-data generator and validation checks for required columns, valid values, duplicate order IDs, reasonable account ages, reasonable historical counts, and class coverage.

### ML Risk Layer

The current ML risk layer trains a COD-only RTO probability model from the synthetic dataset. It filters to COD orders, excludes leakage columns, engineers a small explainable feature set, splits chronologically, trains prevalence and logistic baselines, trains a gradient-boosting model, calibrates probabilities using validation data only, evaluates on held-out test data, and saves reproducible artifacts.

The prediction service returns an RTO probability, configurable risk level, and model-derived feature impact metadata. It does not decide recovery actions.

### Backend Foundation

The FastAPI application exposes:

```text
GET /health
GET /api/v1/db/health
```

Routes are thin and delegate database checks to a service module. Configuration is centralized through environment variables.

## Planned

### Explainability Layer

The explainability layer will later add fuller SHAP-style explanations and merchant-readable reason codes. It should explain risk, not choose recovery actions.

### Economic Decision Engine

The economic engine will calculate expected financial outcomes for recovery options. It must use deterministic code and merchant-configured inputs such as margins, shipping costs, discount limits, and recovery costs.

### AI Agent

The AI agent will orchestrate reasoning and tools across prediction, explanation, economics, policies, execution, and audit. It must not invent financial calculations or bypass policy constraints.

### Policy/Guardrail Layer

The policy layer will determine which recovery actions are allowed for a merchant, customer segment, order value, and risk level. It will enforce bounded actions, escalation thresholds, and channel restrictions.

### Execution Layer

The execution layer will perform approved recovery actions, such as sending a message, triggering a payment-link conversion flow, escalating for human review, or taking no action.

### Audit Layer

The audit layer will record predictions, explanations, economic calculations, policy decisions, agent reasoning summaries, actions, and outcomes. It should support reproducibility and post-hoc review.

### Evaluation Harness

The evaluation harness will test scenarios, compare baselines, measure revenue recovered, and report honest metrics on held-out data. It should separate offline model quality from business outcome evaluation.

### Frontend

The frontend will provide a merchant-facing dashboard for reviewing at-risk COD orders, explanations, recovery actions, policy settings, outcomes, and audit records.

### Razorpay Integration

The Razorpay integration will use test-mode APIs where appropriate for payment-link or prepaid-conversion workflows. It is not part of the current milestone.
