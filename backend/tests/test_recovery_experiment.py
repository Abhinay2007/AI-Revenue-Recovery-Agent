from decimal import Decimal

import pandas as pd

from app.decision.interventions import RecoveryAssumptions
from app.ml.rto_predictor import RiskThresholds
from evaluation import recovery_experiment
from evaluation.recovery_experiment import (
    action_distribution,
    aggregate_metrics,
    run_treatment_outcomes,
    scaled_assumptions,
    sensitivity_analysis,
    threshold_analysis,
)


def experiment_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"order_id": "ORD-1", "amount": "1000", "rto_outcome": "RTO"},
            {"order_id": "ORD-2", "amount": "2000", "rto_outcome": "DELIVERED"},
            {"order_id": "ORD-3", "amount": "12000", "rto_outcome": "RTO"},
        ]
    )


def test_experiment_reproducibility_same_seed():
    probabilities = [0.8, 0.8, 0.8]
    thresholds = RiskThresholds()
    assumptions = RecoveryAssumptions(partial_prepay_success_rate=Decimal("1"))

    first = run_treatment_outcomes(experiment_frame(), probabilities, thresholds, seed=42, assumptions=assumptions)
    second = run_treatment_outcomes(experiment_frame(), probabilities, thresholds, seed=42, assumptions=assumptions)

    assert first == second


def test_baseline_fields_are_zero_in_aggregate_metrics():
    outcomes = run_treatment_outcomes(experiment_frame(), [0.1, 0.1, 0.1], RiskThresholds(), seed=42)
    metrics = aggregate_metrics(outcomes)

    assert metrics.baseline_gross_recovery == 0
    assert metrics.baseline_intervention_cost == 0
    assert metrics.baseline_net_recovery == 0


def test_treatment_uses_decision_engine(monkeypatch):
    calls = {"count": 0}
    original = recovery_experiment.decide_recovery_action

    def wrapped(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(recovery_experiment, "decide_recovery_action", wrapped)

    run_treatment_outcomes(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=42)

    assert calls["count"] == 3


def test_decision_generation_does_not_receive_actual_rto_outcome(monkeypatch):
    original = recovery_experiment.decide_recovery_action

    def wrapped(order, *args, **kwargs):
        assert "rto_outcome" not in order
        return original(order, *args, **kwargs)

    monkeypatch.setattr(recovery_experiment, "decide_recovery_action", wrapped)

    run_treatment_outcomes(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=42)


def test_aggregation_totals_equal_order_level_sums():
    outcomes = run_treatment_outcomes(
        experiment_frame(),
        [0.8, 0.8, 0.8],
        RiskThresholds(),
        seed=1,
        assumptions=RecoveryAssumptions(partial_prepay_success_rate=Decimal("1")),
    )
    metrics = aggregate_metrics(outcomes)

    assert metrics.treatment_gross_recovery == sum(row.gross_recovered_revenue for row in outcomes)
    assert metrics.treatment_intervention_cost == sum(row.intervention_cost for row in outcomes)
    assert metrics.treatment_net_recovery == sum(row.net_recovered_revenue for row in outcomes)


def test_recovery_and_intervention_rate_denominators():
    outcomes = run_treatment_outcomes(
        experiment_frame(),
        [0.8, 0.8, 0.8],
        RiskThresholds(),
        seed=1,
        assumptions=RecoveryAssumptions(partial_prepay_success_rate=Decimal("1")),
    )
    metrics = aggregate_metrics(outcomes)

    assert metrics.recovery_rate == metrics.successful_recoveries / metrics.actual_rto_orders
    assert metrics.intervention_rate == metrics.interventions_attempted / metrics.total_orders


def test_net_recovery_is_gross_minus_cost():
    outcomes = run_treatment_outcomes(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=1)
    metrics = aggregate_metrics(outcomes)

    assert metrics.treatment_net_recovery == metrics.treatment_gross_recovery - metrics.treatment_intervention_cost


def test_sensitivity_scaling_clamps_probabilities():
    base = RecoveryAssumptions(otp_success_rate=Decimal("0.90"))
    optimistic = scaled_assumptions(base, Decimal("1.25"))
    conservative = scaled_assumptions(base, Decimal("0.75"))

    assert optimistic.otp_success_rate == Decimal("1")
    assert conservative.otp_success_rate == Decimal("0.6750")


def test_sensitivity_analysis_returns_expected_scenarios():
    rows = sensitivity_analysis(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=1)

    assert [row["scenario"] for row in rows] == ["CONSERVATIVE", "BASE", "OPTIMISTIC"]


def test_threshold_analysis_produces_valid_metrics():
    rows = threshold_analysis(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=1)

    assert {row["threshold"] for row in rows} == {0.2, 0.3, 0.4, 0.5, 0.6, 0.7}
    assert all(0 <= row["intervention_rate"] <= 1 for row in rows)
    assert all(0 <= row["false_intervention_rate"] <= 1 for row in rows)


def test_action_distribution_counts_sum_to_orders():
    outcomes = run_treatment_outcomes(experiment_frame(), [0.8, 0.8, 0.8], RiskThresholds(), seed=1)
    rows = action_distribution(outcomes)

    assert sum(row["count"] for row in rows) == len(outcomes)

