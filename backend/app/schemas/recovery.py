from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class RecoveryDecisionRequest(BaseModel):
    order_id: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)
    rto_probability: Decimal = Field(ge=0, le=1)
    attempt_count: int = Field(default=0, ge=0)


class RecoveryRequest(BaseModel):
    order_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    session_id: str | None = None


class RecoveryDecisionResponse(BaseModel):
    order_id: str
    recommended_action: str
    reason: str
    reason_codes: list[str]
    rto_probability: float
    order_amount: float
    expected_revenue_at_risk: float
    candidate_actions: list[dict[str, Any]]
    expected_recovered_revenue: float
    expected_intervention_cost: float
    expected_net_recovery: float
    policy_checks: dict[str, list[dict[str, Any]]]
    assumption_source: str
    audit_event: dict[str, Any]
