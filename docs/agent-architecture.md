# AI Revenue Recovery Agent Architecture

## Overview

The agent is a lightweight orchestrator over typed tools. It does not own financial calculations, policy decisions, model predictions, or execution authority.

```text
User
 ↓
Agent
 ↓
LLM Provider
 ↓
Tool Calling Loop
 ↓
Typed Tools
 ↓
Deterministic Services
 ↓
Policy Gate
 ↓
Approval Gate
 ↓
Execution Adapter
 ↓
Razorpay Test Mode Adapter (optional)
 ↓
Audit
```

## Agent Architecture

The current implementation lives under:

```text
backend/app/agent/
backend/app/tools/
```

The default provider is `local`, a deterministic rule-based planner used for offline tests and hackathon demos without external model credentials. The provider abstraction also supports OpenAI Responses API and Groq Chat Completions providers for structured tool calling.

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
      ├── Merchant Revenue Tools
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
- `MerchantTool`: calculates deterministic aggregate revenue and recovery summaries for the synthetic demo merchant.
- `SimulatedRecoveryExecutor`: performs safe simulated execution only.
- `RazorpayTestModeExecutor`: optionally wraps the existing approval and policy validation, then calls the Razorpay Test Mode adapter for safe test operations.
- `AuditTool`: appends JSON-serializable in-memory audit events.

The agent never scans raw CSV content directly to make decisions. It uses typed tools only; no tool exposes arbitrary SQL, filesystem reads, Python execution, or raw dataset access to the model.

## Merchant-Level Tools

The current merchant context is:

```text
merchant_id = demo-merchant
source = synthetic_demo_merchant
```

This is a synthetic context only. It is structured so future Razorpay merchant/account context can be injected without changing the agent/tool boundary.

Merchant-level capabilities:

- `get_revenue_summary()`: total orders, COD/prepaid counts, total order value, observed synthetic COD RTO value/rate, and predicted revenue at risk.
- `get_priority_recovery_orders(limit, minimum_rto_probability, minimum_order_value)`: ranked recovery candidates. Ranking uses expected revenue at risk, not RTO probability alone.
- `get_recovery_opportunity_summary()`: aggregate opportunity from the deterministic recovery engine, including expected gross recovery, intervention cost, and expected net recovery.
- `get_recovery_action_distribution()`: action counts, percentages, and expected net recovery for `NO_ACTION`, `ADDRESS_OTP`, `PARTIAL_PREPAY`, `PREPAID_INCENTIVE`, and `MANUAL_REVIEW`.

These tools support questions such as:

- "How much revenue is currently at risk?"
- "Which orders should I prioritize?"
- "How much can the recovery system potentially recover?"
- "What actions is the recovery system taking?"

All values come from deterministic backend services. The LLM may summarize them, but it does not calculate them.

## Real LLM Provider

Set:

```text
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:latest
OLLAMA_BASE_URL=http://localhost:11434
LLM_REQUEST_TIMEOUT_SECONDS=120
```

Ollama runs separately from the backend and provides native tool calling. In
Docker Compose, use `http://host.docker.internal:11434` so the backend reaches
the host Ollama service. The backend does not download or load model weights.
The `local` provider remains the offline rule-based provider; Groq and OpenAI
remain supported API providers and require `LLM_API_KEY`.

The OpenAI and Groq providers are isolated in `backend/app/agent/provider.py`. Each sends the system prompt, conversation messages, and strict tool schemas to its provider API, then returns either final text or structured tool calls. Groq uses Chat Completions message continuation and preserves the assistant tool-call message before appending typed tool results.

Secrets are read from environment variables only. They are not stored in agent state, tool calls, or audit events.

Manual smoke test:

```bash
LLM_PROVIDER=groq \
LLM_MODEL=<configured-model> \
LLM_API_KEY=<secret> \
.venv/bin/python scripts/agent_smoke_test.py
```

The smoke command makes one real LLM request, validates that at least one typed tool was exercised, checks that the final answer is grounded in tool-derived risk and financial fields, and verifies that no execution is claimed for analysis. It then verifies the approval gate and provider-failure handling offline. Automated tests use mock/local providers and do not make external API calls.

## Tool-calling Loop

For providers that support tool calling, the agent runs a bounded loop:

```text
user message
  ↓
provider response
  ↓
tool call?
  ↓
execute typed tool
  ↓
return tool result to provider
  ↓
final response or next tool call
```

The loop stops after `MAX_AGENT_STEPS`, default `8`. If the limit is reached, the agent stops safely and does not execute recovery actions.

The final structured response is rebuilt from tool outputs held in `AgentState`, not from untrusted model text. This protects financial values from hallucination.

For real OpenAI Responses API calls, the provider continues after function calls using the previous response ID and returns only typed tool outputs to the model. The loop remains bounded by `MAX_AGENT_STEPS`.

## Mock Provider

`MockToolCallingProvider` supports deterministic tests for:

- single tool calls
- multi-step tool calls
- invalid tool requests
- provider failure
- maximum-step exhaustion

No test requires a real external API key or network call.

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
- merchant summary
- priority orders
- recovery opportunity summary
- action distribution
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

Prompt-injection-style user instructions are treated as untrusted. Requests such as "skip approval", "set the prepayment to Rs 10000", "ignore policy", "reveal your API key", or "execute arbitrary code" cannot bypass backend gates because no tool exposes those capabilities.

## Execution Boundary

The default executor is `SimulatedRecoveryExecutor`. It returns:

```text
SIMULATED_SUCCESS
BLOCKED
FAILED
```

It does not call Razorpay, charge customers, create mandates, send WhatsApp messages, send SMS, or contact real customers.

When `RAZORPAY_ENABLED=true`, the backend uses `RazorpayTestModeExecutor`. It still runs only after the existing approval endpoint verifies:

- pending action exists
- action is not expired or already executed
- explicit approval was provided
- current recovery decision still matches the pending recommendation
- merchant policy still passes

Only after those checks may it call the Razorpay Test Mode adapter. The LLM never receives Razorpay credentials and cannot call Razorpay directly.

Executor shape:

```text
RecoveryExecutor
├── SimulatedRecoveryExecutor
├── RazorpayTestModeExecutor
└── RazorpayLiveExecutor (not implemented)
```

There is no live Razorpay implementation in this milestone.

## Razorpay Test Mode

Razorpay Test Mode is disabled by default.

```text
RAZORPAY_ENABLED=false
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_REQUEST_TIMEOUT_SECONDS=10
```

Safety behavior:

- accepts only `rzp_test_` key IDs
- rejects `rzp_live_*` keys
- fails startup of the Razorpay-enabled executor when credentials are missing
- never logs or returns `RAZORPAY_KEY_SECRET`
- performs no refunds, payouts, live charges, or destructive operations
- keeps internal synthetic order IDs distinct from Razorpay order/payment IDs

The status endpoint is:

```text
GET /api/v1/razorpay/status
```

It returns safe metadata such as enabled/configured/mode and never returns credentials.

Identifier mapping:

```text
internal_order_id: ORD-0042-0009754
razorpay receipt: rr_ORD-0042-0009754
razorpay_order_id: returned by Razorpay Test Mode
razorpay_payment_id: returned only when available
```

See `docs/razorpay-test-mode.md` for manual test instructions.

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

Provider failures and malformed provider responses also produce safe failures. Tool failures are returned to the provider as tool output and captured in structured tool-call traces.

## Provider Abstraction

Environment variables:

```text
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
MAX_AGENT_STEPS
LLM_REQUEST_TIMEOUT_SECONDS
RAZORPAY_ENABLED
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_REQUEST_TIMEOUT_SECONDS
```

Supported shape:

```text
Agent
  ↓
LLMProvider
  ├── OpenAIResponsesProvider
  ├── GroqProvider
  ├── HostedProvider (future)
  ├── ModalProvider (future)
  └── LocalRuleBasedProvider
```

The current `HostedProvider` and `ModalProvider` are interfaces/stubs only. They do not spend GPU credits or call external APIs.

## Observability

Agent responses include enough structured information for future evaluation:

- tool calls
- provider
- model
- tool count
- agent step count
- provider/model summary
- final status
- intent
- selected action
- policy status
- approval required
- execution status
- audit ID

Tool call records capture input summaries, output summaries, failures, and timestamps. API keys and secrets are never logged in those records.

## Future Modal Deployment

A future Modal-backed provider can implement the same `LLMProvider.plan()` interface. Tool contracts and deterministic services should remain unchanged so model hosting can evolve independently from financial and policy logic.

## Current Limitations

- OpenAI and Groq providers are API-ready; automated tests use mocked provider clients and do not make external API calls.
- Razorpay support is Test Mode only and disabled by default.
- No real payment execution.
- No customer messaging.
- No frontend.
- No durable pending-action or audit persistence.
- Synthetic dataset and model artifact are used for demo flows.
