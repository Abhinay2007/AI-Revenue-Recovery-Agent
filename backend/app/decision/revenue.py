from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RevenueAtRisk:
    order_amount: Decimal
    rto_probability: Decimal
    expected_revenue_at_risk: Decimal


def calculate_revenue_at_risk(order_amount: Decimal | int | float | str, rto_probability: float | Decimal) -> RevenueAtRisk:
    amount = Decimal(str(order_amount))
    probability = Decimal(str(rto_probability))
    if amount < 0:
        raise ValueError("order_amount must be non-negative")
    if probability < 0 or probability > 1:
        raise ValueError("rto_probability must be between 0 and 1")
    return RevenueAtRisk(
        order_amount=amount,
        rto_probability=probability,
        expected_revenue_at_risk=amount * probability,
    )

