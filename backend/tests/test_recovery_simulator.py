from decimal import Decimal

from app.decision.interventions import RecoveryAssumptions
from evaluation.recovery_simulator import baseline_no_recovery, simulate_recovery


def sample_records():
    return [
        {
            "order_id": "ORD-1",
            "amount": "1000",
            "payment_method": "COD",
            "rto_probability": "0.80",
            "rto_outcome": "RTO",
        },
        {
            "order_id": "ORD-2",
            "amount": "2000",
            "payment_method": "COD",
            "rto_probability": "0.80",
            "rto_outcome": "DELIVERED",
        },
        {
            "order_id": "ORD-3",
            "amount": "500",
            "payment_method": "PREPAID",
            "rto_probability": "0.80",
            "rto_outcome": "RTO",
        },
    ]


def test_baseline_calculation():
    baseline = baseline_no_recovery(sample_records())

    assert baseline.orders == 2
    assert baseline.rto_orders == 1
    assert baseline.revenue_at_risk == 1000.0
    assert baseline.net_recovered_revenue == 0.0


def test_simulator_is_deterministic_with_seed():
    assumptions = RecoveryAssumptions(partial_prepay_success_rate=Decimal("1.0"))

    first = simulate_recovery(sample_records(), seed=7, assumptions=assumptions)
    second = simulate_recovery(sample_records(), seed=7, assumptions=assumptions)

    assert first == second


def test_recovery_calculation_costs_revenue_and_batch_aggregation():
    assumptions = RecoveryAssumptions(
        otp_success_rate=Decimal("0"),
        partial_prepay_success_rate=Decimal("1.0"),
        prepaid_conversion_rate=Decimal("0"),
        manual_review_success_rate=Decimal("0"),
        partial_prepay_cost=Decimal("20"),
    )

    summary = simulate_recovery(sample_records(), seed=1, assumptions=assumptions)

    assert summary.orders == 2
    assert summary.interventions_attempted == 2
    assert summary.successful_recoveries == 1
    assert summary.gross_recovered_revenue == 1000.0
    assert summary.intervention_cost == 40.0
    assert summary.net_recovered_revenue == 960.0
    assert summary.false_intervention_rate == 0.5

