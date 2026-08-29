from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.decision.engine import decide_recovery_action
from app.decision.interventions import InterventionAction, RecoveryAssumptions
from app.decision.policy import MerchantPolicy
from app.ml.data import filter_cod_orders, load_orders_csv, temporal_split
from app.ml.features import build_feature_frame
from app.ml.rto_predictor import RiskThresholds, assign_risk_level

DEFAULT_DATASET_PATH = Path("data/generated/orders.csv")
DEFAULT_ARTIFACT_PATH = Path("data/generated/models/rto_predictor.joblib")
DEFAULT_JSON_REPORT_PATH = Path("evaluation/reports/recovery_experiment.json")
DEFAULT_MARKDOWN_REPORT_PATH = Path("evaluation/reports/recovery_experiment.md")


@dataclass(frozen=True)
class ExperimentConfig:
    dataset_path: Path = DEFAULT_DATASET_PATH
    artifact_path: Path = DEFAULT_ARTIFACT_PATH
    json_report_path: Path = DEFAULT_JSON_REPORT_PATH
    markdown_report_path: Path = DEFAULT_MARKDOWN_REPORT_PATH
    seed: int = 42


@dataclass(frozen=True)
class OrderExperimentOutcome:
    order_id: str
    amount: float
    actual_rto: bool
    predicted_rto_probability: float
    predicted_revenue_at_risk: float
    risk_level: str
    selected_action: str
    intervention_attempted: bool
    intervention_succeeded: bool
    successful_recovered_rto_order: bool
    gross_recovered_revenue: float
    intervention_cost: float
    net_recovered_revenue: float
    policy_blocked_actions: int
    guardrail_trigger_count: int


@dataclass(frozen=True)
class StrategyMetrics:
    total_orders: int
    total_order_value: float
    actual_rto_orders: int
    actual_rto_value: float
    baseline_gross_recovery: float
    baseline_intervention_cost: float
    baseline_net_recovery: float
    treatment_gross_recovery: float
    treatment_intervention_cost: float
    treatment_net_recovery: float
    incremental_gross_recovery: float
    incremental_net_recovery: float
    incremental_net_recovery_per_order: float
    total_predicted_revenue_at_risk: float
    targeted_revenue_at_risk: float
    targeting_rate: float
    intervention_rate: float
    interventions_attempted: int
    successful_recoveries: int
    recovery_rate: float
    recovery_success_rate: float
    cost_per_successful_recovery: float
    cost_per_rupee_recovered: float
    false_intervention_count: int
    interventions_on_actual_rto_orders: int
    false_intervention_rate: float
    policy_blocked_actions: int
    guardrail_trigger_count: int
    orders_sent_to_manual_review: int
    orders_with_no_action: int


def decimal_float(value: Decimal | float | int) -> float:
    return float(value)


def load_evaluation_population(dataset_path: Path = DEFAULT_DATASET_PATH) -> pd.DataFrame:
    dataset = load_orders_csv(dataset_path)
    cod_dataset = filter_cod_orders(dataset)
    return temporal_split(cod_dataset).test.reset_index(drop=True)


def predict_rto_probabilities(frame: pd.DataFrame, artifact_path: Path = DEFAULT_ARTIFACT_PATH) -> tuple[list[float], RiskThresholds]:
    if not artifact_path.exists():
        raise FileNotFoundError(f"model artifact not found: {artifact_path}")
    artifact = joblib.load(artifact_path)
    features = build_feature_frame(frame)
    raw_probabilities = artifact["pipeline"].predict_proba(features)[:, 1]
    probabilities = artifact["calibrator"].predict_proba(raw_probabilities.reshape(-1, 1))[:, 1]
    thresholds = RiskThresholds(**artifact.get("risk_thresholds", {}))
    return [float(value) for value in probabilities], thresholds


def failed_policy_counts(decision: dict[str, Any]) -> tuple[int, int]:
    blocked_actions = 0
    failed_checks = 0
    for candidate in decision["candidate_actions"]:
        if not candidate["permitted"]:
            blocked_actions += 1
        failed_checks += sum(1 for check in candidate["policy_checks"] if not check["passed"])
    return blocked_actions, failed_checks


def run_treatment_outcomes(
    evaluation_frame: pd.DataFrame,
    probabilities: list[float],
    thresholds: RiskThresholds,
    seed: int,
    policy: MerchantPolicy | None = None,
    assumptions: RecoveryAssumptions | None = None,
) -> list[OrderExperimentOutcome]:
    if len(evaluation_frame) != len(probabilities):
        raise ValueError("evaluation_frame and probabilities must have the same length")

    rng = random.Random(seed)
    active_policy = policy or MerchantPolicy()
    active_assumptions = assumptions or RecoveryAssumptions()
    outcomes: list[OrderExperimentOutcome] = []

    for (_, record), probability in zip(evaluation_frame.iterrows(), probabilities, strict=True):
        amount = Decimal(str(record["amount"]))
        decision_order = {"order_id": record["order_id"], "amount": amount, "attempt_count": int(record.get("attempt_count", 0))}
        decision = decide_recovery_action(
            order=decision_order,
            rto_probability=Decimal(str(probability)),
            merchant_policy=active_policy,
            recovery_assumptions=active_assumptions,
        )
        selected_action = decision["recommended_action"]
        attempted = selected_action != InterventionAction.NO_ACTION.value
        intervention_succeeded = False
        actual_rto = record["rto_outcome"] == "RTO"
        gross_recovered = Decimal("0")
        intervention_cost = Decimal(str(decision["expected_intervention_cost"])) if attempted else Decimal("0")

        if attempted:
            success_probability = active_assumptions.success_rate_for(InterventionAction(selected_action))
            intervention_succeeded = rng.random() < float(success_probability)
            if intervention_succeeded and actual_rto:
                gross_recovered = Decimal(str(decision["expected_recovered_revenue"]))

        blocked_actions, failed_checks = failed_policy_counts(decision)
        net_recovered = gross_recovered - intervention_cost
        outcomes.append(
            OrderExperimentOutcome(
                order_id=str(record["order_id"]),
                amount=decimal_float(amount),
                actual_rto=actual_rto,
                predicted_rto_probability=float(probability),
                predicted_revenue_at_risk=float(decision["expected_revenue_at_risk"]),
                risk_level=assign_risk_level(float(probability), thresholds),
                selected_action=selected_action,
                intervention_attempted=attempted,
                intervention_succeeded=intervention_succeeded,
                successful_recovered_rto_order=bool(intervention_succeeded and actual_rto),
                gross_recovered_revenue=decimal_float(gross_recovered),
                intervention_cost=decimal_float(intervention_cost),
                net_recovered_revenue=decimal_float(net_recovered),
                policy_blocked_actions=blocked_actions,
                guardrail_trigger_count=failed_checks,
            )
        )
    return outcomes


def aggregate_metrics(outcomes: list[OrderExperimentOutcome]) -> StrategyMetrics:
    total_orders = len(outcomes)
    total_order_value = sum(row.amount for row in outcomes)
    actual_rto_orders = sum(1 for row in outcomes if row.actual_rto)
    actual_rto_value = sum(row.amount for row in outcomes if row.actual_rto)
    treatment_gross = sum(row.gross_recovered_revenue for row in outcomes)
    treatment_cost = sum(row.intervention_cost for row in outcomes)
    treatment_net = sum(row.net_recovered_revenue for row in outcomes)
    interventions_attempted = sum(1 for row in outcomes if row.intervention_attempted)
    successful_recoveries = sum(1 for row in outcomes if row.successful_recovered_rto_order)
    false_intervention_count = sum(1 for row in outcomes if row.intervention_attempted and not row.actual_rto)
    interventions_on_actual_rto_orders = sum(1 for row in outcomes if row.intervention_attempted and row.actual_rto)
    total_predicted_risk = sum(row.predicted_revenue_at_risk for row in outcomes)
    targeted_risk = sum(row.predicted_revenue_at_risk for row in outcomes if row.intervention_attempted)

    return StrategyMetrics(
        total_orders=total_orders,
        total_order_value=total_order_value,
        actual_rto_orders=actual_rto_orders,
        actual_rto_value=actual_rto_value,
        baseline_gross_recovery=0.0,
        baseline_intervention_cost=0.0,
        baseline_net_recovery=0.0,
        treatment_gross_recovery=treatment_gross,
        treatment_intervention_cost=treatment_cost,
        treatment_net_recovery=treatment_net,
        incremental_gross_recovery=treatment_gross,
        incremental_net_recovery=treatment_net,
        incremental_net_recovery_per_order=treatment_net / total_orders if total_orders else 0.0,
        total_predicted_revenue_at_risk=total_predicted_risk,
        targeted_revenue_at_risk=targeted_risk,
        targeting_rate=targeted_risk / total_predicted_risk if total_predicted_risk else 0.0,
        intervention_rate=interventions_attempted / total_orders if total_orders else 0.0,
        interventions_attempted=interventions_attempted,
        successful_recoveries=successful_recoveries,
        recovery_rate=successful_recoveries / actual_rto_orders if actual_rto_orders else 0.0,
        recovery_success_rate=successful_recoveries / interventions_attempted if interventions_attempted else 0.0,
        cost_per_successful_recovery=treatment_cost / successful_recoveries if successful_recoveries else 0.0,
        cost_per_rupee_recovered=treatment_cost / treatment_gross if treatment_gross else 0.0,
        false_intervention_count=false_intervention_count,
        interventions_on_actual_rto_orders=interventions_on_actual_rto_orders,
        false_intervention_rate=false_intervention_count / interventions_attempted if interventions_attempted else 0.0,
        policy_blocked_actions=sum(row.policy_blocked_actions for row in outcomes),
        guardrail_trigger_count=sum(row.guardrail_trigger_count for row in outcomes),
        orders_sent_to_manual_review=sum(1 for row in outcomes if row.selected_action == InterventionAction.MANUAL_REVIEW.value),
        orders_with_no_action=sum(1 for row in outcomes if row.selected_action == InterventionAction.NO_ACTION.value),
    )


def action_distribution(outcomes: list[OrderExperimentOutcome]) -> list[dict[str, Any]]:
    total = len(outcomes)
    rows: list[dict[str, Any]] = []
    for action in InterventionAction:
        action_rows = [row for row in outcomes if row.selected_action == action.value]
        gross = sum(row.gross_recovered_revenue for row in action_rows)
        cost = sum(row.intervention_cost for row in action_rows)
        rows.append(
            {
                "action": action.value,
                "count": len(action_rows),
                "percentage": len(action_rows) / total if total else 0.0,
                "gross_recovery": gross,
                "intervention_cost": cost,
                "net_recovery": gross - cost,
            }
        )
    return rows


def risk_band_analysis(outcomes: list[OrderExperimentOutcome]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for risk_level in ["LOW", "MEDIUM", "HIGH"]:
        band = [row for row in outcomes if row.risk_level == risk_level]
        rows.append(
            {
                "risk_band": risk_level,
                "orders": len(band),
                "actual_rto_rate": sum(row.actual_rto for row in band) / len(band) if band else 0.0,
                "average_predicted_rto_probability": sum(row.predicted_rto_probability for row in band) / len(band) if band else 0.0,
                "interventions": sum(row.intervention_attempted for row in band),
                "successful_recoveries": sum(row.successful_recovered_rto_order for row in band),
                "net_recovery": sum(row.net_recovered_revenue for row in band),
            }
        )
    return rows


def order_value_bucket(amount: float) -> str:
    if amount < 1000:
        return "< Rs 1000"
    if amount < 2500:
        return "Rs 1000-Rs 2500"
    if amount < 5000:
        return "Rs 2500-Rs 5000"
    if amount < 10000:
        return "Rs 5000-Rs 10000"
    return "> Rs 10000"


def order_value_analysis(outcomes: list[OrderExperimentOutcome]) -> list[dict[str, Any]]:
    buckets = ["< Rs 1000", "Rs 1000-Rs 2500", "Rs 2500-Rs 5000", "Rs 5000-Rs 10000", "> Rs 10000"]
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        bucket_rows = [row for row in outcomes if order_value_bucket(row.amount) == bucket]
        rows.append(
            {
                "order_value_bucket": bucket,
                "orders": len(bucket_rows),
                "rto_rate": sum(row.actual_rto for row in bucket_rows) / len(bucket_rows) if bucket_rows else 0.0,
                "revenue_at_risk": sum(row.amount for row in bucket_rows if row.actual_rto),
                "interventions": sum(row.intervention_attempted for row in bucket_rows),
                "net_recovery": sum(row.net_recovered_revenue for row in bucket_rows),
            }
        )
    return rows


def scaled_assumptions(base: RecoveryAssumptions, multiplier: Decimal) -> RecoveryAssumptions:
    def clamp(value: Decimal) -> Decimal:
        return max(Decimal("0"), min(Decimal("1"), value * multiplier))

    return RecoveryAssumptions(
        otp_success_rate=clamp(base.otp_success_rate),
        partial_prepay_success_rate=clamp(base.partial_prepay_success_rate),
        prepaid_conversion_rate=clamp(base.prepaid_conversion_rate),
        manual_review_success_rate=clamp(base.manual_review_success_rate),
        address_otp_cost=base.address_otp_cost,
        partial_prepay_cost=base.partial_prepay_cost,
        prepaid_incentive_cost=base.prepaid_incentive_cost,
        manual_review_cost=base.manual_review_cost,
        partial_prepay_percent=base.partial_prepay_percent,
        prepaid_discount_percent=base.prepaid_discount_percent,
    )


def sensitivity_analysis(
    evaluation_frame: pd.DataFrame,
    probabilities: list[float],
    thresholds: RiskThresholds,
    seed: int,
) -> list[dict[str, Any]]:
    base = RecoveryAssumptions()
    scenarios = {
        "CONSERVATIVE": Decimal("0.75"),
        "BASE": Decimal("1.00"),
        "OPTIMISTIC": Decimal("1.25"),
    }
    rows: list[dict[str, Any]] = []
    for name, multiplier in scenarios.items():
        outcomes = run_treatment_outcomes(
            evaluation_frame,
            probabilities,
            thresholds,
            seed,
            assumptions=scaled_assumptions(base, multiplier),
        )
        metrics = aggregate_metrics(outcomes)
        rows.append(
            {
                "scenario": name,
                "gross_recovery": metrics.treatment_gross_recovery,
                "intervention_cost": metrics.treatment_intervention_cost,
                "net_recovery": metrics.treatment_net_recovery,
                "incremental_net_recovery": metrics.incremental_net_recovery,
            }
        )
    return rows


def threshold_analysis(
    evaluation_frame: pd.DataFrame,
    probabilities: list[float],
    thresholds: RiskThresholds,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for threshold in [0.20, 0.30, 0.40, 0.50, 0.60, 0.70]:
        policy = MerchantPolicy(minimum_rto_probability_for_intervention=Decimal(str(threshold)))
        outcomes = run_treatment_outcomes(evaluation_frame, probabilities, thresholds, seed, policy=policy)
        metrics = aggregate_metrics(outcomes)
        rows.append(
            {
                "threshold": threshold,
                "intervention_rate": metrics.intervention_rate,
                "successful_recoveries": metrics.successful_recoveries,
                "gross_recovery": metrics.treatment_gross_recovery,
                "cost": metrics.treatment_intervention_cost,
                "net_recovery": metrics.treatment_net_recovery,
                "false_intervention_rate": metrics.false_intervention_rate,
            }
        )
    return rows


def format_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    headers = list(rows[0].keys())
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        output.append("| " + " | ".join(format_number(row[header]) for header in headers) + " |")
    return "\n".join(output)


def write_reports(
    json_path: Path,
    markdown_path: Path,
    metrics: StrategyMetrics,
    action_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    value_rows: list[dict[str, Any]],
    sensitivity_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    seed: int,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "seed": seed,
        "metrics": asdict(metrics),
        "action_distribution": action_rows,
        "risk_band_analysis": risk_rows,
        "order_value_analysis": value_rows,
        "sensitivity_analysis": sensitivity_rows,
        "threshold_analysis": threshold_rows,
        "notes": {
            "primary_metric": "incremental_net_recovery",
            "data_warning": "ALL RESULTS ARE SIMULATED USING SYNTHETIC DATA AND SYNTHETIC INTERVENTION ASSUMPTIONS.",
            "no_leakage": "actual rto_outcome is not used for decision generation; it is used only after decisions for evaluation.",
        },
    }
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    economic_rows = [
        {
            "Metric": "Gross recovery",
            "Baseline": metrics.baseline_gross_recovery,
            "Recovery Policy": metrics.treatment_gross_recovery,
            "Increment": metrics.incremental_gross_recovery,
        },
        {
            "Metric": "Intervention cost",
            "Baseline": metrics.baseline_intervention_cost,
            "Recovery Policy": metrics.treatment_intervention_cost,
            "Increment": metrics.treatment_intervention_cost - metrics.baseline_intervention_cost,
        },
        {
            "Metric": "Net recovery",
            "Baseline": metrics.baseline_net_recovery,
            "Recovery Policy": metrics.treatment_net_recovery,
            "Increment": metrics.incremental_net_recovery,
        },
    ]

    markdown_path.write_text(
        f"""# Recovery Experiment Report

## Executive Summary

ALL RESULTS ARE SIMULATED USING SYNTHETIC DATA AND SYNTHETIC INTERVENTION ASSUMPTIONS.

- Baseline net recovery: {metrics.baseline_net_recovery:.2f}
- Treatment net recovery: {metrics.treatment_net_recovery:.2f}
- Incremental net revenue recovered: {metrics.incremental_net_recovery:.2f}
- Intervention rate: {metrics.intervention_rate:.4f}
- Recovery rate: {metrics.recovery_rate:.4f}

## Dataset

- Number of evaluated orders: {metrics.total_orders}
- COD orders: {metrics.total_orders}
- RTO orders: {metrics.actual_rto_orders}
- RTO rate: {(metrics.actual_rto_orders / metrics.total_orders if metrics.total_orders else 0):.4f}
- Total order value: {metrics.total_order_value:.2f}

## Experimental Design

Baseline is `NO RECOVERY AGENT`: no intervention, no intervention cost, and no recovered revenue from intervention.

Treatment is `RTO predictor -> revenue at risk -> decision engine -> selected intervention -> simulated outcome`.

Both strategies use the same COD held-out evaluation population. Decision generation uses order features, predicted RTO probability, merchant policy, and recovery assumptions. It does not use actual `rto_outcome`; that field is used only afterward for evaluation. Random intervention outcomes use fixed seed `{seed}`.

## Economic Results

{markdown_table(economic_rows)}

Primary metric: **INCREMENTAL NET REVENUE RECOVERED = treatment_net_recovery - baseline_net_recovery**.

## Revenue-at-Risk Coverage

- Total predicted revenue at risk: {metrics.total_predicted_revenue_at_risk:.2f}
- Targeted revenue at risk: {metrics.targeted_revenue_at_risk:.2f}
- Targeting rate: {metrics.targeting_rate:.4f}

## Action Distribution

{markdown_table(action_rows)}

## Risk-band Analysis

Recovery rate denominator is actual RTO orders. Intervention success rate denominator is attempted interventions.

{markdown_table(risk_rows)}

## Order-value Analysis

{markdown_table(value_rows)}

## False Intervention Analysis

False intervention count means interventions on orders that would have been delivered. False intervention rate denominator is attempted interventions.

- Interventions on orders that would have been delivered: {metrics.false_intervention_count}
- Interventions on actual RTO orders: {metrics.interventions_on_actual_rto_orders}
- False intervention rate: {metrics.false_intervention_rate:.4f}

## Guardrail Results

- Policy blocked actions: {metrics.policy_blocked_actions}
- Guardrail trigger count: {metrics.guardrail_trigger_count}
- Orders sent to manual review: {metrics.orders_sent_to_manual_review}
- Orders with no action: {metrics.orders_with_no_action}

## Sensitivity Analysis

{markdown_table(sensitivity_rows)}

## Threshold Analysis

{markdown_table(threshold_rows)}

## Limitations

- Synthetic dataset
- Synthetic intervention probabilities
- Synthetic intervention costs
- Simulated recovery outcomes
- No real merchant data
- No real customer behavior measurement
- No real payment execution
- No real messaging
- ML model has moderate predictive performance
- Recovery estimates are not real-world revenue claims
""",
        encoding="utf-8",
    )


def run_experiment(config: ExperimentConfig = ExperimentConfig()) -> dict[str, Any]:
    evaluation_frame = load_evaluation_population(config.dataset_path)
    probabilities, risk_thresholds = predict_rto_probabilities(evaluation_frame, config.artifact_path)
    outcomes = run_treatment_outcomes(evaluation_frame, probabilities, risk_thresholds, config.seed)
    metrics = aggregate_metrics(outcomes)
    action_rows = action_distribution(outcomes)
    risk_rows = risk_band_analysis(outcomes)
    value_rows = order_value_analysis(outcomes)
    sensitivity_rows = sensitivity_analysis(evaluation_frame, probabilities, risk_thresholds, config.seed)
    threshold_rows = threshold_analysis(evaluation_frame, probabilities, risk_thresholds, config.seed)
    write_reports(
        config.json_report_path,
        config.markdown_report_path,
        metrics,
        action_rows,
        risk_rows,
        value_rows,
        sensitivity_rows,
        threshold_rows,
        config.seed,
    )
    return {
        "metrics": metrics,
        "action_distribution": action_rows,
        "risk_band_analysis": risk_rows,
        "order_value_analysis": value_rows,
        "sensitivity_analysis": sensitivity_rows,
        "threshold_analysis": threshold_rows,
        "outcomes": outcomes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic recovery policy experiment.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT_PATH)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT_PATH)
    parser.add_argument("--markdown-report", type=Path, default=DEFAULT_MARKDOWN_REPORT_PATH)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_experiment(
        ExperimentConfig(
            dataset_path=args.dataset,
            artifact_path=args.artifact,
            json_report_path=args.json_report,
            markdown_report_path=args.markdown_report,
            seed=args.seed,
        )
    )
    metrics = result["metrics"]
    print("ALL RESULTS ARE SIMULATED USING SYNTHETIC DATA AND SYNTHETIC INTERVENTION ASSUMPTIONS.")
    print(f"evaluated orders: {metrics.total_orders}")
    print(f"baseline net recovery: {metrics.baseline_net_recovery:.2f}")
    print(f"treatment net recovery: {metrics.treatment_net_recovery:.2f}")
    print(f"incremental net revenue recovered: {metrics.incremental_net_recovery:.2f}")
    print(f"intervention rate: {metrics.intervention_rate:.4f}")
    print(f"recovery rate: {metrics.recovery_rate:.4f}")
    print(f"false intervention rate: {metrics.false_intervention_rate:.4f}")
    print(f"json report: {args.json_report}")
    print(f"markdown report: {args.markdown_report}")


if __name__ == "__main__":
    main()

