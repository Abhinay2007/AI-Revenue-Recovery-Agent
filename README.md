# AI Revenue Recovery Agent

## Track

Razorpay Buildathon — Track 03: AI Revenue Recovery

## Problem

Indian D2C merchants lose revenue when Cash on Delivery orders are refused, fail delivery, and return to origin. RTO is not just a logistics problem: it leaks revenue, locks inventory, burns shipping cost, and reduces confidence in COD as a growth channel.

This project aims to move beyond merely identifying risky orders. The larger goal is an explainable, policy-bounded revenue recovery system that can predict risk, explain why revenue is at risk, evaluate recovery options, and perform only permitted actions with a complete audit trail.

## Current Milestone

This repository currently contains only the project foundation and synthetic-data pipeline.

Implemented now:

- FastAPI backend foundation
- PostgreSQL and SQLAlchemy setup
- Initial `orders` model for future RTO prediction
- Health checks
- Deterministic synthetic order data generator
- Dataset validation
- COD-only RTO risk model training pipeline
- Temporal train/validation/test split
- Baselines, gradient-boosting model, calibration, threshold analysis, and synthetic cost analysis
- Prediction service with risk levels and model-derived explanation metadata
- Deterministic recovery decision engine with policy guardrails and audit event output
- Synthetic recovery simulator foundation
- pytest coverage for the foundation
- Docker Compose for backend and PostgreSQL

Not implemented yet:

- SHAP explainability
- AI agent
- Guardrails or policy execution
- Razorpay integration
- React dashboard
- Evaluation harness logic
- Full SHAP explainability

## Planned Architecture

```text
Order
 ↓
Risk Detection
 ↓
Risk Explanation
 ↓
Recovery Options
 ↓
Economic Decision
 ↓
AI Agent
 ↓
Guardrails
 ↓
Recovery Action
 ↓
Outcome
 ↓
Revenue Recovered
 ↓
Audit Trail
```

Important separation:

```text
ML Model -> predicts RTO probability
Explainability -> explains model prediction
Economic Engine -> calculates financial outcomes
Policy Engine -> determines what actions are permitted
AI Agent -> orchestrates tools and reasoning
Execution Layer -> performs permitted actions
Audit Layer -> records what happened
```

The LLM must never invent financial calculations. Financial outcomes belong in deterministic code.

## Development Principles

- Explainable decisions
- Deterministic financial calculations
- Bounded actions
- Merchant-defined policies
- Human escalation
- Auditability
- Held-out evaluation
- Honest metrics

## Running Locally

Build and start PostgreSQL plus the backend:

```bash
docker compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

Database health check:

```bash
curl http://localhost:8000/api/v1/db/health
```

## Tests

Install backend dependencies, including test dependencies:

```bash
pip install -e "backend[dev]"
```

Run tests from the repository root:

```bash
pytest
```

Train and evaluate the COD RTO risk model:

```bash
python3 -m app.ml.train
```

When using the project virtualenv created during local setup:

```bash
.venv/bin/python -m app.ml.train
```

This command loads `data/generated/orders.csv`, filters to COD orders, uses a chronological train/validation/test split, trains baselines and a gradient-boosting model, fits calibration on validation data only, saves model artifacts under `data/generated/models/`, and writes `evaluation/reports/rto_model_report.md`.

Run the synthetic recovery experiment:

```bash
.venv/bin/python evaluation/recovery_experiment.py --seed 42
```

This compares a no-intervention baseline with the deterministic recovery policy on the same held-out COD evaluation batch. Outputs are written to `evaluation/reports/recovery_experiment.json` and `evaluation/reports/recovery_experiment.md`.

## Synthetic Data

Generate 10,000 deterministic synthetic orders:

```bash
python data/generate.py --rows 10000 --seed 42
```

The CSV is written to:

```text
data/generated/orders.csv
```

Generated datasets are intentionally ignored by Git. The generator creates realistic relationships between COD usage, pincode risk, customer history, order value, category, and `rto_outcome` without using real customer data.

## Configuration

Configuration is read from environment variables:

```text
APP_ENV
DATABASE_URL
LOG_LEVEL
```

Use `.env.example` as a safe template. Do not commit `.env`.
