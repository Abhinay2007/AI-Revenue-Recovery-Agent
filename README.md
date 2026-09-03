# AI Revenue Recovery Agent

## Track

Razorpay Buildathon — Track 03: AI Revenue Recovery

## Problem

Indian D2C merchants lose revenue when Cash on Delivery orders are refused, fail delivery, and return to origin. RTO is not just a logistics problem: it leaks revenue, locks inventory, burns shipping cost, and reduces confidence in COD as a growth channel.

This project aims to move beyond merely identifying risky orders. The larger goal is an explainable, policy-bounded revenue recovery system that can predict risk, explain why revenue is at risk, evaluate recovery options, and perform only permitted actions with a complete audit trail.

## Current Milestone

This repository currently contains the project foundation, synthetic-data pipeline, COD RTO model, deterministic recovery decision layer, and a bounded AI agent orchestration layer.

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
- AI revenue recovery agent with local, mock, OpenAI Responses API, and Groq providers
- Typed tools for order analysis, risk, revenue-at-risk, recovery recommendations, policy checks, simulated execution, audit, and merchant-level summaries
- Explicit approval API before simulated recovery execution
- pytest coverage for the foundation
- Docker Compose for backend and PostgreSQL

Not implemented yet:

- Razorpay integration
- React dashboard
- Real payment execution
- Customer messaging
- Durable audit or pending-approval persistence

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

Agent API:

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Recover ORD-0042-0009754","session_id":"demo"}'
```

The first response only creates a pending simulated action. Execute through explicit approval:

```bash
curl -X POST http://localhost:8000/api/v1/agent/approve \
  -H "Content-Type: application/json" \
  -d '{"pending_action_id":"...","approved":true,"approved_action":"PARTIAL_PREPAY","session_id":"demo"}'
```

No real payment or customer message is executed in this milestone.

Razorpay Test Mode status:

```bash
curl http://localhost:8000/api/v1/razorpay/status
```

Razorpay Test Mode connectivity:

```bash
curl "http://localhost:8000/api/v1/razorpay/connectivity"
```

Create a developer/demo Razorpay Test Mode order using paise:

```bash
curl -X POST http://localhost:8000/api/v1/razorpay/test-orders \
  -H "Content-Type: application/json" \
  -d '{"amount":10000,"currency":"INR","receipt":"demo-ORD-0042-0009754","internal_order_id":"ORD-0042-0009754"}'
```

Razorpay is disabled by default and accepts only test-mode keys. See `docs/razorpay-test-mode.md`.

Real LLM smoke test:

```bash
LLM_PROVIDER=groq \
LLM_MODEL=<configured-model> \
LLM_API_KEY=<secret> \
.venv/bin/python scripts/agent_smoke_test.py
```

The smoke test makes one real LLM request, verifies that at least one typed tool was exercised, checks that financial values are grounded in tool outputs, and separately verifies the approval gate with the offline provider. Both OpenAI and Groq are interchangeable LLM providers: they orchestrate typed tools while deterministic backend services remain authoritative for financial calculations, recovery economics, policy, approval, execution, and audit. The normal pytest suite does not call external APIs.

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
DATASET_PATH
LOG_LEVEL
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
MAX_AGENT_STEPS
LLM_REQUEST_TIMEOUT_SECONDS
RAZORPAY_ENABLED
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_REQUEST_TIMEOUT_SECONDS
RAZORPAY_TEST_ORDER_ID
```

`DATASET_PATH` resolves the synthetic demo dataset from the project root by default, and the Docker image also includes the dataset at `/app/data/generated/orders.csv`. Use `.env.example` as a safe template. Do not commit `.env`.
