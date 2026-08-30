from decimal import Decimal

from app.decision.policy import MerchantPolicy
from app.tools.audit_tool import AuditTool
from app.tools.order_tool import OrderTool
from app.tools.policy_tool import PolicyTool
from app.tools.recovery_tool import RecoveryTool
from app.tools.revenue_tool import RevenueTool
from app.tools.risk_tool import RiskTool


ORDER_ID = "ORD-0042-0000001"


def test_order_tool_retrieves_prediction_time_fields_only():
    order = OrderTool().get_order(ORDER_ID)

    assert order.order_id == ORDER_ID
    assert order.payment_method in {"COD", "PREPAID"}
    assert not hasattr(order, "rto_outcome")
    assert not hasattr(order, "order_status")


def test_risk_tool_uses_existing_predictor():
    order_tool = OrderTool()
    risk = RiskTool(order_tool).get_rto_risk(ORDER_ID)

    assert 0 <= risk.rto_probability <= 1
    assert risk.risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert risk.reasons


def test_revenue_tool_uses_deterministic_revenue_calculation():
    order_tool = OrderTool()
    risk_tool = RiskTool(order_tool)
    revenue = RevenueTool(order_tool, risk_tool).calculate_revenue_at_risk(ORDER_ID)

    assert revenue.expected_revenue_at_risk == revenue.order_amount * revenue.rto_probability


def test_recovery_tool_returns_authoritative_decision():
    order_tool = OrderTool()
    risk_tool = RiskTool(order_tool)
    decision = RecoveryTool(order_tool, risk_tool).evaluate_recovery(ORDER_ID)

    assert decision["recommended_action"] in {"NO_ACTION", "ADDRESS_OTP", "PARTIAL_PREPAY", "PREPAID_INCENTIVE", "MANUAL_REVIEW"}
    assert decision["candidate_actions"]


def test_policy_tool_reports_blocked_action():
    order_tool = OrderTool()
    risk_tool = RiskTool(order_tool)
    recovery_tool = RecoveryTool(
        order_tool,
        risk_tool,
        policy=MerchantPolicy(max_partial_prepay_amount=Decimal("1")),
    )
    policy = PolicyTool(recovery_tool).check_recovery_policy(ORDER_ID, "PARTIAL_PREPAY")

    assert policy.allowed is False
    assert "max_partial_prepay_amount" in policy.violations


def test_audit_tool_creates_append_only_event():
    audit_tool = AuditTool()
    event = audit_tool.create_audit_event(
        session_id="session-1",
        order_id=ORDER_ID,
        tool="test",
        inputs_summary={"x": 1},
        outputs_summary={"y": 2},
    )

    assert event["actor"] == "agent"
    assert event["audit_id"]
    assert audit_tool.events == [event]

