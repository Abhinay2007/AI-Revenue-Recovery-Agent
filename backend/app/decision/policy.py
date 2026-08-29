from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.decision.interventions import InterventionAction, InterventionProposal


@dataclass(frozen=True)
class MerchantPolicy:
    max_partial_prepay_amount: Decimal = Decimal("500")
    max_discount_percent: Decimal = Decimal("0.10")
    max_intervention_attempts: int = 2
    manual_review_order_value_threshold: Decimal = Decimal("10000")
    minimum_rto_probability_for_intervention: Decimal = Decimal("0.30")


@dataclass(frozen=True)
class PolicyCheck:
    name: str
    passed: bool
    reason: str


def evaluate_policy(
    proposal: InterventionProposal,
    order_amount: Decimal,
    rto_probability: Decimal,
    attempt_count: int,
    policy: MerchantPolicy,
) -> list[PolicyCheck]:
    checks = [
        PolicyCheck(
            name="minimum_rto_probability_for_intervention",
            passed=proposal.action == InterventionAction.NO_ACTION
            or rto_probability >= policy.minimum_rto_probability_for_intervention,
            reason="intervention allowed only when RTO probability meets policy minimum",
        ),
        PolicyCheck(
            name="max_intervention_attempts",
            passed=proposal.action == InterventionAction.NO_ACTION or attempt_count < policy.max_intervention_attempts,
            reason="intervention attempts must be below merchant limit",
        ),
    ]

    if proposal.action == InterventionAction.PARTIAL_PREPAY:
        checks.append(
            PolicyCheck(
                name="max_partial_prepay_amount",
                passed=proposal.requested_partial_prepay_amount <= policy.max_partial_prepay_amount,
                reason="requested partial prepayment must not exceed merchant maximum",
            )
        )

    if proposal.action == InterventionAction.PREPAID_INCENTIVE:
        checks.append(
            PolicyCheck(
                name="max_discount_percent",
                passed=proposal.discount_percent <= policy.max_discount_percent,
                reason="discount percent must not exceed merchant maximum",
            )
        )

    if proposal.action == InterventionAction.MANUAL_REVIEW:
        checks.append(
            PolicyCheck(
                name="manual_review_order_value_threshold",
                passed=order_amount >= policy.manual_review_order_value_threshold,
                reason="manual review is reserved for high-value orders",
            )
        )

    return checks


def is_permitted(checks: list[PolicyCheck]) -> bool:
    return all(check.passed for check in checks)

