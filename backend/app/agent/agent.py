from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.agent.provider import AgentIntent, LLMProvider, ProviderToolCall, build_provider
from app.agent.schemas import AgentApprovalRequest, AgentChatRequest, AgentResponse
from app.agent.state import AgentState, PendingAction, ToolCallRecord, pending_approval_store
from app.core.config import get_default_artifact_path, get_default_dataset_path, get_settings
from app.integrations.razorpay import RazorpayTestModeAdapter
from app.tools.audit_tool import AuditTool
from app.tools.execution_tool import RazorpayTestModeExecutor, SimulatedRecoveryExecutor
from app.tools.merchant_tool import MerchantContext, MerchantTool
from app.tools.order_tool import OrderTool
from app.tools.policy_tool import PolicyTool
from app.tools.recovery_tool import RecoveryTool
from app.tools.revenue_tool import RevenueTool
from app.tools.risk_tool import RiskTool
from app.tools.schemas import OrderQueryInput


logger = logging.getLogger(__name__)


class AgentToolset:
    def __init__(
        self,
        dataset_path: Path | None = None,
        artifact_path: Path | None = None,
        audit_tool: AuditTool | None = None,
    ) -> None:
        resolved_dataset_path = dataset_path or get_default_dataset_path()
        resolved_artifact_path = artifact_path or get_default_artifact_path()
        self.order_tool = OrderTool(resolved_dataset_path)
        self.risk_tool = RiskTool(self.order_tool, resolved_artifact_path)
        self.revenue_tool = RevenueTool(self.order_tool, self.risk_tool)
        self.recovery_tool = RecoveryTool(self.order_tool, self.risk_tool)
        self.policy_tool = PolicyTool(self.recovery_tool)
        self.merchant_tool = MerchantTool(
            self.order_tool,
            self.risk_tool,
            self.revenue_tool,
            self.recovery_tool,
            MerchantContext(),
        )
        self.audit_tool = audit_tool or AuditTool()
        settings = get_settings()
        if settings.razorpay_enabled:
            razorpay_adapter = RazorpayTestModeAdapter.from_settings(settings)
            self.execution_tool = RazorpayTestModeExecutor(self.order_tool, self.policy_tool, razorpay_adapter)
        else:
            self.execution_tool = SimulatedRecoveryExecutor(self.order_tool, self.policy_tool)

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "get_order",
                "description": "Use for one order. Returns prediction-time order fields only; no target/outcome fields.",
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
                "description": "Use for one COD order. Returns model-derived RTO probability, risk level, and reasons.",
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
                "description": "Use after risk is needed. Deterministically returns order amount times model RTO probability.",
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
                "description": "Use for recovery recommendations. Returns authoritative candidate economics, policy checks, and selected action.",
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
                "description": "Use before execution or when explaining restrictions. Returns authoritative policy allow/block result.",
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
                "name": "get_revenue_summary",
                "description": "Use for merchant-level questions like how much revenue is at risk. Returns deterministic aggregate revenue summary.",
                "strict": True,
                "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "get_priority_recovery_orders",
                "description": "Use for prioritization questions. Returns orders ranked by expected revenue at risk, not raw probability alone.",
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
                "name": "get_recovery_opportunity_summary",
                "description": "Use for questions about potential recovery. Aggregates expected economics from the deterministic recovery engine.",
                "strict": True,
                "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "get_recovery_action_distribution",
                "description": "Use for questions about what actions the recovery system is taking. Returns counts and expected net recovery by action.",
                "strict": True,
                "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
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
        if name == "get_revenue_summary":
            return self.merchant_tool.get_revenue_summary()
        if name == "get_priority_recovery_orders":
            return self.merchant_tool.get_priority_recovery_orders(**arguments)
        if name == "get_recovery_opportunity_summary":
            return self.merchant_tool.get_recovery_opportunity_summary()
        if name == "get_recovery_action_distribution":
            return self.merchant_tool.get_recovery_action_distribution()
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
            response = self._chat_with_tool_loop(state)
            self._log_result(response)
            return response
        try:
            plan = self.provider.plan(request.message)
        except Exception as exc:
            response = self._failure(state, f"Unable to interpret request: {exc}")
            self._log_result(response)
            return response

        state.order_id = plan.order_id
        state.intent = plan.intent.value
        if plan.intent == AgentIntent.UNKNOWN:
            response = self._failure(state, "I need an order ID or a clearer recovery request.")
        if plan.intent == AgentIntent.REVENUE_SUMMARY:
            response = self._merchant_summary(state)
        elif plan.intent == AgentIntent.PRIORITY_RECOVERY:
            response = self._priority_recovery(state)
        elif plan.intent == AgentIntent.RECOVERY_OPPORTUNITY:
            response = self._recovery_opportunity(state)
        elif plan.intent == AgentIntent.ACTION_DISTRIBUTION:
            response = self._action_distribution(state)
        elif plan.intent == AgentIntent.FIND_REVENUE_AT_RISK:
            response = self._find_revenue_at_risk(state)
        elif not plan.order_id:
            response = self._failure(state, "I need an order ID to inspect or recover an order.")
        elif plan.intent in {AgentIntent.INSPECT_ORDER, AgentIntent.RECOMMEND_RECOVERY}:
            response = self._analyze_order(state, require_approval=False)
        elif plan.intent == AgentIntent.REQUEST_EXECUTION:
            response = self._analyze_order(state, require_approval=True)
        else:
            response = self._failure(state, "Unsupported request.")
        self._log_result(response)
        return response

    def approve(self, request: AgentApprovalRequest) -> AgentResponse:
        session_id = request.session_id or f"session_{uuid4().hex}"
        state = AgentState(session_id=session_id, user_request="approve recovery action")
        pending = pending_approval_store.get(request.pending_action_id)
        if pending is None:
            response = self._failure(state, "Pending action not found.")
            self._log_result(response)
            return response
        state.order_id = pending.order_id
        if pending.is_expired():
            response = self._failure(state, "Pending action has expired. Re-run the recommendation before executing.")
            self._log_result(response)
            return response
        if request.approved_action is not None and request.approved_action != pending.recommended_action:
            response = self._failure(state, "Approved action does not match the pending recommendation. No action was executed.")
            self._log_result(response)
            return response
        if not request.approved:
            response = self._failure(state, "Explicit approval was not provided. No action was executed.")
            self._log_result(response)
            return response

        policy_result = self._record_tool(
            state,
            "policy_tool.check_recovery_policy",
            {"order_id": pending.order_id, "action": pending.recommended_action},
            lambda: self.tools.policy_tool.check_recovery_policy(pending.order_id, pending.recommended_action, pending.attempt_count).model_dump(),
        )
        state.policy_result = policy_result
        if not policy_result["allowed"]:
            response = self._failure(state, f"Policy blocked the action: {', '.join(policy_result['violations'])}")
            self._log_result(response)
            return response

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
            response = self._failure(state, "Action was approved but execution failed.")
            self._log_result(response)
            return response
        response = AgentResponse(
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
            intent=AgentIntent.REQUEST_EXECUTION.value,
            order_id=pending.order_id,
            recommendation=pending.decision,
            approval_required=False,
            policy_status=policy_result,
            execution_status=execution,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )
        self._log_result(response)
        return response

    def _chat_with_tool_loop(self, state: AgentState) -> AgentResponse:
        self.provider.reset()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": state.user_request},
        ]
        final_text: str | None = None
        try:
            for step in range(self.max_steps):
                provider_response = self.provider.complete(messages, self.tools.tool_definitions())
                if provider_response.tool_calls:
                    tool_outputs: list[dict[str, Any]] = []
                    for tool_call in provider_response.tool_calls:
                        result = self._execute_provider_tool_call(state, tool_call)
                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": tool_call.id,
                                "output": result,
                            }
                        )
                    messages = tool_outputs
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
        elif name == "get_revenue_summary":
            state.intent = AgentIntent.REVENUE_SUMMARY.value
            state.merchant_summary = output
        elif name == "get_priority_recovery_orders":
            state.intent = AgentIntent.PRIORITY_RECOVERY.value
            state.priority_orders = output
        elif name == "get_recovery_opportunity_summary":
            state.intent = AgentIntent.RECOVERY_OPPORTUNITY.value
            state.recovery_opportunity = output
        elif name == "get_recovery_action_distribution":
            state.intent = AgentIntent.ACTION_DISTRIBUTION.value
            state.action_distribution = output

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
            intent=state.intent,
            order_id=state.order_id,
            risk=state.risk_result,
            revenue_at_risk=state.revenue_result,
            recommendation=recommendation,
            merchant_summary=state.merchant_summary,
            priority_orders=state.priority_orders,
            recovery_opportunity=state.recovery_opportunity,
            action_distribution=state.action_distribution,
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
        if state.merchant_summary:
            return self._natural_merchant_summary(state.merchant_summary)
        if state.priority_orders:
            return self._natural_priority_orders(state.priority_orders)
        if state.recovery_opportunity:
            return self._natural_recovery_opportunity(state.recovery_opportunity)
        if state.action_distribution:
            return self._natural_action_distribution(state.action_distribution)
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
            intent=state.intent,
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
            intent=state.intent,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _merchant_summary(self, state: AgentState) -> AgentResponse:
        try:
            summary = self._record_tool(state, "merchant_tool.get_revenue_summary", {}, self.tools.merchant_tool.get_revenue_summary)
        except Exception as exc:
            return self._failure(state, f"Unable to retrieve merchant revenue summary. Error: {exc}")
        state.merchant_summary = summary
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=None,
            tool="agent.merchant_summary",
            inputs_summary={"merchant_id": summary["merchant_id"]},
            outputs_summary=self._summary(summary),
        )
        return AgentResponse(
            status="ANALYSIS",
            summary="Merchant revenue summary retrieved.",
            natural_language_response=self._natural_merchant_summary(summary),
            session_id=state.session_id,
            intent=state.intent,
            merchant_summary=summary,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _priority_recovery(self, state: AgentState) -> AgentResponse:
        query = {"limit": 10, "minimum_rto_probability": 0.30, "minimum_order_value": 0.0}
        try:
            result = self._record_tool(
                state,
                "merchant_tool.get_priority_recovery_orders",
                query,
                lambda: self.tools.merchant_tool.get_priority_recovery_orders(**query),
            )
        except Exception as exc:
            return self._failure(state, f"Unable to retrieve priority recovery orders. Error: {exc}")
        state.priority_orders = result
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=None,
            tool="agent.priority_recovery",
            inputs_summary=query,
            outputs_summary={"orders": len(result["orders"]), "ranking_metric": result["ranking_metric"]},
        )
        return AgentResponse(
            status="ANALYSIS",
            summary="Priority recovery orders retrieved.",
            natural_language_response=self._natural_priority_orders(result),
            session_id=state.session_id,
            intent=state.intent,
            priority_orders=result,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _recovery_opportunity(self, state: AgentState) -> AgentResponse:
        try:
            result = self._record_tool(state, "merchant_tool.get_recovery_opportunity_summary", {}, self.tools.merchant_tool.get_recovery_opportunity_summary)
        except Exception as exc:
            return self._failure(state, f"Unable to retrieve recovery opportunity summary. Error: {exc}")
        state.recovery_opportunity = result
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=None,
            tool="agent.recovery_opportunity",
            inputs_summary={"merchant_id": result["merchant_id"]},
            outputs_summary=self._summary(result),
        )
        return AgentResponse(
            status="ANALYSIS",
            summary="Recovery opportunity summary retrieved.",
            natural_language_response=self._natural_recovery_opportunity(result),
            session_id=state.session_id,
            intent=state.intent,
            recovery_opportunity=result,
            audit_id=audit["audit_id"],
            tool_calls=[call.model_dump() for call in state.tool_calls],
        )

    def _action_distribution(self, state: AgentState) -> AgentResponse:
        try:
            result = self._record_tool(state, "merchant_tool.get_recovery_action_distribution", {}, self.tools.merchant_tool.get_recovery_action_distribution)
        except Exception as exc:
            return self._failure(state, f"Unable to retrieve recovery action distribution. Error: {exc}")
        state.action_distribution = result
        audit = self.tools.audit_tool.create_audit_event(
            session_id=state.session_id,
            order_id=None,
            tool="agent.action_distribution",
            inputs_summary={"merchant_id": result["merchant_id"]},
            outputs_summary={"orders_evaluated": result["orders_evaluated"]},
        )
        return AgentResponse(
            status="ANALYSIS",
            summary="Recovery action distribution retrieved.",
            natural_language_response=self._natural_action_distribution(result),
            session_id=state.session_id,
            intent=state.intent,
            action_distribution=result,
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
            intent=state.intent,
            order_id=state.order_id,
            merchant_summary=state.merchant_summary,
            priority_orders=state.priority_orders,
            recovery_opportunity=state.recovery_opportunity,
            action_distribution=state.action_distribution,
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

    def _log_result(self, response: AgentResponse) -> None:
        logger.info(
            "agent_request_completed",
            extra={
                "session_id": response.session_id,
                "provider": self.provider.name,
                "model": self.provider.model,
                "tool_calls": [call.get("tool_name") for call in response.tool_calls if "tool_name" in call],
                "tool_count": len([call for call in response.tool_calls if "tool_name" in call]),
                "agent_steps": len(response.tool_calls),
                "final_status": response.status,
                "intent": response.intent,
                "approval_required": response.approval_required,
                "execution_status": response.execution_status.get("status") if response.execution_status else None,
            },
        )

    def _natural_merchant_summary(self, summary: dict[str, Any]) -> str:
        return (
            f"Merchant {summary['merchant_id']} revenue summary\n\n"
            f"Total orders: {summary['total_orders']}\n"
            f"COD orders: {summary['cod_orders']}\n"
            f"Prepaid orders: {summary['prepaid_orders']}\n"
            f"Total order value: Rs {summary['total_order_value']:.2f}\n"
            f"Observed COD RTO value: Rs {summary['rto_value']:.2f}\n"
            f"Observed COD RTO rate: {summary['rto_rate']:.1%}\n"
            f"Predicted revenue at risk: Rs {summary['predicted_revenue_at_risk']:.2f}\n\n"
            f"Source: {summary['merchant_context_source']}."
        )

    def _natural_priority_orders(self, result: dict[str, Any]) -> str:
        orders = result["orders"]
        lines = [
            f"I found {len(orders)} priority recovery opportunities for merchant {result['merchant_id']}.",
            f"Ranking metric: {result['ranking_metric']}.",
        ]
        if orders:
            top = orders[0]
            lines.extend(
                [
                    "",
                    "Top opportunity:",
                    f"{top['order_id']}",
                    f"Order value: Rs {top['amount']:.2f}",
                    f"RTO probability: {top['rto_probability']:.1%}",
                    f"Expected revenue at risk: Rs {top['expected_revenue_at_risk']:.2f}",
                    f"Recommended action: {top['recommended_action']}",
                    f"Expected net recovery: Rs {top['expected_net_recovery']:.2f}",
                ]
            )
        return "\n".join(lines)

    def _natural_recovery_opportunity(self, result: dict[str, Any]) -> str:
        return (
            f"Recovery opportunity for merchant {result['merchant_id']}\n\n"
            f"Orders evaluated: {result['orders_evaluated']}\n"
            f"Orders with positive expected recovery: {result['orders_with_positive_expected_recovery']}\n"
            f"Total predicted revenue at risk: Rs {result['total_revenue_at_risk']:.2f}\n"
            f"Expected gross recovery: Rs {result['expected_gross_recovery']:.2f}\n"
            f"Expected intervention cost: Rs {result['expected_intervention_cost']:.2f}\n"
            f"Expected net recovery: Rs {result['expected_net_recovery']:.2f}\n\n"
            "These are synthetic evaluation assumptions, not real-world production claims."
        )

    def _natural_action_distribution(self, result: dict[str, Any]) -> str:
        lines = [
            f"Recovery action distribution for merchant {result['merchant_id']}",
            f"Orders evaluated: {result['orders_evaluated']}",
            "",
        ]
        for row in result["distribution"]:
            lines.append(
                f"- {row['action']}: {row['count']} orders ({row['percentage']:.1%}), "
                f"expected net recovery Rs {row['expected_net_recovery']:.2f}"
            )
        return "\n".join(lines)

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
