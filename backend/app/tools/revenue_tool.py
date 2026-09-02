from __future__ import annotations

from app.decision.revenue import calculate_revenue_at_risk
from app.tools.order_tool import OrderTool
from app.tools.risk_tool import RiskTool
from app.tools.schemas import RevenueRiskResult


class RevenueTool:
    description = "Calculate expected revenue at risk using deterministic revenue math."

    def __init__(self, order_tool: OrderTool, risk_tool: RiskTool) -> None:
        self.order_tool = order_tool
        self.risk_tool = risk_tool

    def calculate_revenue_at_risk(self, order_id: str, rto_probability: float | None = None) -> RevenueRiskResult:
        order = self.order_tool.get_order(order_id)
        probability = rto_probability if rto_probability is not None else self.risk_tool.get_rto_risk(order_id).rto_probability
        revenue = calculate_revenue_at_risk(order.amount, probability)
        return RevenueRiskResult(
            order_id=order_id,
            order_amount=float(revenue.order_amount),
            rto_probability=float(revenue.rto_probability),
            expected_revenue_at_risk=float(revenue.expected_revenue_at_risk),
        )

