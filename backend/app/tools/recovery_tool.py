from __future__ import annotations

from app.decision.engine import decide_recovery_action
from app.decision.interventions import RecoveryAssumptions
from app.decision.policy import MerchantPolicy
from app.tools.order_tool import OrderTool
from app.tools.risk_tool import RiskTool


class RecoveryTool:
    description = "Evaluate candidate recovery actions using the deterministic decision engine."

    def __init__(
        self,
        order_tool: OrderTool,
        risk_tool: RiskTool,
        policy: MerchantPolicy | None = None,
        assumptions: RecoveryAssumptions | None = None,
    ) -> None:
        self.order_tool = order_tool
        self.risk_tool = risk_tool
        self.policy = policy or MerchantPolicy()
        self.assumptions = assumptions or RecoveryAssumptions()

    def evaluate_recovery(self, order_id: str, attempt_count: int = 0) -> dict:
        order = self.order_tool.get_order(order_id)
        risk = self.risk_tool.get_rto_risk(order_id)
        return decide_recovery_action(
            order={"order_id": order.order_id, "amount": order.amount, "attempt_count": attempt_count},
            rto_probability=risk.rto_probability,
            merchant_policy=self.policy,
            recovery_assumptions=self.assumptions,
        )

