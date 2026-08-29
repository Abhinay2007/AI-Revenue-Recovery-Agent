from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


def create_audit_event(decision: dict[str, Any]) -> dict[str, Any]:
    return json_value(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "order_id": decision["order_id"],
            "rto_probability": decision["rto_probability"],
            "revenue_at_risk": decision["expected_revenue_at_risk"],
            "candidate_actions": decision["candidate_actions"],
            "selected_action": decision["recommended_action"],
            "decision_reason": decision["reason_codes"],
            "policy_checks": decision["policy_checks"],
            "assumption_source": decision["assumption_source"],
        }
    )

