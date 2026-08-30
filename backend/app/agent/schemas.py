from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class AgentApprovalRequest(BaseModel):
    pending_action_id: str = Field(min_length=1)
    approved: bool
    approved_action: str | None = None
    session_id: str | None = None


class AgentResponse(BaseModel):
    status: str
    summary: str
    natural_language_response: str
    session_id: str
    order_id: str | None = None
    risk: dict[str, Any] | None = None
    revenue_at_risk: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    approval_required: bool = False
    pending_action_id: str | None = None
    policy_status: dict[str, Any] | None = None
    execution_status: dict[str, Any] | None = None
    audit_id: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
