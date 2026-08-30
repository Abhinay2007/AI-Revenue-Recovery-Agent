from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.agent.provider import AgentIntent, LLMProvider, ProviderToolCall, build_provider
from app.agent.schemas import AgentApprovalRequest, AgentChatRequest, AgentResponse
from app.agent.state import AgentState, PendingAction, ToolCallRecord, pending_approval_store
from app.core.config import get_settings
from app.tools.audit_tool import AuditTool
from app.tools.execution_tool import SimulatedRecoveryExecutor
from app.tools.order_tool import OrderTool
from app.tools.policy_tool import PolicyTool
from app.tools.recovery_tool import RecoveryTool
from app.tools.revenue_tool import RevenueTool
from app.tools.risk_tool import RiskTool
from app.tools.schemas import OrderQueryInput


class AgentToolset:
    def __init__(
        self,
        dataset_path: Path = Path("data/generated/orders.csv"),
        artifact_path: Path = Path("data/generated/models/rto_predictor.joblib"),
        audit_tool: AuditTool | None = None,
    ) -> None:
        self.order_tool = OrderTool(dataset_path)
        self.risk_tool = RiskTool(self.order_tool, artifact_path)
        self.revenue_tool = RevenueTool(self.order_tool, self.risk_tool)
        self.recovery_tool = RecoveryTool(self.order_tool, self.risk_tool)
        self.policy_tool = PolicyTool(self.recovery_tool)
        self.audit_tool = audit_tool or AuditTool()
        self.execution_tool = SimulatedRecoveryExecutor(self.order_tool, self.policy_tool)

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "get_order",
                "description": "Retrieve prediction-time fields for one order.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_rto_risk",
                "description": "Get RTO probability and risk explanations from the trained model.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "calculate_revenue_at_risk",
                "description": "Calculate deterministic expected revenue at risk for one order.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "evaluate_recovery",
                "description": "Evaluate recovery economics and recommended action using deterministic engine.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "check_recovery_policy",
                "description": "Check if a recovery action is allowed by merchant policy.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}, "action": {"type": "string"}},
                    "required": ["order_id", "action"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "find_revenue_at_risk_orders",
                "description": "Find highest predicted revenue-at-risk COD orders using deterministic tools.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                        "minimum_rto_probability": {"type": "number", "minimum": 0, "maximum": 1},
                        "minimum_order_value": {"type": "number", "minimum": 0},
                    },
                    "required": ["limit", "minimum_rto_probability", "minimum_order_value"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "execute_recovery",
                "description": "Attempt simulated execution for an already pending approved action. Will block without approval.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pending_action_id": {"type": "string"},
                        "approved_by_user": {"type": "boolean"},
                    },
                    "required": ["pending_action_id", "approved_by_user"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "create_audit_event",
                "description": "Create an agent audit event with concise input and output summaries.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "order_id": {"type": ["string", "null"]},
                        "tool": {"type": "string"},
                    },
                    "required": ["session_id", "order_id", "tool"],
                    "additionalProperties": False,
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any], session_id: str) -> Any:
        if name == "get_order":
            return self.order_tool.get_order(str(arguments["order_id"])).model_dump()
        if name == "get_rto_risk":
            return self.risk_tool.get_rto_risk(str(arguments["order_id"])).model_dump()
        if name == "calculate_revenue_at_risk":
            return self.revenue_tool.calculate_revenue_at_risk(str(arguments["order_id"])).model_dump()
        if name == "evaluate_recovery":
            return self.recovery_tool.evaluate_recovery(str(arguments["order_id"]))
        if name == "check_recovery_policy":
            return self.policy_tool.check_recovery_policy(str(arguments["order_id"]), str(arguments["action"])).model_dump()
        if name == "find_revenue_at_risk_orders":
            frame = self.order_tool._load()
            scored: list[dict[str, Any]] = []
            for _, row in frame.loc[frame["payment_method"] == "COD"].tail(250).iterrows():
                order_id = str(row["order_id"])
                risk = self.risk_tool.get_rto_risk(order_id)
                revenue = self.revenue_tool.calculate_revenue_at_risk(order_id)
                scored.append(
                    {
                        "order_id": order_id,
                        "amount": float(row["amount"]),
                        "payment_method": "COD",
                        "rto_probability": risk.rto_probability,
                        "risk_level": risk.risk_level,
                        "expected_revenue_at_risk": revenue.expected_revenue_at_risk,
                    }
                )
            return self.order_tool.find_cod_orders(OrderQueryInput(**arguments), scored)
        if name == "execute_recovery":
            return self.execution_tool.execute_recovery(
                str(arguments["pending_action_id"]),
                bool(arguments["approved_by_user"]),
            ).model_dump()
        if name == "create_audit_event":
            return self.audit_tool.create_audit_event(
                session_id=session_id,
                order_id=arguments.get("order_id"),
                tool=str(arguments["tool"]),
                inputs_summary={"source": "llm_tool_call"},
            )
        raise ValueError(f"unknown tool requested: {name}")


def default_toolset() -> AgentToolset:
    return AgentToolset()


class RevenueRecoveryAgent:
    def __init__(self, provider: LLMProvider | None = None, tools: AgentToolset | None = None) -> None:
        settings = get_settings()
        self.provider = provider or build_provider(
            settings.llm_provider,
            settings.llm_model,
            settings.llm_api_key,
            settings.llm_request_timeout_seconds,
        )
        self.tools = tools or default_toolset()
        self.max_steps = settings.max_agent_steps

    def chat(self, request: AgentChatRequest) -> AgentResponse:
        session_id = request.session_id or f"session_{uuid4().hex}"
        state = AgentState(session_id=session_id, user_request=request.message)
        if self.provider.supports_tool_calling:
            return self._chat_with_tool_loop(state)
        try:
            plan = self.provider.plan(request.message)
        except Exception as exc:
            return self._failure(state, f"Unable to interpret request: {exc}")

        state.order_id = plan.order_id
        if plan.intent == AgentIntent.UNKNOWN:
            return self._failure(state, "I need an order ID or a clearer recovery request.")
        if plan.intent == AgentIntent.FIND_REVENUE_AT_RISK:
            return self._find_revenue_at_risk(state)
        if not plan.order_id:
            return self._failure(state, "I need an order ID to inspect or recover an order.")
        if plan.intent in {AgentIntent.INSPECT_ORDER, AgentIntent.RECOMMEND_RECOVERY}:
            return self._analyze_order(state, require_approval=False)
        if plan.intent == AgentIntent.REQUEST_EXECUTION:
            return self._analyze_order(state, require_approval=True)
        return self._failure(state, "Unsupported request.")

    def approve(self, request: AgentApprovalRequest) -> AgentResponse:
        session_id = request.session_id or f"session_{uuid4().hex}"
        state = AgentState(session_id=session_id, user_request="approve recovery action")
        pending = pending_approval_store.get(request.pending_action_id)
        if pending is None:
            return self._failure(state, "Pending action not found.")
        state.order_id = pending.order_id
        if pending.is_expired():
            return self._failure(state, "Pending action has expired. Re-run the recommendation before executing.")
        if request.approved_action is not None and request.approved_action != pending.recommended_action:
            return self._failure(state, "Approved action does not match the pending recommendation. No action was executed.")
        if not request.approved:
            return self._failure(state, "Explicit approval was not provided. No action was executed.")

        policy_result = self._record_tool(
            state,
            "policy_tool.check_recovery_policy",
            {"order_id": pending.order_id, "action": pending.recommended_action},
            lambda: self.tools.policy_tool.check_recovery_policy(pending.order_id, pending.recommended_action, pending.attempt_count).model_dump(),
        )
        state.policy_result = policy_result
        if not policy_result["allowed"]:
            return self._failure(state, f"Policy blocked the action: {', '.join(policy_result['violations'])}")

        execution = self._record_tool(
            state,
            "execution_tool.execute_recovery",
            {"pending_action_id": request.pending_action_id, "approved_by_user": True},
            lambda: self.tools.execution_tool.execute_recovery(request.pending_action_id, True).model_dump(),
        )
        state.execution_result = execution
        audit = self.tools.audit_tool.create_audit_event(
            session_id=session_id,
            order_id=pending.order_id,
            tool="agent.approve",
            inputs_summary={"pending_action_id": request.pending_action_id},
            outputs_summary=execution,
            decision=pending.decision,
            approval_state="APPROVED",
            execution_status=execution["status"],
            policy_result=policy_result,
        )
        state.audit_event = audit
        if execution["status"] != "SIMULATED_SUCCESS":
            return self._failure(state, "Action was approved but execution failed.")
        return AgentResponse(
            status="EXECUTED_ACTION",
            summary=f"Simulated {execution['action']} execution completed for {execution['order_id']}.",
            natural_language_response=(
                f"Approved action executed in simulation.\n\n"
                f"Order: {execution['order_id']}\n"
                f"Action: {execution['action']}\n"
                f"Status: {execution['status']}\n"
                "No real payment or customer message was sent."
            ),
            session_id=session_id,
            order_id=pending.order_id,
            recommendation=pending.decision,
            approval_required=False,
            policy_status=policy_result,
            execution_status=execution,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _chat_with_tool_loop(self, state: AgentState) -> AgentResponse:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": state.user_request},
        ]
        final_text: str | None = None
        try:
            for step in range(self.max_steps):
                provider_response = self.provider.complete(messages, self.tools.tool_definitions())
                if provider_response.tool_calls:
                    for tool_call in provider_response.tool_calls:
                        result = self._execute_provider_tool_call(state, tool_call)
                        messages.append(
                            {
                                "type": "function_call_output",
                                "call_id": tool_call.id,
                                "output": result,
                            }
                        )
                    continue
                final_text = provider_response.final_text or "Completed."
                break
            else:
                return self._failure(state, f"Agent stopped safely after reaching max tool steps ({self.max_steps}).")
        except Exception as exc:
            return self._failure(state, f"Agent provider or tool loop failed. No financial recovery action will be executed. Error: {exc}")

        response = self._response_from_state(state, final_text or "Completed.")
        response.tool_calls.extend([{"steps": len(state.tool_calls), "provider": self.provider.name, "model": self.provider.model}])
        return response

    def _execute_provider_tool_call(self, state: AgentState, tool_call: ProviderToolCall) -> str:
        try:
            output = self.tools.call_tool(tool_call.name, tool_call.arguments, state.session_id)
            self._capture_tool_output(state, tool_call.name, output)
            state.tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_call.name,
                    inputs_summary=tool_call.arguments,
                    outputs_summary=self._summary(output),
                )
            )
            return self._safe_json(output)
        except Exception as exc:
            state.tool_calls.append(ToolCallRecord(tool_name=tool_call.name, inputs_summary=tool_call.arguments, error=str(exc)))
            return self._safe_json({"error": str(exc), "tool": tool_call.name})

    def _capture_tool_output(self, state: AgentState, name: str, output: Any) -> None:
        if not isinstance(output, dict):
            return
        if name == "get_order":
            state.order_id = output.get("order_id")
        elif name == "get_rto_risk":
            state.risk_result = output
            state.order_id = output.get("order_id")
        elif name == "calculate_revenue_at_risk":
            state.revenue_result = output
            state.order_id = output.get("order_id")
        elif name == "evaluate_recovery":
            state.recovery_result = output
            state.order_id = output.get("order_id")
        elif name == "check_recovery_policy":
            state.policy_result = output
        elif name == "execute_recovery":
            state.execution_result = output

    def _response_from_state(self, state: AgentState, provider_text: str) -> AgentResponse:
        approval_required = False
        pending_action_id = None
        recommendation = state.recovery_result
        policy = state.policy_result
        if recommendation and recommendation.get("recommended_action") != "NO_ACTION":
            if policy is None:
                policy = self.tools.policy_tool.check_recovery_policy(
                    recommendation["order_id"],
                    recommendation["recommended_action"],
                ).model_dump()
                state.policy_result = policy
            if policy.get("allowed") and state.execution_result is None:
                pending = pending_approval_store.create(
                    PendingAction(
                        session_id=state.session_id,
                        order_id=recommendation["order_id"],
                        recommended_action=recommendation["recommended_action"],
                        policy_version=policy["policy_version"],
                        decision=recommendation,
                    )
                )
                pending_action_id = pending.pending_action_id
                approval_required = True
                state.approval_state = "PENDING"
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=state.order_id,
            tool="agent.tool_loop",
            inputs_summary={"provider": self.provider.name, "model": self.provider.model},
            outputs_summary={"final_text": provider_text},
            decision=recommendation,
            approval_state=state.approval_state,
            execution_status=state.execution_result.get("status") if state.execution_result else None,
            policy_result=policy,
        )
        status = "EXECUTED_ACTION" if state.execution_result and state.execution_result.get("status") == "SIMULATED_SUCCESS" else "RECOMMENDATION" if recommendation else "ANALYSIS"
        text = self._tool_grounded_response(provider_text, state, approval_required, pending_action_id)
        return AgentResponse(
            status=status,
            summary=provider_text,
            natural_language_response=text,
            session_id=state.session_id,
            order_id=state.order_id,
            risk=state.risk_result,
            revenue_at_risk=state.revenue_result,
            recommendation=recommendation,
            approval_required=approval_required,
            pending_action_id=pending_action_id,
            policy_status=policy,
            execution_status=state.execution_result,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _tool_grounded_response(
        self,
        provider_text: str,
        state: AgentState,
        approval_required: bool,
        pending_action_id: str | None,
    ) -> str:
        if state.risk_result and state.revenue_result and state.recovery_result:
            return self._natural_response(
                {"order_id": state.order_id},
                state.risk_result,
                state.revenue_result,
                state.recovery_result,
                state.policy_result or {"allowed": False, "violations": ["policy not checked"]},
                approval_required,
                pending_action_id,
            )
        return provider_text

    def _safe_json(self, value: Any) -> str:
        import json

        return json.dumps(value, default=str)

    def _analyze_order(self, state: AgentState, require_approval: bool) -> AgentResponse:
        try:
            order = self._record_tool(state, "order_tool.get_order", {"order_id": state.order_id}, lambda: self.tools.order_tool.get_order(state.order_id or "").model_dump())
            risk = self._record_tool(state, "risk_tool.get_rto_risk", {"order_id": state.order_id}, lambda: self.tools.risk_tool.get_rto_risk(state.order_id or "").model_dump())
            revenue = self._record_tool(state, "revenue_tool.calculate_revenue_at_risk", {"order_id": state.order_id}, lambda: self.tools.revenue_tool.calculate_revenue_at_risk(state.order_id or "").model_dump())
            recovery = self._record_tool(state, "recovery_tool.evaluate_recovery", {"order_id": state.order_id}, lambda: self.tools.recovery_tool.evaluate_recovery(state.order_id or ""))
            policy = self._record_tool(
                state,
                "policy_tool.check_recovery_policy",
                {"order_id": state.order_id, "action": recovery["recommended_action"]},
                lambda: self.tools.policy_tool.check_recovery_policy(state.order_id or "", recovery["recommended_action"]).model_dump(),
            )
        except Exception as exc:
            return self._failure(state, f"Unable to calculate order risk or recovery decision. No financial recovery action will be executed. Error: {exc}")

        state.risk_result = risk
        state.revenue_result = revenue
        state.recovery_result = recovery
        state.policy_result = policy
        pending_action_id = None
        approval_required = False

        if require_approval and recovery["recommended_action"] != "NO_ACTION" and policy["allowed"]:
            pending = pending_approval_store.create(
                PendingAction(
                    session_id=state.session_id,
                    order_id=state.order_id or "",
                    recommended_action=recovery["recommended_action"],
                    policy_version=policy["policy_version"],
                    decision=recovery,
                    attempt_count=0,
                )
            )
            pending_action_id = pending.pending_action_id
            approval_required = True
            state.approval_state = "PENDING"

        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=state.order_id,
            tool="agent.chat",
            inputs_summary={"intent": "REQUEST_EXECUTION" if require_approval else "ANALYZE"},
            outputs_summary={"recommended_action": recovery["recommended_action"]},
            decision=recovery,
            approval_state=state.approval_state,
            policy_result=policy,
        )
        state.audit_event = audit
        return AgentResponse(
            status="RECOMMENDATION" if require_approval else "ANALYSIS",
            summary=f"Recommendation for {state.order_id}: {recovery['recommended_action']}",
            natural_language_response=self._natural_response(order, risk, revenue, recovery, policy, approval_required, pending_action_id),
            session_id=state.session_id,
            order_id=state.order_id,
            risk=risk,
            revenue_at_risk=revenue,
            recommendation=recovery,
            approval_required=approval_required,
            pending_action_id=pending_action_id,
            policy_status=policy,
            execution_status=None,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _find_revenue_at_risk(self, state: AgentState) -> AgentResponse:
        try:
            frame = self.tools.order_tool._load()
            cod = frame.loc[frame["payment_method"] == "COD"].tail(250).copy()
            scored: list[dict[str, Any]] = []
            for _, row in cod.iterrows():
                order_id = str(row["order_id"])
                risk = self.tools.risk_tool.get_rto_risk(order_id)
                revenue = self.tools.revenue_tool.calculate_revenue_at_risk(order_id)
                scored.append(
                    {
                        "order_id": order_id,
                        "amount": float(row["amount"]),
                        "payment_method": "COD",
                        "rto_probability": risk.rto_probability,
                        "risk_level": risk.risk_level,
                        "expected_revenue_at_risk": revenue.expected_revenue_at_risk,
                    }
                )
            orders = self.tools.order_tool.find_cod_orders(
                OrderQueryInput(limit=5, minimum_rto_probability=0.30, minimum_order_value=0),
                scored,
            )
        except Exception as exc:
            return self._failure(state, f"Unable to retrieve revenue-at-risk orders. Error: {exc}")
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=None,
            tool="agent.find_revenue_at_risk",
            inputs_summary={"limit": 5, "minimum_rto_probability": 0.30},
            outputs_summary={"orders": orders},
        )
        return AgentResponse(
            status="ANALYSIS",
            summary="Highest revenue-at-risk COD orders retrieved.",
            natural_language_response="\n".join(
                ["Highest revenue-at-risk COD orders:", *[f"- {item['order_id']}: Rs {item['expected_revenue_at_risk']:.2f} at {item['rto_probability']:.1%} RTO risk" for item in orders]]
            ),
            session_id=state.session_id,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _record_tool(self, state: AgentState, name: str, inputs: dict[str, Any], func):
        try:
            output = func()
            state.tool_calls.append(ToolCallRecord(tool_name=name, inputs_summary=inputs, outputs_summary=self._summary(output)))
            return output
        except Exception as exc:
            state.tool_calls.append(ToolCallRecord(tool_name=name, inputs_summary=inputs, error=str(exc)))
            raise

    def _failure(self, state: AgentState, message: str) -> AgentResponse:
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=state.order_id,
            tool="agent.failure",
            inputs_summary={"request": state.user_request},
            outputs_summary={"message": message},
            approval_state=state.approval_state,
            execution_status="BLOCKED",
        )
        return AgentResponse(
            status="FAILED",
            summary=message,
            natural_language_response=message,
            session_id=state.session_id,
            order_id=state.order_id,
            approval_required=False,
            policy_status=state.policy_result,
            execution_status=state.execution_result,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _summary(self, output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            return {key: output[key] for key in list(output)[:8]}
        if hasattr(output, "model_dump"):
            return output.model_dump()
        return {"value": str(output)}

    def _natural_response(
        self,
        order: dict[str, Any],
        risk: dict[str, Any],
        revenue: dict[str, Any],
        recovery: dict[str, Any],
        policy: dict[str, Any],
        approval_required: bool,
        pending_action_id: str | None,
    ) -> str:
        policy_line = "Allowed" if policy["allowed"] else f"Blocked: {', '.join(policy['violations'])}"
        approval_line = (
            f"Approval required before execution. Pending action ID: {pending_action_id}"
            if approval_required
            else "No execution has been performed."
        )
        return (
            f"Order {order['order_id']}\n\n"
            f"RTO risk: {risk['risk_level']} - {risk['rto_probability']:.1%}\n"
            f"Revenue at risk: Rs {revenue['expected_revenue_at_risk']:.2f}\n\n"
            f"Recommended action: {recovery['recommended_action']}\n"
            f"Expected recovered revenue: Rs {recovery['expected_recovered_revenue']:.2f}\n"
            f"Intervention cost: Rs {recovery['expected_intervention_cost']:.2f}\n"
            f"Expected net recovery: Rs {recovery['expected_net_recovery']:.2f}\n\n"
            f"Why: {recovery['reason']}\n\n"
            f"Policy: {policy_line}\n"
            f"{approval_line}"
        )


agent_singleton = RevenueRecoveryAgent()
