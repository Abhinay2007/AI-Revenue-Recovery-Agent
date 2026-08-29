from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.decision.engine import decide_recovery_action
from app.decision.interventions import InterventionAction, RecoveryAssumptions
from app.decision.policy import MerchantPolicy


@dataclass(frozen=True)
class SimulationSummary:
    orders: int
    rto_orders: int
    revenue_at_risk: float
    interventions_attempted: int
    successful_recoveries: int
    gross_recovered_revenue: float
    intervention_cost: float
    net_recovered_revenue: float
    recovery_rate: float
    intervention_rate: float
    cost_per_recovered_order: float
    false_intervention_rate: float


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def risk_probability_for_record(record: dict[str, Any]) -> Decimal:
    if "rto_probability" in record and record["rto_probability"] not in {"", None}:
        return Decimal(str(record["rto_probability"]))
    return Decimal(str(record.get("pincode_rto_rate", "0.30")))


def success_probability_for_action(action: str, assumptions: RecoveryAssumptions) -> Decimal:
    return assumptions.success_rate_for(InterventionAction(action))


def simulate_recovery(
    records: list[dict[str, Any]],
    seed: int = 42,
    policy: MerchantPolicy | None = None,
    assumptions: RecoveryAssumptions | None = None,
) -> SimulationSummary:
    rng = random.Random(seed)
    active_policy = policy or MerchantPolicy()
    active_assumptions = assumptions or RecoveryAssumptions()

    orders = 0
    rto_orders = 0
    revenue_at_risk = Decimal("0")
    interventions_attempted = 0
    successful_recoveries = 0
    gross_recovered = Decimal("0")
    intervention_cost = Decimal("0")
    false_interventions = 0

    for record in records:
        if record.get("payment_method") != "COD":
            continue
        orders += 1
        amount = Decimal(str(record["amount"]))
        actual_rto = record.get("rto_outcome") == "RTO"
        if actual_rto:
            rto_orders += 1
            revenue_at_risk += amount

        decision = decide_recovery_action(
            order={"order_id": record["order_id"], "amount": amount, "attempt_count": int(record.get("attempt_count", 0))},
            rto_probability=risk_probability_for_record(record),
            merchant_policy=active_policy,
            recovery_assumptions=active_assumptions,
        )
        if decision["recommended_action"] == InterventionAction.NO_ACTION.value:
            continue

        interventions_attempted += 1
        intervention_cost += Decimal(str(decision["expected_intervention_cost"]))
        if not actual_rto:
            false_interventions += 1

        success_probability = success_probability_for_action(decision["recommended_action"], active_assumptions)
        if actual_rto and rng.random() < float(success_probability):
            successful_recoveries += 1
            gross_recovered += amount

    net_recovered = gross_recovered - intervention_cost
    return SimulationSummary(
        orders=orders,
        rto_orders=rto_orders,
        revenue_at_risk=float(revenue_at_risk),
        interventions_attempted=interventions_attempted,
        successful_recoveries=successful_recoveries,
        gross_recovered_revenue=float(gross_recovered),
        intervention_cost=float(intervention_cost),
        net_recovered_revenue=float(net_recovered),
        recovery_rate=successful_recoveries / rto_orders if rto_orders else 0.0,
        intervention_rate=interventions_attempted / orders if orders else 0.0,
        cost_per_recovered_order=float(intervention_cost / successful_recoveries) if successful_recoveries else 0.0,
        false_intervention_rate=false_interventions / interventions_attempted if interventions_attempted else 0.0,
    )


def baseline_no_recovery(records: list[dict[str, Any]]) -> SimulationSummary:
    cod_records = [record for record in records if record.get("payment_method") == "COD"]
    rto_records = [record for record in cod_records if record.get("rto_outcome") == "RTO"]
    revenue_at_risk = sum(Decimal(str(record["amount"])) for record in rto_records)
    return SimulationSummary(
        orders=len(cod_records),
        rto_orders=len(rto_records),
        revenue_at_risk=float(revenue_at_risk),
        interventions_attempted=0,
        successful_recoveries=0,
        gross_recovered_revenue=0.0,
        intervention_cost=0.0,
        net_recovered_revenue=0.0,
        recovery_rate=0.0,
        intervention_rate=0.0,
        cost_per_recovered_order=0.0,
        false_intervention_rate=0.0,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate synthetic recovery-engine outcomes.")
    parser.add_argument("--dataset", type=Path, default=Path("data/generated/orders.csv"))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.dataset)
    baseline = baseline_no_recovery(records)
    recovery = simulate_recovery(records, seed=args.seed)
    print("Synthetic outcomes only. These are not real merchant results.")
    print(f"baseline: {baseline}")
    print(f"recovery_engine: {recovery}")


if __name__ == "__main__":
    main()

