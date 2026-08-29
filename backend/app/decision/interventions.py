from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class InterventionAction(StrEnum):
    NO_ACTION = "NO_ACTION"
    ADDRESS_OTP = "ADDRESS_OTP"
    PARTIAL_PREPAY = "PARTIAL_PREPAY"
    PREPAID_INCENTIVE = "PREPAID_INCENTIVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


ASSUMPTION_SOURCE = "synthetic_demo_assumption"


@dataclass(frozen=True)
class RecoveryAssumptions:
    otp_success_rate: Decimal = Decimal("0.18")
    partial_prepay_success_rate: Decimal = Decimal("0.38")
    prepaid_conversion_rate: Decimal = Decimal("0.30")
    manual_review_success_rate: Decimal = Decimal("0.25")
    address_otp_cost: Decimal = Decimal("12")
    partial_prepay_cost: Decimal = Decimal("20")
    prepaid_incentive_cost: Decimal = Decimal("8")
    manual_review_cost: Decimal = Decimal("75")
    partial_prepay_percent: Decimal = Decimal("0.10")
    prepaid_discount_percent: Decimal = Decimal("0.05")

    def success_rate_for(self, action: InterventionAction) -> Decimal:
        return {
            InterventionAction.NO_ACTION: Decimal("0"),
            InterventionAction.ADDRESS_OTP: self.otp_success_rate,
            InterventionAction.PARTIAL_PREPAY: self.partial_prepay_success_rate,
            InterventionAction.PREPAID_INCENTIVE: self.prepaid_conversion_rate,
            InterventionAction.MANUAL_REVIEW: self.manual_review_success_rate,
        }[action]


@dataclass(frozen=True)
class InterventionProposal:
    action: InterventionAction
    expected_recovered_revenue: Decimal
    expected_intervention_cost: Decimal
    expected_net_recovery: Decimal
    success_probability: Decimal
    requested_partial_prepay_amount: Decimal = Decimal("0")
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    assumption_source: str = ASSUMPTION_SOURCE


def expected_intervention(
    action: InterventionAction,
    order_amount: Decimal,
    expected_revenue_at_risk: Decimal,
    assumptions: RecoveryAssumptions,
) -> InterventionProposal:
    success_probability = assumptions.success_rate_for(action)
    expected_recovered = expected_revenue_at_risk * success_probability

    if action == InterventionAction.NO_ACTION:
        cost = Decimal("0")
        partial_amount = Decimal("0")
        discount_percent = Decimal("0")
        discount_amount = Decimal("0")
    elif action == InterventionAction.ADDRESS_OTP:
        cost = assumptions.address_otp_cost
        partial_amount = Decimal("0")
        discount_percent = Decimal("0")
        discount_amount = Decimal("0")
    elif action == InterventionAction.PARTIAL_PREPAY:
        partial_amount = order_amount * assumptions.partial_prepay_percent
        cost = assumptions.partial_prepay_cost
        discount_percent = Decimal("0")
        discount_amount = Decimal("0")
    elif action == InterventionAction.PREPAID_INCENTIVE:
        discount_percent = assumptions.prepaid_discount_percent
        discount_amount = order_amount * discount_percent
        cost = assumptions.prepaid_incentive_cost + (discount_amount * success_probability)
        partial_amount = Decimal("0")
    elif action == InterventionAction.MANUAL_REVIEW:
        cost = assumptions.manual_review_cost
        partial_amount = Decimal("0")
        discount_percent = Decimal("0")
        discount_amount = Decimal("0")
    else:
        raise ValueError(f"unsupported intervention action: {action}")

    return InterventionProposal(
        action=action,
        expected_recovered_revenue=expected_recovered,
        expected_intervention_cost=cost,
        expected_net_recovery=expected_recovered - cost,
        success_probability=success_probability,
        requested_partial_prepay_amount=partial_amount,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
    )

