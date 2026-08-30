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
