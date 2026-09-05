import pytest

from app.agent.agent import AgentToolset, RevenueRecoveryAgent
from app.agent.provider import LocalRuleBasedProvider, MockToolCallingProvider, ProviderResponse, ProviderToolCall
from app.agent.schemas import AgentChatRequest


ORDER_ID = "ORD-0042-0009754"


def make_agent(provider):
    agent = RevenueRecoveryAgent(provider=provider, tools=AgentToolset())
    agent.max_steps = 8
    return agent


def test_local_agent_answers_revenue_summary_question_with_tool_values():
    agent = RevenueRecoveryAgent(provider=LocalRuleBasedProvider(), tools=AgentToolset())

    response = agent.chat(AgentChatRequest(message="How much revenue is currently at risk?"))

    assert response.intent == "REVENUE_SUMMARY"
    assert response.merchant_summary is not None
    assert str(response.merchant_summary["cod_orders"]) in response.natural_language_response
    assert "Predicted revenue at risk" in response.natural_language_response


def test_mock_llm_selects_revenue_summary_tool():
    provider = MockToolCallingProvider(
        [
            ProviderResponse(tool_calls=[ProviderToolCall(id="1", name="get_revenue_summary", arguments={})]),
            ProviderResponse(final_text="The merchant has made up numbers."),
        ]
    )
    agent = make_agent(provider)

    response = agent.chat(AgentChatRequest(message="How much revenue is currently at risk?"))

    assert response.intent == "REVENUE_SUMMARY"
    assert response.merchant_summary is not None
    assert "made up numbers" not in response.natural_language_response
    assert response.tool_calls[0]["tool_name"] == "get_revenue_summary"


def test_mock_llm_selects_priority_orders_tool():
    provider = MockToolCallingProvider(
        [
            ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        id="1",
                        name="get_priority_recovery_orders",
                        arguments={"limit": 3, "minimum_rto_probability": 0.30, "minimum_order_value": 0},
                    )
                ]
            ),
            ProviderResponse(final_text="Top orders summarized."),
        ]
    )
    agent = make_agent(provider)

    response = agent.chat(AgentChatRequest(message="Which orders should I prioritize?"))

    assert response.intent == "PRIORITY_RECOVERY"
    assert response.priority_orders is not None
    assert len(response.priority_orders["orders"]) <= 3
    assert response.priority_orders["orders"][0]["order_id"] in response.natural_language_response


def test_priority_question_uses_backend_default_without_threshold():
    provider = MockToolCallingProvider(
        [
            ProviderResponse(tool_calls=[ProviderToolCall(id="1", name="get_priority_recovery_orders", arguments={})]),
            ProviderResponse(final_text="Here are the priority orders."),
        ]
    )
    agent = make_agent(provider)

    response = agent.chat(AgentChatRequest(message="Which orders should I prioritize for recovery?"))

    assert response.priority_orders is not None
    assert response.priority_orders["minimum_rto_probability"] == 0.30
    assert response.tool_calls[0]["inputs_summary"]["minimum_rto_probability"] == 0.30


@pytest.mark.parametrize(
    ("message", "model_threshold", "expected_threshold"),
    [
        ("Show orders with at least 50% RTO probability", 0.0, 0.50),
        ("Show all orders regardless of RTO probability", 0.30, 0.0),
    ],
)
def test_priority_threshold_comes_from_explicit_user_request(message, model_threshold, expected_threshold):
    provider = MockToolCallingProvider(
        [
            ProviderResponse(
                tool_calls=[
                    ProviderToolCall(
                        id="1",
                        name="get_priority_recovery_orders",
                        arguments={"limit": 5, "minimum_rto_probability": model_threshold},
                    )
                ]
            ),
            ProviderResponse(final_text="Priority orders."),
        ]
    )
    response = make_agent(provider).chat(AgentChatRequest(message=message))

    assert response.priority_orders["minimum_rto_probability"] == expected_threshold
    assert response.tool_calls[0]["inputs_summary"]["minimum_rto_probability"] == expected_threshold


def test_priority_tool_coerces_numeric_string_threshold_at_tool_boundary():
    agent = make_agent(MockToolCallingProvider())

    result = agent.tools.call_tool(
        "get_priority_recovery_orders",
        {"minimum_rto_probability": "0.50", "minimum_order_value": "0", "limit": 3},
        "session-test",
    )

    assert result["minimum_rto_probability"] == 0.50


def test_priority_tool_normalizes_omitted_and_null_optional_arguments():
    agent = make_agent(MockToolCallingProvider())

    omitted = agent.tools.call_tool("get_priority_recovery_orders", {}, "session-test")
    nulls = agent.tools.call_tool(
        "get_priority_recovery_orders",
        {"limit": None, "minimum_order_value": None, "minimum_rto_probability": None},
        "session-test",
    )

    for result in (omitted, nulls):
        assert result["limit"] == 50
        assert result["minimum_order_value"] == 0.0
        assert result["minimum_rto_probability"] == 0.30


def test_priority_tool_preserves_explicit_zero_threshold():
    agent = make_agent(MockToolCallingProvider())

    result = agent.tools.call_tool(
        "get_priority_recovery_orders",
        {"minimum_rto_probability": 0.0},
        "session-test",
    )

    assert result["minimum_rto_probability"] == 0.0


@pytest.mark.parametrize("threshold", ["not-a-number", -0.01, 1.01])
def test_priority_tool_rejects_invalid_threshold_at_tool_boundary(threshold):
    agent = make_agent(MockToolCallingProvider())

    with pytest.raises(ValueError):
        agent.tools.call_tool(
            "get_priority_recovery_orders",
            {"minimum_rto_probability": threshold},
            "session-test",
        )


def test_mock_llm_order_workflow_still_returns_grounded_numbers():
    provider = MockToolCallingProvider(
        [
            ProviderResponse(tool_calls=[ProviderToolCall(id="1", name="get_order", arguments={"order_id": ORDER_ID})]),
            ProviderResponse(tool_calls=[ProviderToolCall(id="2", name="get_rto_risk", arguments={"order_id": ORDER_ID})]),
            ProviderResponse(tool_calls=[ProviderToolCall(id="3", name="calculate_revenue_at_risk", arguments={"order_id": ORDER_ID})]),
            ProviderResponse(tool_calls=[ProviderToolCall(id="4", name="evaluate_recovery", arguments={"order_id": ORDER_ID})]),
            ProviderResponse(final_text="Revenue at risk is Rs 999999."),
        ]
    )
    agent = make_agent(provider)

    response = agent.chat(AgentChatRequest(message=f"Analyze order {ORDER_ID}"))

    assert response.risk is not None
    assert response.revenue_at_risk is not None
    assert response.recommendation is not None
    assert "999999" not in response.natural_language_response
    assert f"{response.revenue_at_risk['expected_revenue_at_risk']:.2f}" in response.natural_language_response


def test_provider_failure_remains_safe_for_merchant_question():
    agent = make_agent(MockToolCallingProvider(fail=RuntimeError("provider unavailable")))

    response = agent.chat(AgentChatRequest(message="How much revenue is currently at risk?"))

    assert response.status == "FAILED"
    assert response.execution_status is None
    assert "No financial recovery action will be executed" in response.summary
