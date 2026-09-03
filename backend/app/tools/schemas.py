from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolError(RuntimeError):
    pass


class OrderLookupInput(BaseModel):
    order_id: str = Field(min_length=1)


class OrderQueryInput(BaseModel):
    limit: int = Field(default=5, ge=1, le=50)
    minimum_rto_probability: float = Field(default=0.0, ge=0, le=1)
    minimum_order_value: float = Field(default=0.0, ge=0)


class OrderSnapshot(BaseModel):
    order_id: str
    customer_id: str
    amount: float
    payment_method: str
    customer_account_age_days: int
    previous_cod_orders: int
    previous_cod_refusals: int
    previous_successful_deliveries: int
    pincode_risk_group: str
    pincode_rto_rate: float
    product_category: str
    is_first_order: bool
    created_at: str
    source: str = "synthetic"
    razorpay_order_id: str | None = None


class RiskResult(BaseModel):
    order_id: str
    rto_probability: float
    risk_level: str
    reasons: list[dict[str, Any]]


class RevenueRiskResult(BaseModel):
    order_id: str
    order_amount: float
    rto_probability: float
    expected_revenue_at_risk: float


class PolicyResult(BaseModel):
    order_id: str
    action: str
    allowed: bool
    reasons: list[str]
    violations: list[str]
    policy_version: str = "demo-policy-v1"


class ExecutionRequest(BaseModel):
    pending_action_id: str
    approved_by_user: bool


class ExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"exec_{uuid4().hex}")
    status: Literal["SIMULATED_SUCCESS", "BLOCKED", "FAILED"]
    action: str
    order_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str
    razorpay: dict[str, Any] | None = None
