from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.agent.state import ApprovalStatus, PendingApprovalStore, pending_approval_store
from app.integrations.razorpay import RazorpayAPIError, RazorpayConfigurationError, RazorpayTestModeAdapter
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
        pending, current_decision, blocked = self.validate_recovery(pending_action_id, approved_by_user)
        if blocked is not None:
            return blocked

        self.store.mark(pending_action_id, ApprovalStatus.EXECUTED)
        return ExecutionResult(
            status="SIMULATED_SUCCESS",
            action=pending.recommended_action,
            order_id=pending.order_id,
            reason="simulated recovery action executed after explicit approval",
        )

    def validate_recovery(
        self,
        pending_action_id: str,
        approved_by_user: bool,
    ) -> tuple[Any, dict[str, Any] | None, ExecutionResult | None]:
        pending = self.store.get(pending_action_id)
        if pending is None:
            return None, None, ExecutionResult(status="BLOCKED", action="UNKNOWN", order_id="UNKNOWN", reason="pending action not found")
        if pending.status != ApprovalStatus.PENDING:
            return None, None, ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"pending action is not executable in status {pending.status}",
            )
        if pending.is_expired():
            self.store.mark(pending_action_id, ApprovalStatus.EXPIRED)
            return None, None, ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason="pending action expired",
            )
        if not approved_by_user:
            return None, None, ExecutionResult(
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
            return None, None, ExecutionResult(
                status="FAILED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"execution validation failed: {exc}",
            )

        if not policy.allowed:
            self.store.mark(pending_action_id, ApprovalStatus.BLOCKED)
            return None, current_decision, ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"policy blocked action: {', '.join(policy.violations)}",
            )

        current_decision_action = current_decision.get("recommended_action")
        if current_decision_action != pending.recommended_action:
            self.store.mark(pending_action_id, ApprovalStatus.BLOCKED)
            return None, current_decision, ExecutionResult(
                status="BLOCKED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason="pending action no longer matches current decision",
            )

        return pending, current_decision, None


class RazorpayTestModeExecutor(RecoveryExecutor):
    description = "Razorpay Test Mode executor. Runs only after the existing approval and policy gate."

    def __init__(
        self,
        order_tool: OrderTool,
        policy_tool: PolicyTool,
        razorpay_adapter: RazorpayTestModeAdapter,
        store: PendingApprovalStore = pending_approval_store,
    ) -> None:
        self.store = store
        self.razorpay_adapter = razorpay_adapter
        self.validator = SimulatedRecoveryExecutor(order_tool, policy_tool, store)

    def execute_recovery(self, pending_action_id: str, approved_by_user: bool) -> ExecutionResult:
        pending, current_decision, blocked = self.validator.validate_recovery(pending_action_id, approved_by_user)
        if blocked is not None:
            return blocked
        if pending is None or current_decision is None:
            return ExecutionResult(status="FAILED", action="UNKNOWN", order_id="UNKNOWN", reason="execution validation failed")

        try:
            razorpay_result = self._execute_test_mode_operation(pending.order_id, pending.recommended_action, current_decision)
        except (RazorpayConfigurationError, RazorpayAPIError, TimeoutError) as exc:
            return ExecutionResult(
                status="FAILED",
                action=pending.recommended_action,
                order_id=pending.order_id,
                reason=f"Razorpay Test Mode execution failed: {exc}",
                razorpay={"enabled": self.razorpay_adapter.enabled, "mode": "test", "status": "FAILED"},
            )

        self.store.mark(pending_action_id, ApprovalStatus.EXECUTED)
        return ExecutionResult(
            status="SIMULATED_SUCCESS",
            action=pending.recommended_action,
            order_id=pending.order_id,
            reason="Razorpay Test Mode operation completed after explicit approval",
            razorpay=razorpay_result,
        )

    def _execute_test_mode_operation(self, internal_order_id: str, action: str, decision: dict[str, Any]) -> dict[str, Any]:
        if action != "PARTIAL_PREPAY":
            return {"enabled": True, "mode": "test", "status": "SKIPPED", "reason": f"no Razorpay test order required for {action}"}
        amount = self._partial_prepay_amount(decision)
        return self.razorpay_adapter.create_test_order(
            internal_order_id=internal_order_id,
            amount_rupees=amount,
            notes={"recovery_action": action},
        )

    @staticmethod
    def _partial_prepay_amount(decision: dict[str, Any]) -> Decimal:
        selected = decision.get("recommended_action")
        for candidate in decision.get("candidate_actions", []):
            if candidate.get("action") == selected:
                return Decimal(str(candidate.get("requested_partial_prepay_amount", "0")))
        return Decimal("0")
