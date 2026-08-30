from __future__ import annotations

from abc import ABC, abstractmethod

from app.agent.state import ApprovalStatus, PendingApprovalStore, pending_approval_store
from app.tools.order_tool import OrderTool
from app.tools.policy_tool import PolicyTool
from app.tools.schemas import ExecutionResult


class RecoveryExecutor(ABC):
    @abstractmethod
    def execute_recovery(self, pending_action_id: str, approved_by_user: bool) -> ExecutionResult:
        raise NotImplementedError


class SimulatedRecoveryExecutor(RecoveryExecutor):
    description = "Safe simulated recovery executor. Does not call real payment or messaging APIs."

    def __init__(
        self,
        order_tool: OrderTool,
        policy_tool: PolicyTool,
        store: PendingApprovalStore = pending_approval_store,
    ) -> None:
        self.order_tool = order_tool
        self.policy_tool = policy_tool
        self.store = store

    def execute_recovery(self, pending_action_id: str, approved_by_user: bool) -> ExecutionResult:
        pending = self.store.get(pending_action_id)
        if pending is None:
            return ExecutionResult(status="BLOCKED", action="UNKNOWN", order_id="UNKNOWN", reason="pending action not found")
        if pending.status != ApprovalStatus.PENDING:
            return ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"pending action is not executable in status {pending.status}",
            )
        if pending.is_expired():
            self.store.mark(pending_action_id, ApprovalStatus.EXPIRED)
            return ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason="pending action expired",
            )
        if not approved_by_user:
            return ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason="explicit user approval is required",
            )

        try:
            self.order_tool.get_order(pending.order_id)
            current_decision = self.policy_tool.recovery_tool.evaluate_recovery(pending.order_id, pending.attempt_count)
            policy = self.policy_tool.check_recovery_policy(pending.order_id, pending.recommended_action, pending.attempt_count)
        except Exception as exc:
            self.store.mark(pending_action_id, ApprovalStatus.BLOCKED)
            return ExecutionResult(
                status="FAILED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"execution validation failed: {exc}",
            )

        if not policy.allowed:
            self.store.mark(pending_action_id, ApprovalStatus.BLOCKED)
            return ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"policy blocked action: {', '.join(policy.violations)}",
            )

        current_decision_action = current_decision.get("recommended_action")
        if current_decision_action != pending.recommended_action:
            self.store.mark(pending_action_id, ApprovalStatus.BLOCKED)
            return ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason="pending action no longer matches current decision",
            )

        self.store.mark(pending_action_id, ApprovalStatus.EXECUTED)
        return ExecutionResult(
            status="SIMULATED_SUCCESS",
            action=pending.recommended_action,
            order_id=pending.order_id,
            reason="simulated recovery action executed after explicit approval",
        )
