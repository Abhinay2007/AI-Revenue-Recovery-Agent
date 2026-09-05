import pytest

from app.agent.agent import AgentToolset
from app.decision.interventions import InterventionAction
from app.tools.schemas import OrderQueryInput


def test_revenue_summary_matches_order_population():
    tools = AgentToolset()
    frame = tools.order_tool._load()
    summary = tools.merchant_tool.get_revenue_summary()

    cod_count = int((frame["payment_method"] == "COD").sum())
    prepaid_count = int((frame["payment_method"] == "PREPAID").sum())

    assert summary["merchant_id"] == "demo-merchant"
    assert summary["total_orders"] == len(frame)
    assert summary["cod_orders"] == cod_count
    assert summary["prepaid_orders"] == prepaid_count
    assert summary["total_order_value"] == float(frame["amount"].sum())
    assert summary["predicted_revenue_at_risk"] > 0


def test_priority_orders_are_deterministically_ranked_and_limited():
    tools = AgentToolset()

    first = tools.merchant_tool.get_priority_recovery_orders(limit=5, minimum_rto_probability=0.0, minimum_order_value=0.0)
    second = tools.merchant_tool.get_priority_recovery_orders(limit=5, minimum_rto_probability=0.0, minimum_order_value=0.0)

    expected_values = [order["expected_revenue_at_risk"] for order in first["orders"]]
    assert first == second
    assert len(first["orders"]) == 5
    assert expected_values == sorted(expected_values, reverse=True)


def test_priority_orders_apply_risk_and_amount_filters():
    tools = AgentToolset()

    result = tools.merchant_tool.get_priority_recovery_orders(
        limit=50,
        minimum_rto_probability=0.60,
        minimum_order_value=5000,
    )

    assert all(order["rto_probability"] >= 0.60 for order in result["orders"])
    assert all(order["amount"] >= 5000 for order in result["orders"])


def test_default_priority_orders_include_all_eligible_orders():
    tools = AgentToolset()
    result = tools.merchant_tool.get_priority_recovery_orders()
    eligible = [order for order in tools.merchant_tool._scored_cod_orders() if order["rto_probability"] >= 0.30]

    assert result["limit"] == 250
    assert len(result["orders"]) == len(eligible)


def test_priority_orders_default_threshold_is_030():
    tools = AgentToolset()

    result = tools.merchant_tool.get_priority_recovery_orders()

    assert result["minimum_rto_probability"] == 0.30


def test_priority_orders_accept_explicit_threshold():
    tools = AgentToolset()

    result = tools.merchant_tool.get_priority_recovery_orders(minimum_rto_probability=0.50)

    assert result["minimum_rto_probability"] == 0.50
    assert all(order["rto_probability"] >= 0.50 for order in result["orders"])


def test_priority_order_threshold_validation_remains_strict():
    with pytest.raises(ValueError):
        OrderQueryInput(minimum_rto_probability=1.01)
    with pytest.raises(ValueError):
        OrderQueryInput(minimum_rto_probability=-0.01)


def test_recovery_opportunity_summary_matches_underlying_scored_orders():
    tools = AgentToolset()
    scored = tools.merchant_tool._scored_cod_orders()
    positive = [
        order
        for order in scored
        if order["expected_net_recovery"] > 0 and order["recommended_action"] != InterventionAction.NO_ACTION.value
    ]

    summary = tools.merchant_tool.get_recovery_opportunity_summary()

    assert summary["orders_evaluated"] == len(scored)
    assert summary["orders_with_positive_expected_recovery"] == len(positive)
    assert summary["total_revenue_at_risk"] == sum(order["expected_revenue_at_risk"] for order in scored)
    assert summary["expected_gross_recovery"] == sum(order["expected_gross_recovery"] for order in positive)
    assert summary["expected_intervention_cost"] == sum(order["expected_intervention_cost"] for order in positive)
    assert summary["expected_net_recovery"] == sum(order["expected_net_recovery"] for order in positive)


def test_action_distribution_counts_sum_to_evaluated_orders():
    tools = AgentToolset()

    result = tools.merchant_tool.get_recovery_action_distribution()

    assert {row["action"] for row in result["distribution"]} == {action.value for action in InterventionAction}
    assert sum(row["count"] for row in result["distribution"]) == result["orders_evaluated"]
    assert sum(row["percentage"] for row in result["distribution"]) == 1.0
