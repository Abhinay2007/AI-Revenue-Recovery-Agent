from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class AuditTool:
    description = "Append-only in-memory audit log for agent tool usage and simulated execution."

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def create_audit_event(
        self,
        session_id: str,
        order_id: str | None,
        tool: str,
        inputs_summary: dict[str, Any],
        outputs_summary: dict[str, Any] | None = None,
        decision: dict[str, Any] | None = None,
        approval_state: str = "NOT_REQUIRED",
        execution_status: str | None = None,
        policy_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "audit_id": f"audit_{uuid4().hex}",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "order_id": order_id,
            "actor": "agent",
            "tool": tool,
            "inputs_summary": inputs_summary,
            "outputs_summary": outputs_summary or {},
            "decision": decision or {},
            "approval_state": approval_state,
            "execution_status": execution_status,
            "policy_result": policy_result or {},
        }
        self.events.append(event)
        return event

