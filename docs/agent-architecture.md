# AI Revenue Recovery Agent Architecture

## Overview

The agent is a lightweight orchestrator over typed tools. It does not own financial calculations, policy decisions, model predictions, or execution authority.

```text
LLM
 ↓
Typed Tools
 ↓
Deterministic Services
 ↓
Policy Gate
 ↓
Execution Adapter
 ↓
Audit
```

## Agent Architecture

The current implementation lives under:

```text
backend/app/agent/
backend/app/tools/
```

The default provider is `local`, a deterministic rule-based planner used for tests and hackathon demos without external model credentials. The provider abstraction supports future hosted, Modal-backed, or local model providers without changing tool implementations.

```text
Merchant/User
      ↓
AI Revenue Recovery Agent
      │
      ├── Order Tool
      ├── RTO Risk Tool
      ├── Revenue-at-Risk Tool
      ├── Recovery Evaluation Tool
      ├── Policy Tool
      ├── Execution Tool
      └── Audit Tool
              │
              ▼
      Existing deterministic services
```

## Tool Architecture

Tools expose strict Pydantic schemas and deterministic behavior where applicable:

- `OrderTool`: retrieves prediction-time order fields from the synthetic dataset.
- `RiskTool`: calls the existing trained RTO predictor artifact.
- `RevenueTool`: calls the deterministic revenue-at-risk calculator.
- `RecoveryTool`: calls the deterministic recovery decision engine.
- `PolicyTool`: rechecks merchant policy for a requested action.
- `SimulatedRecoveryExecutor`: performs safe simulated execution only.
- `AuditTool`: appends JSON-serializable in-memory audit events.

The agent never scans raw CSV content directly to make decisions. It uses tools.

## State

Agent state tracks:

- session ID
- user request
- order ID
- tool calls
- risk result
- revenue result
- recovery result
- policy result
- approval state
- execution result
- audit event

No secrets are stored in agent state.

## Approval Flow

Recovery execution requires explicit approval:

```text
User request
    ↓
Inspect order
    ↓
Risk prediction
    ↓
Recovery evaluation
    ↓
Policy validation
    ↓
Pending action stored server-side
    ↓
User approval with pending_action_id
    ↓
Policy recheck
    ↓
Simulated execution
    ↓
Audit
```

Pending approval state includes:

- pending action ID
- session ID
- order ID
- recommended action
- policy version
- decision snapshot
- created and expiry timestamps
- status

The approval endpoint rejects missing, expired, duplicate, and mismatched approvals.

## Guardrails

The LLM/provider cannot:

- bypass policy
- directly access the database
- directly execute arbitrary code
- directly call payment APIs
- specify arbitrary financial amounts
- modify merchant policy
- modify audit history

All recovery actions go through typed tools and deterministic policy checks.

## Execution Boundary

The current executor is `SimulatedRecoveryExecutor`. It returns:

```text
SIMULATED_SUCCESS
BLOCKED
FAILED
```

It does not call Razorpay, charge customers, create mandates, send WhatsApp messages, send SMS, or contact real customers.

Future adapter shape:

```text
RecoveryExecutor
├── SimulatedRecoveryExecutor
└── RazorpayRecoveryExecutor (future)
```

There is no fake Razorpay implementation in this milestone.

## Audit Trail

Audit events record:

- timestamp
- session ID
- order ID
- actor
- tool/action
- input summary
- output summary
- decision
- approval state
- execution status
- policy result

The current audit store is in-memory. Database persistence can be added later.

## Failure Handling

If order lookup, model prediction, revenue calculation, recovery evaluation, policy validation, or execution fails, the agent returns a structured failure and does not execute recovery actions.

Examples:

- Missing order: no recovery action is executed.
- Risk model unavailable: no recovery action is executed.
- Policy failure: execution is blocked.
- Execution failure: the agent reports failure and never claims success.

## Provider Abstraction

Environment variables:

```text
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
```

Supported shape:

```text
Agent
  ↓
LLMProvider
  ├── HostedProvider (future)
  ├── ModalProvider (future)
  └── LocalRuleBasedProvider
```

The current `HostedProvider` and `ModalProvider` are interfaces/stubs only. They do not spend GPU credits or call external APIs.

## Future Modal Deployment

A future Modal-backed provider can implement the same `LLMProvider.plan()` interface. Tool contracts and deterministic services should remain unchanged so model hosting can evolve independently from financial and policy logic.

## Current Limitations

- Local rule-based provider only.
- No real LLM API call yet.
- No Razorpay integration.
- No real payment execution.
- No customer messaging.
- No frontend.
- No durable pending-action or audit persistence.
- Synthetic dataset and model artifact are used for demo flows.

