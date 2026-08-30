from __future__ import annotations

from app.tools.recovery_tool import RecoveryTool
from app.tools.schemas import PolicyResult


class PolicyTool:
    description = "Check whether a recovery action is permitted by the current merchant policy."

    def __init__(self, recovery_tool: RecoveryTool, policy_version: str = "demo-policy-v1") -> None:
        self.recovery_tool = recovery_tool
        self.policy_version = policy_version

    def check_recovery_policy(self, order_id: str, action: str, attempt_count: int = 0) -> PolicyResult:
        decision = self.recovery_tool.evaluate_recovery(order_id, attempt_count=attempt_count)
        candidate = next((item for item in decision["candidate_actions"] if item["action"] == action), None)
        if candidate is None:
            return PolicyResult(
                order_id=order_id,
                action=action,
                allowed=False,
                reasons=[],
                violations=[f"unknown action: {action}"],
                policy_version=self.policy_version,
            )
        violations = [check["name"] for check in candidate["policy_checks"] if not check["passed"]]
        reasons = [check["reason"] for check in candidate["policy_checks"] if check["passed"]]
        return PolicyResult(
            order_id=order_id,
            action=action,
            allowed=bool(candidate["permitted"]),
            reasons=reasons,
            violations=violations,
            policy_version=self.policy_version,
        )

