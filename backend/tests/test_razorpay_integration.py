from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.agent.agent import AgentToolset, RevenueRecoveryAgent
from app.agent.provider import LocalRuleBasedProvider
from app.agent.schemas import AgentApprovalRequest, AgentChatRequest
from app.agent.state import PendingAction, pending_approval_store
from app.integrations.razorpay import (
    DemoRazorpayOrderMapper,
    InMemoryRazorpayMappingStore,
    RazorpayAPIError,
    RazorpayConfigurationError,
    RazorpayIdentifierMapping,
    RazorpayMappingError,
    RazorpayTestModeAdapter,
    razorpay_mapping_store,
)
from app.tools.execution_tool import RazorpayTestModeExecutor


ORDER_ID = "ORD-0042-0009754"


class FakeRazorpayResponse:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://api.razorpay.com")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("bad status", request=self.request, response=response)

    def json(self):
        return self.payload


class FakeRazorpayClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response or FakeRazorpayResponse({"id": "order_test_1", "amount": 20000, "currency": "INR", "receipt": "rr_ORDER", "status": "created"})
        self.error = error
        self.requests = []

    def request(self, *args, **kwargs):
        self.requests.append({"args": args, "kwargs": kwargs})
        if self.error:
            raise self.error
        return self.response


@pytest.fixture(autouse=True)
def clear_pending_store():
    pending_approval_store.clear()
    razorpay_mapping_store.clear()
    yield
    pending_approval_store.clear()
    razorpay_mapping_store.clear()


def test_razorpay_disabled_fails_safely_without_credentials():
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_hidden", key_secret="hidden", enabled=False)

    assert adapter.status()["enabled"] is False
    assert adapter.status()["key_id_prefix"] is None
    with pytest.raises(RazorpayConfigurationError, match="disabled"):
        adapter.fetch_order("order_test")


def test_razorpay_enabled_requires_credentials():
    with pytest.raises(RazorpayConfigurationError, match="credentials are missing"):
        RazorpayTestModeAdapter(key_id="", key_secret="", enabled=True)


def test_razorpay_rejects_live_keys():
    with pytest.raises(RazorpayConfigurationError, match="Live Razorpay keys"):
        RazorpayTestModeAdapter(key_id="rzp_live_bad", key_secret="secret", enabled=True)


def test_razorpay_accepts_test_key_and_never_exposes_secret_in_status():
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="super-secret", enabled=True)

    status = adapter.status()

    assert status == {"enabled": True, "mode": "test", "configured": True, "key_id_prefix": "rzp_test"}
    assert "super-secret" not in str(status)


def test_razorpay_adapter_creates_test_order_with_internal_mapping():
    mapping_store = InMemoryRazorpayMappingStore()
    client = FakeRazorpayClient()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client, mapping_store=mapping_store)

    result = adapter.create_test_order(ORDER_ID, Decimal("200.00"))

    request = client.requests[0]
    assert request["args"][:2] == ("POST", "https://api.razorpay.com/v1/orders")
    assert request["kwargs"]["auth"] == ("rzp_test_123", "secret")
    assert request["kwargs"]["json"]["amount"] == 20000
    assert request["kwargs"]["json"]["receipt"] == DemoRazorpayOrderMapper.receipt_for_internal_order(ORDER_ID)
    assert request["kwargs"]["json"]["notes"]["internal_order_id"] == ORDER_ID
    assert result["internal_order_id"] == ORDER_ID
    assert result["razorpay_order_id"] == "order_test_1"
    assert mapping_store.get(ORDER_ID).razorpay_order_id == "order_test_1"
    assert mapping_store.get(ORDER_ID).receipt == "rr_ORDER"


def test_razorpay_adapter_creates_test_order_from_paise_without_internal_mapping():
    mapping_store = InMemoryRazorpayMappingStore()
    client = FakeRazorpayClient()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client, mapping_store=mapping_store)

    result = adapter.create_test_order_from_paise(amount_paise=50000, currency="INR", receipt="demo-receipt")

    assert result["amount"] == 20000
    assert result["internal_order_id"] is None
    assert mapping_store.get(ORDER_ID) is None
    assert client.requests[0]["kwargs"]["json"]["amount"] == 50000
    assert client.requests[0]["kwargs"]["json"]["receipt"] == "demo-receipt"


def test_razorpay_adapter_rejects_invalid_test_order_amount():
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=FakeRazorpayClient())

    with pytest.raises(RazorpayConfigurationError, match="amount must be positive"):
        adapter.create_test_order_from_paise(amount_paise=0, currency="INR", receipt="bad")


def test_razorpay_adapter_fetches_order_and_payment():
    client = FakeRazorpayClient(FakeRazorpayResponse({"id": "order_test_1"}))
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)

    assert adapter.fetch_order("order_test_1") == {"id": "order_test_1"}
    adapter.fetch_payment("pay_test_1")

    assert client.requests[0]["args"][:2] == ("GET", "https://api.razorpay.com/v1/orders/order_test_1")
    assert client.requests[1]["args"][:2] == ("GET", "https://api.razorpay.com/v1/payments/pay_test_1")


def test_razorpay_mapping_lookup_and_fetch_mapped_order():
    mapping_store = InMemoryRazorpayMappingStore()
    mapping_store.save(RazorpayIdentifierMapping(internal_order_id=ORDER_ID, razorpay_order_id="order_test_1", receipt="receipt"))
    client = FakeRazorpayClient(FakeRazorpayResponse({"id": "order_test_1", "amount": 10000, "currency": "INR", "receipt": "receipt", "status": "created"}))
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client, mapping_store=mapping_store)

    assert adapter.get_mapping(ORDER_ID)["razorpay_order_id"] == "order_test_1"
    result = adapter.fetch_order_for_internal_order(ORDER_ID)

    assert result["internal_order_id"] == ORDER_ID
    assert result["mapping"]["razorpay_order_id"] == "order_test_1"
    assert result["razorpay_order"]["id"] == "order_test_1"


def test_razorpay_mapping_not_found_and_wrong_order_rejected():
    mapping_store = InMemoryRazorpayMappingStore()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=FakeRazorpayClient(), mapping_store=mapping_store)

    with pytest.raises(RazorpayMappingError, match="mapping_not_found"):
        adapter.get_mapping(ORDER_ID)

    mapping_store.save(RazorpayIdentifierMapping(internal_order_id=ORDER_ID, razorpay_order_id="order_expected"))
    wrong_client = FakeRazorpayClient(FakeRazorpayResponse({"id": "order_other", "amount": 10000, "currency": "INR", "status": "created"}))
    wrong_adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=wrong_client, mapping_store=mapping_store)

    with pytest.raises(RazorpayMappingError, match="did not match"):
        wrong_adapter.fetch_order_for_internal_order(ORDER_ID)


def test_razorpay_api_failure_and_timeout_are_safe_errors():
    adapter = RazorpayTestModeAdapter(
        key_id="rzp_test_123",
        key_secret="secret",
        enabled=True,
        client=FakeRazorpayClient(FakeRazorpayResponse({"error": "bad"}, status_code=500)),
    )
    with pytest.raises(RazorpayAPIError, match="HTTP 500"):
        adapter.fetch_order("order_test")

    timeout_adapter = RazorpayTestModeAdapter(
        key_id="rzp_test_123",
        key_secret="secret",
        enabled=True,
        client=FakeRazorpayClient(error=httpx.TimeoutException("slow")),
    )
    with pytest.raises(TimeoutError, match="timed out"):
        timeout_adapter.fetch_order("order_test")


def test_razorpay_connectivity_lists_orders_for_auth_check():
    client = FakeRazorpayClient(FakeRazorpayResponse({"items": []}))
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)

    result = adapter.check_connectivity()

    assert result["reachable"] is True
    assert result["authentication_successful"] is True
    assert result["requested_test_resource_found"] is None
    assert result["operation"] == "list_orders"
    assert client.requests[0]["args"][:2] == ("GET", "https://api.razorpay.com/v1/orders")
    assert client.requests[0]["kwargs"]["params"] == {"count": 1}
    assert "secret" not in str(result)


def test_razorpay_connectivity_fetches_requested_order():
    client = FakeRazorpayClient(FakeRazorpayResponse({"id": "order_test_1"}))
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)

    result = adapter.check_connectivity("order_test_1")

    assert result["reachable"] is True
    assert result["authentication_successful"] is True
    assert result["requested_test_resource_found"] is True
    assert result["operation"] == "fetch_order"
    assert result["razorpay_order_id_checked"] == "order_test_1"


def test_razorpay_connectivity_distinguishes_auth_failure_and_missing_resource():
    auth_client = FakeRazorpayClient(FakeRazorpayResponse({"error": "unauthorized"}, status_code=401))
    auth_adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=auth_client)

    auth_result = auth_adapter.check_connectivity()

    assert auth_result["reachable"] is True
    assert auth_result["authentication_successful"] is False
    assert auth_result["error_type"] == "authentication"
    assert "secret" not in str(auth_result)

    missing_client = FakeRazorpayClient(FakeRazorpayResponse({"error": "not found"}, status_code=404))
    missing_adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=missing_client)

    missing_result = missing_adapter.check_connectivity("order_missing")

    assert missing_result["reachable"] is True
    assert missing_result["authentication_successful"] is True
    assert missing_result["requested_test_resource_found"] is False
    assert missing_result["error_type"] == "not_found"


def test_razorpay_connectivity_reports_timeout_without_fabricating_auth_success():
    adapter = RazorpayTestModeAdapter(
        key_id="rzp_test_123",
        key_secret="secret",
        enabled=True,
        client=FakeRazorpayClient(error=httpx.TimeoutException("slow")),
    )

    result = adapter.check_connectivity()

    assert result["reachable"] is False
    assert result["authentication_successful"] is False
    assert result["error_type"] == "timeout"


def test_razorpay_executor_blocks_before_approval_without_api_call():
    tools = AgentToolset()
    client = FakeRazorpayClient()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)
    executor = RazorpayTestModeExecutor(tools.order_tool, tools.policy_tool, adapter)
    decision = tools.recovery_tool.evaluate_recovery(ORDER_ID)
    pending = PendingAction(
        session_id="rzp-denied",
        order_id=ORDER_ID,
        recommended_action=decision["recommended_action"],
        decision=decision,
    )
    pending_approval_store.create(pending)

    result = executor.execute_recovery(pending.pending_action_id, approved_by_user=False)

    assert result.status == "BLOCKED"
    assert client.requests == []


def test_razorpay_executor_runs_after_explicit_approval():
    tools = AgentToolset()
    client = FakeRazorpayClient()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)
    executor = RazorpayTestModeExecutor(tools.order_tool, tools.policy_tool, adapter)
    decision = tools.recovery_tool.evaluate_recovery(ORDER_ID)
    pending = PendingAction(
        session_id="rzp-approved",
        order_id=ORDER_ID,
        recommended_action=decision["recommended_action"],
        decision=decision,
    )
    pending_approval_store.create(pending)

    result = executor.execute_recovery(pending.pending_action_id, approved_by_user=True)

    assert result.status == "SIMULATED_SUCCESS"
    assert result.razorpay is not None
    assert result.razorpay["internal_order_id"] == ORDER_ID
    assert result.razorpay["mode"] == "test"


def test_agent_approval_audits_razorpay_test_execution():
    tools = AgentToolset()
    client = FakeRazorpayClient()
    adapter = RazorpayTestModeAdapter(key_id="rzp_test_123", key_secret="secret", enabled=True, client=client)
    tools.execution_tool = RazorpayTestModeExecutor(tools.order_tool, tools.policy_tool, adapter)
    agent = RevenueRecoveryAgent(provider=LocalRuleBasedProvider(), tools=tools)

    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ORDER_ID}", session_id="rzp-agent"))
    approval = agent.approve(
        AgentApprovalRequest(
            pending_action_id=recommendation.pending_action_id or "",
            approved=True,
            approved_action=recommendation.recommendation["recommended_action"],
            session_id="rzp-agent",
        )
    )

    assert approval.execution_status["status"] == "SIMULATED_SUCCESS"
    assert approval.execution_status["razorpay"]["mode"] == "test"
    assert tools.audit_tool.events[-1]["execution_status"] == "SIMULATED_SUCCESS"
    assert "secret" not in str(approval.model_dump())


def test_razorpay_status_endpoint_never_returns_credentials(monkeypatch):
    monkeypatch.setenv("RAZORPAY_ENABLED", "true")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_123")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "super-secret")
    from app.core.config import get_settings
    from app.api.routes.razorpay import razorpay_status

    get_settings.cache_clear()
    status = razorpay_status()
    get_settings.cache_clear()

    assert status["configured"] is True
    assert "super-secret" not in str(status)


def test_create_test_order_endpoint_returns_safe_response(monkeypatch):
    from app.api.routes import razorpay as razorpay_route

    class FakeAdapter:
        @classmethod
        def from_settings(cls, settings):
            return cls()

        def create_test_order_from_paise(self, **kwargs):
            return {
                "mode": "test",
                "internal_order_id": kwargs["internal_order_id"],
                "razorpay_order_id": "order_test_created",
                "receipt": kwargs["receipt"],
                "amount": kwargs["amount_paise"],
                "currency": kwargs["currency"],
                "status": "created",
            }

    monkeypatch.setattr(razorpay_route, "RazorpayTestModeAdapter", FakeAdapter)
    request = razorpay_route.RazorpayTestOrderRequest(
        amount=50000,
        currency="INR",
        receipt="demo-ORD-0042-0009754",
        internal_order_id=ORDER_ID,
    )

    result = razorpay_route.create_razorpay_test_order(request)

    assert result["created"] is True
    assert result["mode"] == "test"
    assert result["razorpay_order_id"] == "order_test_created"
    assert result["mapping_created"] is True
    assert "secret" not in str(result).lower()


def test_create_test_order_endpoint_handles_configuration_error(monkeypatch):
    from app.api.routes import razorpay as razorpay_route

    class FakeAdapter:
        @classmethod
        def from_settings(cls, settings):
            raise RazorpayConfigurationError("Razorpay Test Mode integration is disabled")

    monkeypatch.setattr(razorpay_route, "RazorpayTestModeAdapter", FakeAdapter)
    request = razorpay_route.RazorpayTestOrderRequest(amount=10000, currency="INR")

    result = razorpay_route.create_razorpay_test_order(request)

    assert result["created"] is False
    assert result["error_type"] == "configuration"
    assert result["razorpay_order_id"] is None


def test_fetch_mapped_order_endpoint_returns_mapping_or_not_found(monkeypatch):
    from app.api.routes import razorpay as razorpay_route

    class FakeAdapter:
        @classmethod
        def from_settings(cls, settings):
            return cls()

        def fetch_order_for_internal_order(self, internal_order_id):
            if internal_order_id == "missing":
                raise RazorpayMappingError("mapping_not_found: missing")
            return {
                "mode": "test",
                "internal_order_id": internal_order_id,
                "mapping": {"internal_order_id": internal_order_id, "razorpay_order_id": "order_test_1"},
                "razorpay_order": {"id": "order_test_1", "amount": 10000, "currency": "INR", "status": "created"},
            }

    monkeypatch.setattr(razorpay_route, "RazorpayTestModeAdapter", FakeAdapter)

    found = razorpay_route.fetch_razorpay_test_order_for_internal_order(ORDER_ID)
    missing = razorpay_route.fetch_razorpay_test_order_for_internal_order("missing")

    assert found["found"] is True
    assert found["mapping"]["razorpay_order_id"] == "order_test_1"
    assert missing["found"] is False
    assert missing["error_type"] == "mapping_not_found"


def test_razorpay_connectivity_endpoint_uses_env_order_id_and_hides_secret(monkeypatch):
    monkeypatch.setenv("RAZORPAY_ENABLED", "true")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_123")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "super-secret")
    monkeypatch.setenv("RAZORPAY_TEST_ORDER_ID", "order_from_env")

    from app.api.routes import razorpay as razorpay_route
    from app.core.config import get_settings

    class FakeAdapter:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_settings(cls, settings):
            return cls()

        def check_connectivity(self, razorpay_order_id=None):
            return {
                "enabled": True,
                "mode": "test",
                "configured": True,
                "reachable": True,
                "authentication_successful": True,
                "requested_test_resource_found": True,
                "operation": "fetch_order",
                "razorpay_order_id_checked": razorpay_order_id,
                "error_type": None,
                "error": None,
            }

    monkeypatch.setattr(razorpay_route, "RazorpayTestModeAdapter", FakeAdapter)
    get_settings.cache_clear()
    result = razorpay_route.razorpay_connectivity()
    get_settings.cache_clear()

    assert result["razorpay_order_id_checked"] == "order_from_env"
    assert "super-secret" not in str(result)
