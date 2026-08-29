from decimal import Decimal

from app.api.routes.recovery import create_recovery_decision
from app.decision.engine import decide_recovery_action
from app.decision.interventions import RecoveryAssumptions
from app.decision.policy import MerchantPolicy
from app.decision.revenue import calculate_revenue_at_risk
from app.schemas.recovery import RecoveryDecisionRequest


def test_revenue_at_risk_calculation():
    result = calculate_revenue_at_risk(Decimal("5000"), Decimal("0.70"))

    assert result.expected_revenue_at_risk == Decimal("3500.00")


def test_intervention_ranking_selects_highest_positive_net_recovery():
    decision = decide_recovery_action(
        order={"order_id": "ORD-1", "amount": Decimal("5000")},
        rto_probability=Decimal("0.70"),
        recovery_assumptions=RecoveryAssumptions(
            otp_success_rate=Decimal("0.10"),
            partial_prepay_success_rate=Decimal("0.60"),
            prepaid_conversion_rate=Decimal("0.20"),
            manual_review_success_rate=Decimal("0.10"),
        ),
    )

    assert decision["recommended_action"] == "PARTIAL_PREPAY"
    assert decision["expected_net_recovery"] == 2080.0


def test_no_action_when_every_intervention_has_non_positive_net_recovery():
    decision = decide_recovery_action(
        order={"order_id": "ORD-2", "amount": Decimal("100")},
        rto_probability=Decimal("0.30"),
        recovery_assumptions=RecoveryAssumptions(
            otp_success_rate=Decimal("0"),
            partial_prepay_success_rate=Decimal("0"),
            prepaid_conversion_rate=Decimal("0"),
            manual_review_success_rate=Decimal("0"),
        ),
    )

    assert decision["recommended_action"] == "NO_ACTION"
    assert "NO_POSITIVE_NET_RECOVERY" in decision["reason_codes"]


def test_partial_prepayment_guardrail_rejects_excess_amount():
    decision = decide_recovery_action(
        order={"order_id": "ORD-3", "amount": Decimal("9000")},
        rto_probability=Decimal("0.80"),
        merchant_policy=MerchantPolicy(max_partial_prepay_amount=Decimal("500")),
    )

    partial = next(candidate for candidate in decision["candidate_actions"] if candidate["action"] == "PARTIAL_PREPAY")

    assert partial["requested_partial_prepay_amount"] == 900.0
    assert partial["permitted"] is False
    assert any(check["name"] == "max_partial_prepay_amount" and not check["passed"] for check in partial["policy_checks"])


def test_discount_guardrail_rejects_excess_discount():
    decision = decide_recovery_action(
        order={"order_id": "ORD-4", "amount": Decimal("3000")},
        rto_probability=Decimal("0.80"),
        merchant_policy=MerchantPolicy(max_discount_percent=Decimal("0.03")),
        recovery_assumptions=RecoveryAssumptions(prepaid_discount_percent=Decimal("0.05")),
    )

    incentive = next(candidate for candidate in decision["candidate_actions"] if candidate["action"] == "PREPAID_INCENTIVE")

    assert incentive["permitted"] is False
    assert any(check["name"] == "max_discount_percent" and not check["passed"] for check in incentive["policy_checks"])


def test_attempt_limit_blocks_interventions():
    decision = decide_recovery_action(
        order={"order_id": "ORD-5", "amount": Decimal("5000"), "attempt_count": 2},
        rto_probability=Decimal("0.80"),
        merchant_policy=MerchantPolicy(max_intervention_attempts=2),
    )

    assert decision["recommended_action"] == "NO_ACTION"
    assert all(
        not candidate["permitted"]
        for candidate in decision["candidate_actions"]
        if candidate["action"] != "NO_ACTION"
    )


def test_high_value_manual_review_policy_is_respected():
    low_value = decide_recovery_action(
        order={"order_id": "ORD-6", "amount": Decimal("5000")},
        rto_probability=Decimal("0.80"),
        merchant_policy=MerchantPolicy(manual_review_order_value_threshold=Decimal("10000")),
    )
    high_value = decide_recovery_action(
        order={"order_id": "ORD-7", "amount": Decimal("12000")},
        rto_probability=Decimal("0.80"),
        merchant_policy=MerchantPolicy(manual_review_order_value_threshold=Decimal("10000")),
    )

    low_manual = next(candidate for candidate in low_value["candidate_actions"] if candidate["action"] == "MANUAL_REVIEW")
    high_manual = next(candidate for candidate in high_value["candidate_actions"] if candidate["action"] == "MANUAL_REVIEW")

    assert low_manual["permitted"] is False
    assert high_manual["permitted"] is True


def test_explanation_contains_actual_values_and_selected_action():
    decision = decide_recovery_action(order={"order_id": "ORD-8", "amount": Decimal("5000")}, rto_probability=Decimal("0.70"))

    assert "70.0%" in decision["reason"]
    assert "Rs 3500.00" in decision["reason"]
    assert decision["recommended_action"] in decision["reason"]


def test_audit_record_is_generated():
    decision = decide_recovery_action(order={"order_id": "ORD-9", "amount": Decimal("5000")}, rto_probability=Decimal("0.70"))

    assert decision["audit_event"]["order_id"] == "ORD-9"
    assert decision["audit_event"]["selected_action"] == decision["recommended_action"]
    assert decision["audit_event"]["assumption_source"] == "synthetic_demo_assumption"


def test_decision_is_deterministic_for_same_inputs():
    first = decide_recovery_action(order={"order_id": "ORD-10", "amount": Decimal("5000")}, rto_probability=Decimal("0.70"))
    second = decide_recovery_action(order={"order_id": "ORD-10", "amount": Decimal("5000")}, rto_probability=Decimal("0.70"))

    first_without_timestamp = {**first, "audit_event": {**first["audit_event"], "timestamp": ""}}
    second_without_timestamp = {**second, "audit_event": {**second["audit_event"], "timestamp": ""}}
    assert first_without_timestamp == second_without_timestamp


def test_recovery_decision_api_route_uses_server_side_defaults():
    response = create_recovery_decision(
        RecoveryDecisionRequest(order_id="ORD-11", amount=Decimal("4999"), rto_probability=Decimal("0.72"))
    )

    assert response["order_id"] == "ORD-11"
    assert response["recommended_action"] in {"ADDRESS_OTP", "PARTIAL_PREPAY", "PREPAID_INCENTIVE", "MANUAL_REVIEW", "NO_ACTION"}
