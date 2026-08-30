from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.decision.interventions import InterventionAction
from app.tools.order_tool import OrderTool
from app.tools.recovery_tool import RecoveryTool
from app.tools.revenue_tool import RevenueTool
from app.tools.risk_tool import RiskTool


@dataclass(frozen=True)
class MerchantContext:
    merchant_id: str = "demo-merchant"
    source: str = "synthetic_demo_merchant"


class MerchantTool:
    description = "Deterministic merchant-level revenue and recovery summaries for the synthetic demo merchant."

    def __init__(
        self,
        order_tool: OrderTool,
        risk_tool: RiskTool,
        revenue_tool: RevenueTool,
        recovery_tool: RecoveryTool,
        merchant_context: MerchantContext | None = None,
        evaluation_limit: int = 250,
    ) -> None:
        self.order_tool = order_tool
        self.risk_tool = risk_tool
        self.revenue_tool = revenue_tool
        self.recovery_tool = recovery_tool
        self.merchant_context = merchant_context or MerchantContext()
        self.evaluation_limit = evaluation_limit

    def _cod_population(self) -> pd.DataFrame:
        frame = self.order_tool._load()
        return frame.loc[frame["payment_method"] == "COD"].tail(self.evaluation_limit).reset_index(drop=True)

    def _all_population(self) -> pd.DataFrame:
        return self.order_tool._load()

    def _scored_cod_orders(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for _, record in self._cod_population().iterrows():
            order_id = str(record["order_id"])
            risk = self.risk_tool.get_rto_risk(order_id)
            revenue = self.revenue_tool.calculate_revenue_at_risk(order_id)
            decision = self.recovery_tool.evaluate_recovery(order_id)
            rows.append(
                {
                    "order_id": order_id,
                    "amount": float(record["amount"]),
                    "payment_method": "COD",
                    "rto_probability": risk.rto_probability,
                    "risk_level": risk.risk_level,
                    "expected_revenue_at_risk": revenue.expected_revenue_at_risk,
                    "recommended_action": decision["recommended_action"],
                    "expected_gross_recovery": decision["expected_recovered_revenue"],
                    "expected_intervention_cost": decision["expected_intervention_cost"],
                    "expected_net_recovery": decision["expected_net_recovery"],
                }
            )
        return rows

    def get_revenue_summary(self) -> dict[str, Any]:
        frame = self._all_population()
        cod = frame.loc[frame["payment_method"] == "COD"]
        prepaid = frame.loc[frame["payment_method"] == "PREPAID"]
        rto = cod.loc[cod["rto_outcome"] == "RTO"] if "rto_outcome" in cod.columns else cod.iloc[0:0]
        scored = self._scored_cod_orders()
        return {
            "merchant_id": self.merchant_context.merchant_id,
            "merchant_context_source": self.merchant_context.source,
            "total_orders": int(len(frame)),
            "cod_orders": int(len(cod)),
            "prepaid_orders": int(len(prepaid)),
            "total_order_value": float(pd.to_numeric(frame["amount"]).sum()),
            "rto_orders": int(len(rto)),
            "rto_value": float(pd.to_numeric(rto["amount"]).sum()) if not rto.empty else 0.0,
            "rto_rate": float(len(rto) / len(cod)) if len(cod) else 0.0,
            "predicted_revenue_at_risk": float(sum(order["expected_revenue_at_risk"] for order in scored)),
            "scored_cod_orders": len(scored),
            "ranking_note": "predicted_revenue_at_risk is calculated over the recent synthetic COD evaluation window",
        }

    def get_priority_recovery_orders(
        self,
        limit: int = 10,
        minimum_rto_probability: float = 0.30,
        minimum_order_value: float = 0.0,
    ) -> dict[str, Any]:
        scored = [
            order
            for order in self._scored_cod_orders()
            if order["rto_probability"] >= minimum_rto_probability and order["amount"] >= minimum_order_value
        ]
        ranked = sorted(scored, key=lambda order: order["expected_revenue_at_risk"], reverse=True)[:limit]
        return {
            "merchant_id": self.merchant_context.merchant_id,
            "ranking_metric": "expected_revenue_at_risk",
            "limit": limit,
            "minimum_rto_probability": minimum_rto_probability,
            "minimum_order_value": minimum_order_value,
            "orders": ranked,
        }

    def get_recovery_opportunity_summary(self) -> dict[str, Any]:
        scored = self._scored_cod_orders()
        positive = [order for order in scored if order["expected_net_recovery"] > 0 and order["recommended_action"] != InterventionAction.NO_ACTION.value]
        return {
            "merchant_id": self.merchant_context.merchant_id,
            "orders_evaluated": len(scored),
            "orders_with_positive_expected_recovery": len(positive),
            "total_revenue_at_risk": float(sum(order["expected_revenue_at_risk"] for order in scored)),
            "expected_gross_recovery": float(sum(order["expected_gross_recovery"] for order in positive)),
            "expected_intervention_cost": float(sum(order["expected_intervention_cost"] for order in positive)),
            "expected_net_recovery": float(sum(order["expected_net_recovery"] for order in positive)),
            "assumption_source": "synthetic_demo_assumption",
        }

    def get_recovery_action_distribution(self) -> dict[str, Any]:
        scored = self._scored_cod_orders()
        rows: list[dict[str, Any]] = []
        total = len(scored)
        for action in InterventionAction:
            action_rows = [order for order in scored if order["recommended_action"] == action.value]
            rows.append(
                {
                    "action": action.value,
                    "count": len(action_rows),
                    "percentage": len(action_rows) / total if total else 0.0,
                    "expected_net_recovery": float(sum(order["expected_net_recovery"] for order in action_rows)),
                }
            )
        return {
            "merchant_id": self.merchant_context.merchant_id,
            "orders_evaluated": total,
            "distribution": rows,
        }

