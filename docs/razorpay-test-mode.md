# Razorpay Test Mode Integration

This project supports Razorpay Test Mode only. No real money is processed.

## Environment

```text
RAZORPAY_ENABLED=false
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_REQUEST_TIMEOUT_SECONDS=10
RAZORPAY_TEST_ORDER_ID=
```

Razorpay is disabled by default. To enable the adapter locally, use Razorpay test credentials:

```text
RAZORPAY_ENABLED=true
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=<secret>
RAZORPAY_TEST_ORDER_ID=<optional-razorpay-test-order-id>
```

Live keys such as `rzp_live_*` are rejected. Secrets are never returned by API responses and must not be committed.

## Architecture

```text
Analyze order
 ↓
RTO Risk
 ↓
Revenue at Risk
 ↓
Recovery Decision
 ↓
Merchant Approval
 ↓
Razorpay Test Mode Adapter
 ↓
Test Operation
 ↓
Audit
```

The LLM never calls Razorpay directly. It can only request existing typed backend tools. Razorpay calls happen only after the backend approval endpoint verifies a pending action, current decision match, merchant policy, and explicit approval.

## Identifier Mapping

Synthetic internal order IDs, for example `ORD-0042-0009754`, are not Razorpay order IDs.

For demo test orders, the adapter creates a deterministic Razorpay receipt:

```text
internal_order_id = ORD-0042-0009754
receipt = rr_ORD-0042-0009754
```

Adapter outputs distinguish:

- `internal_order_id`
- `razorpay_order_id`
- `razorpay_payment_id`
- `receipt`

The current mapping store is in-memory and intended for local demo validation only. Durable mapping persistence is future work.

## API

Status endpoint:

```bash
curl http://localhost:8000/api/v1/razorpay/status
```

Example response:

```json
{
  "enabled": true,
  "mode": "test",
  "configured": true,
  "key_id_prefix": "rzp_test"
}
```

Credentials are never returned.

Connectivity endpoint:

```bash
curl "http://localhost:8000/api/v1/razorpay/connectivity"
```

With a known Razorpay Test Mode order:

```bash
curl "http://localhost:8000/api/v1/razorpay/connectivity?razorpay_order_id=order_test_..."
```

If no order ID is supplied, the endpoint performs a safe read-only `list_orders` check with `count=1`. If an order ID is supplied, it performs a safe read-only `fetch_order` check. The response distinguishes:

- credentials configured
- Razorpay Test Mode reachable
- authentication successful
- requested test resource found
- API/network/configuration failure

No API secret, Authorization header, or credential value is returned.

Create a Razorpay Test Mode order:

```bash
curl -X POST http://localhost:8000/api/v1/razorpay/test-orders \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 10000,
    "currency": "INR",
    "receipt": "demo-ORD-0042-0009754",
    "internal_order_id": "ORD-0042-0009754"
  }'
```

Razorpay expects `amount` in the smallest currency unit. For INR, Rs 100 is `10000` paise.

Example safe response:

```json
{
  "mode": "test",
  "created": true,
  "internal_order_id": "ORD-0042-0009754",
  "razorpay_order_id": "order_...",
  "receipt": "demo-ORD-0042-0009754",
  "amount": 10000,
  "currency": "INR",
  "status": "created",
  "mapping_created": true
}
```

Fetch a Razorpay Test Mode order through the internal-order mapping:

```bash
curl http://localhost:8000/api/v1/razorpay/test-orders/internal/ORD-0042-0009754
```

If no mapping exists, the API returns `found=false` with `error_type=mapping_not_found`. It never substitutes an unrelated Razorpay order.

## Manual Test Flow

1. Configure Razorpay Test Mode credentials in `.env`.
2. Start the backend:

```bash
docker compose up --build
```

3. Request recovery:

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Recover ORD-0042-0009754","session_id":"rzp-demo"}'
```

The response should include a `pending_action_id` and `approval_required=true`. Razorpay is not called yet.

4. Approve the pending action:

```bash
curl -X POST http://localhost:8000/api/v1/agent/approve \
  -H "Content-Type: application/json" \
  -d '{"pending_action_id":"<pending-action-id>","approved":true,"approved_action":"PARTIAL_PREPAY","session_id":"rzp-demo"}'
```

Only after this approval can the backend adapter create a Razorpay Test Mode order for an action that requires it.

## One-Shot Local Connectivity Check

Without starting the API server, you can validate the adapter from the repository root:

```bash
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "backend")
from app.core.config import get_settings
from app.integrations.razorpay import RazorpayTestModeAdapter

settings = get_settings()
adapter = RazorpayTestModeAdapter.from_settings(settings)
print(adapter.check_connectivity(settings.razorpay_test_order_id))
PY
```

This command reads local environment variables and prints only the safe connectivity result.

## Safety

- Disabled by default.
- Requires `rzp_test_` key IDs.
- Rejects live keys.
- No refunds, payouts, live charges, or destructive operations.
- Bounded request timeout.
- Clear distinction between internal order IDs and Razorpay IDs.
- Existing deterministic financial logic remains authoritative.
- Existing approval and policy gates remain authoritative.
- Audit events include Razorpay test execution summaries, not secrets.

## Tests

Unit tests mock all Razorpay API calls:

```bash
.venv/bin/pytest backend/tests/test_razorpay_integration.py
```

The full pytest suite does not call the real Razorpay API.
