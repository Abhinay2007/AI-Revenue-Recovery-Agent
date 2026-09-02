from __future__ import annotations

from pathlib import Path

from app.core.config import get_default_artifact_path
from app.ml.rto_predictor import RTOPredictor
from app.tools.order_tool import OrderTool
from app.tools.schemas import RiskResult, ToolError


class RiskTool:
    description = "Calculate RTO probability using the existing trained model artifact."

    def __init__(self, order_tool: OrderTool, artifact_path: Path | None = None) -> None:
        self.order_tool = order_tool
        self.artifact_path = artifact_path or get_default_artifact_path()
        self._predictor: RTOPredictor | None = None

    def _load_predictor(self) -> RTOPredictor:
        if self._predictor is None:
            self._predictor = RTOPredictor.load(self.artifact_path)
        return self._predictor

    def get_rto_risk(self, order_id: str) -> RiskResult:
        order = self.order_tool.get_internal_record(order_id)
        if order.get("payment_method") != "COD":
            raise ToolError("RTO risk model is currently available only for COD orders")
        prediction = self._load_predictor().predict(order)
        return RiskResult(
            order_id=order_id,
            rto_probability=prediction["rto_probability"],
            risk_level=prediction["risk_level"],
            reasons=prediction["explanation"],
        )

    def get_rto_probability(self, order_id: str) -> float:
        order = self.order_tool.get_internal_record(order_id)
        if order.get("payment_method") != "COD":
            raise ToolError("RTO risk model is currently available only for COD orders")
        return self._load_predictor().predict_probability(order)

    def get_rto_probabilities(self, orders: list[dict]) -> list[float]:
        if any(order.get("payment_method") != "COD" for order in orders):
            raise ToolError("RTO risk model is currently available only for COD orders")
        return self._load_predictor().predict_probabilities(orders)

