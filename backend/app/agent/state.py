from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"


class ToolCallRecord(BaseModel):
    tool_name: str
    inputs_summary: dict[str, Any]
    outputs_summary: dict[str, Any] | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class PendingAction(BaseModel):
    pending_action_id: str = Field(default_factory=lambda: f"pending_{uuid4().hex}")
    session_id: str
    order_id: str
    recommended_action: str
    policy_version: str = "demo-policy-v1"
    decision: dict[str, Any]
    attempt_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=15))
    status: ApprovalStatus = ApprovalStatus.PENDING

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at


class AgentState(BaseModel):
    session_id: str
    user_request: str
    order_id: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    risk_result: dict[str, Any] | None = None
    revenue_result: dict[str, Any] | None = None
    recovery_result: dict[str, Any] | None = None
    policy_result: dict[str, Any] | None = None
    approval_state: str = "NOT_REQUIRED"
    execution_result: dict[str, Any] | None = None
    audit_event: dict[str, Any] | None = None


class PendingApprovalStore:
    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}

    def create(self, action: PendingAction) -> PendingAction:
        self._actions[action.pending_action_id] = action
        return action

    def get(self, pending_action_id: str) -> PendingAction | None:
        return self._actions.get(pending_action_id)

    def mark(self, pending_action_id: str, status: ApprovalStatus) -> None:
        if pending_action_id in self._actions:
            existing = self._actions[pending_action_id]
            self._actions[pending_action_id] = existing.model_copy(update={"status": status})

    def clear(self) -> None:
        self._actions.clear()


pending_approval_store = PendingApprovalStore()
