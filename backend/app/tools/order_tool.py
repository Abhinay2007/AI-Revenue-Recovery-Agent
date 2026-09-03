from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from app.core.config import get_default_dataset_path
from app.ml.data import load_orders_csv
from app.models.order import Order
from app.db.session import SessionLocal
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
    "source",
    "razorpay_order_id",
]


class OrderTool:
    description = "Retrieve synthetic order records without exposing post-outcome target fields."

    def __init__(self, dataset_path: Path | None = None) -> None:
        self.dataset_path = dataset_path or get_default_dataset_path()
        self._orders: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._orders is None:
            self._orders = self._load_with_persisted_orders()
        return self._orders

    def refresh(self) -> None:
        self._orders = self._load_with_persisted_orders()

    def _load_with_persisted_orders(self) -> pd.DataFrame:
        frame = load_orders_csv(self.dataset_path).copy()
        frame["source"] = "synthetic"
        frame["razorpay_order_id"] = None
        try:
            with SessionLocal() as session:
                persisted = session.scalars(select(Order)).all()
            if persisted:
                database_rows = pd.DataFrame(
                    [
                        {
                            "order_id": order.order_id,
                            "customer_id": order.customer_id,
                            "amount": float(order.amount),
                            "payment_method": order.payment_method.value,
                            "order_status": order.order_status.value,
                            "customer_account_age_days": order.customer_account_age_days,
                            "previous_cod_orders": order.previous_cod_orders,
                            "previous_cod_refusals": order.previous_cod_refusals,
                            "previous_successful_deliveries": order.previous_successful_deliveries,
                            "pincode": order.pincode,
                            "product_category": order.product_category,
                            "is_first_order": order.is_first_order,
                            "rto_outcome": order.rto_outcome.value if order.rto_outcome else None,
                            "created_at": order.created_at,
                            "pincode_risk_group": "MEDIUM",
                            "pincode_rto_rate": 0.20,
                            "source": getattr(order.source, "value", order.source),
                            "razorpay_order_id": order.razorpay_order_id,
                        }
                        for order in persisted
                    ]
                )
                frame = pd.concat([frame, database_rows], ignore_index=True)
                frame = frame.drop_duplicates(subset=["order_id"], keep="last")
        except Exception:
            # CSV-backed analysis must continue to work when PostgreSQL is
            # unavailable; ingestion itself still requires a database.
            pass
        return frame

    def get_order(self, order_id: str) -> OrderSnapshot:
        frame = self._load()
        matches = frame.loc[frame["order_id"] == order_id]
        if matches.empty:
            raise ToolError(f"order not found: {order_id}")
        record = matches.iloc[0][PREDICTION_TIME_COLUMNS].to_dict()
        record["created_at"] = str(record["created_at"])
        record["source"] = str(record.get("source") or "synthetic")
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
