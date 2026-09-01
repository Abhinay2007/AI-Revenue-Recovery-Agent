#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402


ORDER_ID = "ORD-0042-0009754"


def fail(message: str) -> int:
    print(f"SMOKE TEST FAILED: {message}", file=sys.stderr)
    return 1


def validate_analysis_response(response) -> None:
    text = response.natural_language_response
    if ORDER_ID not in (response.order_id or text):
        raise AssertionError("response does not include the requested order ID")
    if response.risk is None or "rto_probability" not in response.risk:
        raise AssertionError("response does not include tool-derived risk information")
    if response.revenue_at_risk is None or "expected_revenue_at_risk" not in response.revenue_at_risk:
        raise AssertionError("response does not include tool-derived financial information")
    if response.recommendation is None or "recommended_action" not in response.recommendation:
        raise AssertionError("response does not include tool-derived recovery recommendation")
    if response.execution_status and response.execution_status.get("status") == "SIMULATED_SUCCESS":
        raise AssertionError("analysis request claimed execution")
    if response.approval_required and "Approval required" not in text:
        raise AssertionError("approval requirement is missing from the grounded response")


def run_real_analysis() -> object:
    settings = get_settings()
    if settings.llm_provider not in {"openai", "groq"}:
        raise RuntimeError("Set LLM_PROVIDER=openai or groq for the real smoke test")
    if not settings.llm_api_key:
        raise RuntimeError("Set LLM_API_KEY for the real smoke test")
    if not settings.llm_model or settings.llm_model == "rule-based-recovery-agent":
        raise RuntimeError("Set LLM_MODEL to the configured model")

    from app.agent.agent import RevenueRecoveryAgent
    from app.agent.schemas import AgentChatRequest

    agent = RevenueRecoveryAgent()
    response = agent.chat(
        AgentChatRequest(
            session_id="smoke-real-llm",
            message=(
                f"Analyze order {ORDER_ID}. Tell me its RTO risk, revenue at risk, "
                "recommended recovery action, and why."
            ),
        )
    )
    validate_analysis_response(response)
    if not any(call.get("tool_name") for call in response.tool_calls):
        raise AssertionError("real LLM response did not exercise any typed tool")
    return response


def run_approval_safety_check() -> object:
    from app.agent.agent import AgentToolset, RevenueRecoveryAgent
    from app.agent.provider import LocalRuleBasedProvider
    from app.agent.schemas import AgentApprovalRequest, AgentChatRequest
    from app.agent.state import pending_approval_store

    pending_approval_store.clear()
    agent = RevenueRecoveryAgent(provider=LocalRuleBasedProvider(), tools=AgentToolset())
    recommendation = agent.chat(AgentChatRequest(session_id="smoke-approval", message=f"Recover {ORDER_ID}"))
    if not recommendation.approval_required:
        raise AssertionError("recover request did not create a pending approval")
    if recommendation.execution_status is not None:
        raise AssertionError("recover request executed before approval")

    approval = agent.approve(
        AgentApprovalRequest(
            pending_action_id=recommendation.pending_action_id or "",
            approved=True,
            approved_action=recommendation.recommendation["recommended_action"],
            session_id="smoke-approval",
        )
    )
    if approval.execution_status is None or approval.execution_status.get("status") != "SIMULATED_SUCCESS":
        raise AssertionError("explicit approval did not execute in simulation")
    return approval


def run_provider_failure_check() -> object:
    from app.agent.agent import AgentToolset, RevenueRecoveryAgent
    from app.agent.provider import MockToolCallingProvider
    from app.agent.schemas import AgentChatRequest

    agent = RevenueRecoveryAgent(provider=MockToolCallingProvider(fail=RuntimeError("mock provider failure")), tools=AgentToolset())
    response = agent.chat(AgentChatRequest(session_id="smoke-failure", message=f"Analyze order {ORDER_ID}"))
    if response.status != "FAILED":
        raise AssertionError("provider failure was not surfaced safely")
    if response.execution_status is not None:
        raise AssertionError("provider failure produced execution state")
    return response


def main() -> int:
    try:
        real_response = run_real_analysis()
        approval = run_approval_safety_check()
        failure = run_provider_failure_check()
    except Exception as exc:
        return fail(str(exc))

    print("Real LLM smoke test passed.")
    print(f"Provider/model: {get_settings().llm_provider}/{get_settings().llm_model}")
    print("Tool calls:", ", ".join(call["tool_name"] for call in real_response.tool_calls if "tool_name" in call))
    print("\nGrounded response:\n")
    print(real_response.natural_language_response)
    print("\nApproval safety:")
    print(f"- First recover request required approval: yes")
    print(f"- Approval API execution status: {approval.execution_status['status']}")
    print("\nProvider failure handling:")
    print(f"- {failure.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
