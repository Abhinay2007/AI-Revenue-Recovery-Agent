from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.ml.data import load_orders_csv
from app.tools.schemas import OrderQueryInput, OrderSnapshot, ToolError


PREDICTION_TIME_COLUMNS = [
    "order_id",
    "customer_id",
    "amount",
    "payment_method",
    "customer_account_age_days",
    "previous_cod_orders",
    "previous_cod_refusals",
    "previous_successful_deliveries",
    "pincode_risk_group",
    "pincode_rto_rate",
    "product_category",
    "is_first_order",
    "created_at",
]


class OrderTool:
    description = "Retrieve synthetic order records without exposing post-outcome target fields."

    def __init__(self, dataset_path: Path = Path("data/generated/orders.csv")) -> None:
        self.dataset_path = dataset_path
        self._orders: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._orders is None:
            self._orders = load_orders_csv(self.dataset_path)
        return self._orders

    def get_order(self, order_id: str) -> OrderSnapshot:
        frame = self._load()
        matches = frame.loc[frame["order_id"] == order_id]
        if matches.empty:
            raise ToolError(f"order not found: {order_id}")
        record = matches.iloc[0][PREDICTION_TIME_COLUMNS].to_dict()
        record["created_at"] = str(record["created_at"])
        return OrderSnapshot(**record)

    def get_internal_record(self, order_id: str) -> dict[str, Any]:
        frame = self._load()
        matches = frame.loc[frame["order_id"] == order_id]
        if matches.empty:
            raise ToolError(f"order not found: {order_id}")
        return matches.iloc[0].to_dict()

    def find_cod_orders(self, query: OrderQueryInput, scored_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = [
            order
            for order in scored_orders
            if order["payment_method"] == "COD"
            and order["rto_probability"] >= query.minimum_rto_probability
            and order["amount"] >= query.minimum_order_value
        ]
        return sorted(filtered, key=lambda item: item["expected_revenue_at_risk"], reverse=True)[: query.limit]

