from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.decision.audit import create_audit_event, json_value
from app.decision.interventions import (
    ASSUMPTION_SOURCE,
    InterventionAction,
    RecoveryAssumptions,
    expected_intervention,
)
from app.decision.policy import MerchantPolicy, evaluate_policy, is_permitted
from app.decision.revenue import calculate_revenue_at_risk


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def reason_codes_for(
    selected_action: InterventionAction,
    rto_probability: Decimal,
    revenue_at_risk: Decimal,
    net_recovery: Decimal,
) -> list[str]:
    reasons: list[str] = []
    if rto_probability >= Decimal("0.50"):
        reasons.append("HIGH_RTO_RISK")
    if revenue_at_risk >= Decimal("3000"):
        reasons.append("HIGH_EXPECTED_REVENUE_AT_RISK")
    if selected_action == InterventionAction.NO_ACTION:
        reasons.append("NO_POSITIVE_NET_RECOVERY" if net_recovery <= 0 else "BELOW_POLICY_INTERVENTION_THRESHOLD")
    elif selected_action == InterventionAction.PARTIAL_PREPAY:
        reasons.append("PARTIAL_PREPAY_HAS_HIGHEST_EXPECTED_NET_RECOVERY")
    elif selected_action == InterventionAction.PREPAID_INCENTIVE:
        reasons.append("PREPAID_INCENTIVE_HAS_HIGHEST_EXPECTED_NET_RECOVERY")
    elif selected_action == InterventionAction.ADDRESS_OTP:
        reasons.append("ADDRESS_OTP_HAS_HIGHEST_EXPECTED_NET_RECOVERY")
    elif selected_action == InterventionAction.MANUAL_REVIEW:
        reasons.append("MANUAL_REVIEW_REQUIRED")
    return reasons


def candidate_to_dict(candidate: dict[str, Any]) -> dict[str, Any]:
    proposal = candidate["proposal"]
    return {
        "action": proposal.action.value,
        "permitted": candidate["permitted"],
        "expected_recovered_revenue": money(proposal.expected_recovered_revenue),
        "expected_intervention_cost": money(proposal.expected_intervention_cost),
        "expected_net_recovery": money(proposal.expected_net_recovery),
        "success_probability": proposal.success_probability,
        "requested_partial_prepay_amount": money(proposal.requested_partial_prepay_amount),
        "discount_percent": proposal.discount_percent,
        "discount_amount": money(proposal.discount_amount),
        "policy_checks": [asdict(check) for check in candidate["policy_checks"]],
        "assumption_source": proposal.assumption_source,
    }


def build_explanation(
    selected_action: InterventionAction,
    rto_probability: Decimal,
    expected_revenue_at_risk: Decimal,
    expected_net_recovery: Decimal,
) -> str:
    if selected_action == InterventionAction.NO_ACTION:
        return (
            f"RTO probability is {percent(rto_probability)}, creating approximately "
            f"Rs {money(expected_revenue_at_risk)} of expected revenue at risk. "
            "No permitted intervention has positive expected net recovery, so NO_ACTION was selected."
        )
    return (
        f"RTO probability is {percent(rto_probability)}, creating approximately "
        f"Rs {money(expected_revenue_at_risk)} of expected revenue at risk. "
        f"{selected_action.value} has the highest expected net recovery among permitted interventions "
        f"at Rs {money(expected_net_recovery)}, so it was selected."
    )


def decide_recovery_action(
    order: dict[str, Any],
    rto_probability: float | Decimal,
    merchant_policy: MerchantPolicy | None = None,
    recovery_assumptions: RecoveryAssumptions | None = None,
) -> dict[str, Any]:
    policy = merchant_policy or MerchantPolicy()
    assumptions = recovery_assumptions or RecoveryAssumptions()
    order_id = str(order["order_id"])
    order_amount = Decimal(str(order["amount"]))
    attempt_count = int(order.get("attempt_count", 0))

    revenue = calculate_revenue_at_risk(order_amount, rto_probability)
    candidates: list[dict[str, Any]] = []
    for action in InterventionAction:
        proposal = expected_intervention(action, revenue.order_amount, revenue.expected_revenue_at_risk, assumptions)
        checks = evaluate_policy(proposal, revenue.order_amount, revenue.rto_probability, attempt_count, policy)
        candidates.append({"proposal": proposal, "policy_checks": checks, "permitted": is_permitted(checks)})

    permitted_candidates = [candidate for candidate in candidates if candidate["permitted"]]
    positive_candidates = [
        candidate
        for candidate in permitted_candidates
        if candidate["proposal"].action != InterventionAction.NO_ACTION
        and candidate["proposal"].expected_net_recovery > Decimal("0")
    ]
    if positive_candidates:
        selected = max(positive_candidates, key=lambda item: item["proposal"].expected_net_recovery)
    else:
        selected = next(candidate for candidate in candidates if candidate["proposal"].action == InterventionAction.NO_ACTION)

    selected_proposal = selected["proposal"]
    candidate_actions = [candidate_to_dict(candidate) for candidate in candidates]
    policy_checks = {
        candidate["proposal"].action.value: [asdict(check) for check in candidate["policy_checks"]]
        for candidate in candidates
    }
    reasons = reason_codes_for(
        selected_proposal.action,
        revenue.rto_probability,
        revenue.expected_revenue_at_risk,
        selected_proposal.expected_net_recovery,
    )

    decision = {
        "order_id": order_id,
        "recommended_action": selected_proposal.action.value,
        "reason": build_explanation(
            selected_proposal.action,
            revenue.rto_probability,
            revenue.expected_revenue_at_risk,
            selected_proposal.expected_net_recovery,
        ),
        "reason_codes": reasons,
        "rto_probability": revenue.rto_probability,
        "order_amount": money(revenue.order_amount),
        "expected_revenue_at_risk": money(revenue.expected_revenue_at_risk),
        "candidate_actions": candidate_actions,
        "expected_recovered_revenue": money(selected_proposal.expected_recovered_revenue),
        "expected_intervention_cost": money(selected_proposal.expected_intervention_cost),
        "expected_net_recovery": money(selected_proposal.expected_net_recovery),
        "policy_checks": policy_checks,
        "assumption_source": ASSUMPTION_SOURCE,
    }
    decision["audit_event"] = create_audit_event(decision)
    return json_value(decision)

