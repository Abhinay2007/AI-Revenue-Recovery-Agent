from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.agent.agent import AgentToolset, RevenueRecoveryAgent
from app.agent.provider import AgentIntent, LocalRuleBasedProvider
from app.agent.schemas import AgentApprovalRequest, AgentChatRequest
from app.agent.state import ApprovalStatus, PendingAction, pending_approval_store
from app.decision.policy import MerchantPolicy


ORDER_ID = "ORD-0042-0000001"
ACTIONABLE_ORDER_ID = "ORD-0042-0009754"


@pytest.fixture(autouse=True)
def clear_pending_store():
    pending_approval_store.clear()
    yield
    pending_approval_store.clear()


def make_agent(**kwargs) -> RevenueRecoveryAgent:
    return RevenueRecoveryAgent(provider=LocalRuleBasedProvider(), tools=AgentToolset(**kwargs))


def test_provider_selects_expected_tools_for_intents():
    provider = LocalRuleBasedProvider()

    assert provider.plan(f"Analyze order {ORDER_ID}").intent == AgentIntent.INSPECT_ORDER
    assert provider.plan(f"What should we do with {ORDER_ID}?").intent == AgentIntent.RECOMMEND_RECOVERY
    assert provider.plan(f"Recover {ORDER_ID}").intent == AgentIntent.REQUEST_EXECUTION
    assert provider.plan("Find today's highest revenue-at-risk COD orders.").intent == AgentIntent.FIND_REVENUE_AT_RISK


def test_agent_analyze_order_returns_tool_numbers_without_execution():
    agent = make_agent()
    response = agent.chat(AgentChatRequest(message=f"Analyze order {ORDER_ID}", session_id="s1"))

    assert response.status == "ANALYSIS"
    assert response.order_id == ORDER_ID
    assert response.risk is not None
    assert response.revenue_at_risk is not None
    assert response.recommendation is not None
    assert response.approval_required is False
    assert response.execution_status is None
    assert f"{response.revenue_at_risk['expected_revenue_at_risk']:.2f}" in response.natural_language_response


def test_agent_recover_requires_approval_and_does_not_execute():
    agent = make_agent()
    response = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s2"))

    assert response.status == "RECOMMENDATION"
    assert response.approval_required is True
    assert response.pending_action_id is not None
    assert response.execution_status is None
    assert "Approval required" in response.natural_language_response


def test_valid_approval_executes_simulated_action_and_audits():
    agent = make_agent()
    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s3"))

    response = agent.approve(
        AgentApprovalRequest(
            pending_action_id=recommendation.pending_action_id or "",
            approved=True,
            approved_action=recommendation.recommendation["recommended_action"],
            session_id="s3",
        )
    )

    assert response.status == "EXECUTED_ACTION"
    assert response.execution_status["status"] == "SIMULATED_SUCCESS"
    assert response.audit_id


def test_invalid_action_id_fails():
    agent = make_agent()
    response = agent.approve(AgentApprovalRequest(pending_action_id="missing", approved=True))

    assert response.status == "FAILED"
    assert "not found" in response.summary


def test_expired_approval_fails():
    pending = PendingAction(
        session_id="s4",
        order_id=ORDER_ID,
        recommended_action="PARTIAL_PREPAY",
        decision={"recommended_action": "PARTIAL_PREPAY"},
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    pending_approval_store.create(pending)
    agent = make_agent()

    response = agent.approve(AgentApprovalRequest(pending_action_id=pending.pending_action_id, approved=True))

    assert response.status == "FAILED"
    assert "expired" in response.summary


def test_mismatched_approval_action_fails():
    agent = make_agent()
    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s5"))

    response = agent.approve(
        AgentApprovalRequest(
            pending_action_id=recommendation.pending_action_id or "",
            approved=True,
            approved_action="ADDRESS_OTP",
        )
    )

    assert response.status == "FAILED"
    assert "does not match" in response.summary


def test_duplicate_approval_does_not_execute_twice():
    agent = make_agent()
    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s6"))
    request = AgentApprovalRequest(
        pending_action_id=recommendation.pending_action_id or "",
        approved=True,
        approved_action=recommendation.recommendation["recommended_action"],
    )

    first = agent.approve(request)
    second = agent.approve(request)

    assert first.execution_status["status"] == "SIMULATED_SUCCESS"
    assert second.status == "FAILED"


def test_policy_changed_after_recommendation_is_rechecked():
    agent = make_agent()
    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s7"))
    agent.tools.recovery_tool.policy = MerchantPolicy(max_intervention_attempts=0)

    response = agent.approve(
        AgentApprovalRequest(
            pending_action_id=recommendation.pending_action_id or "",
            approved=True,
            approved_action=recommendation.recommendation["recommended_action"],
        )
    )

    assert response.status == "FAILED"
    assert response.policy_status is not None
    assert response.policy_status["allowed"] is False


def test_missing_order_is_graceful_failure():
    agent = make_agent()
    response = agent.chat(AgentChatRequest(message="Analyze order ORD-DOES-NOT-EXIST"))

    assert response.status == "FAILED"
    assert "No financial recovery action will be executed" in response.summary


def test_model_failure_is_graceful_and_does_not_execute(tmp_path: Path):
    agent = make_agent(artifact_path=tmp_path / "missing.joblib")
    response = agent.chat(AgentChatRequest(message=f"Recover {ORDER_ID}"))

    assert response.status == "FAILED"
    assert response.execution_status is None
    assert "No financial recovery action will be executed" in response.summary


def test_find_revenue_at_risk_uses_tools_not_raw_llm_scan():
    agent = make_agent()
    response = agent.chat(AgentChatRequest(message="Find today's highest revenue-at-risk COD orders."))

    assert response.status == "ANALYSIS"
    assert "Highest revenue-at-risk COD orders" in response.natural_language_response


def test_execution_tool_blocks_without_explicit_approval():
    agent = make_agent()
    recommendation = agent.chat(AgentChatRequest(message=f"Recover {ACTIONABLE_ORDER_ID}", session_id="s8"))

    result = agent.tools.execution_tool.execute_recovery(recommendation.pending_action_id or "", approved_by_user=False)

    assert result.status == "BLOCKED"
    assert "approval" in result.reason


def test_execution_tool_blocks_exceeded_attempt_limit():
    agent = make_agent()
    decision = agent.tools.recovery_tool.evaluate_recovery(ACTIONABLE_ORDER_ID)
    pending = PendingAction(
        session_id="s9",
        order_id=ACTIONABLE_ORDER_ID,
        recommended_action=decision["recommended_action"],
        decision=decision,
        attempt_count=2,
    )
    pending_approval_store.create(pending)
    agent.tools.recovery_tool.policy = MerchantPolicy(max_intervention_attempts=2)

    result = agent.tools.execution_tool.execute_recovery(pending.pending_action_id, approved_by_user=True)

    assert result.status == "BLOCKED"
