from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx


class AgentIntent(StrEnum):
    INSPECT_ORDER = "INSPECT_ORDER"
    RECOMMEND_RECOVERY = "RECOMMEND_RECOVERY"
    FIND_REVENUE_AT_RISK = "FIND_REVENUE_AT_RISK"
    REQUEST_EXECUTION = "REQUEST_EXECUTION"
    UNKNOWN = "UNKNOWN"


class IntentPlan:
    def __init__(self, intent: AgentIntent, order_id: str | None = None) -> None:
        self.intent = intent
        self.order_id = order_id


@dataclass(frozen=True)
class ProviderToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ProviderResponse:
    final_text: str | None = None
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    name: str
    model: str
    supports_tool_calling = False

    @abstractmethod
    def plan(self, message: str) -> IntentPlan:
        raise NotImplementedError

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        raise RuntimeError(f"provider {self.name} does not support tool calling")


class LocalRuleBasedProvider(LLMProvider):
    name = "local"
    model = "rule-based-recovery-agent"

    ORDER_PATTERN = re.compile(r"\bORD-[A-Z0-9-]+\b", re.IGNORECASE)

    def plan(self, message: str) -> IntentPlan:
        normalized = message.lower()
        order_match = self.ORDER_PATTERN.search(message)
        order_id = order_match.group(0).upper() if order_match else None

        if any(term in normalized for term in ["highest revenue", "revenue at risk", "at-risk orders"]) and not order_id:
            return IntentPlan(AgentIntent.FIND_REVENUE_AT_RISK)
        if any(term in normalized for term in ["recover", "execute", "run recovery"]):
            return IntentPlan(AgentIntent.REQUEST_EXECUTION, order_id)
        if any(term in normalized for term in ["what should", "recommend", "do about", "do with"]):
            return IntentPlan(AgentIntent.RECOMMEND_RECOVERY, order_id)
        if any(term in normalized for term in ["analyze", "inspect", "check", "risk"]) and order_id:
            return IntentPlan(AgentIntent.INSPECT_ORDER, order_id)
        if order_id:
            return IntentPlan(AgentIntent.INSPECT_ORDER, order_id)
        return IntentPlan(AgentIntent.UNKNOWN)


class HostedProvider(LLMProvider):
    def __init__(self, model: str, api_key: str | None) -> None:
        self.name = "hosted"
        self.model = model
        self.api_key = api_key

    def plan(self, message: str) -> IntentPlan:
        raise RuntimeError("hosted provider requires the tool-calling interface")


class ModalProvider(LLMProvider):
    def __init__(self, model: str) -> None:
        self.name = "modal"
        self.model = model

    def plan(self, message: str) -> IntentPlan:
        raise RuntimeError("Modal provider is reserved for a future milestone")


class OpenAIResponsesProvider(LLMProvider):
    supports_tool_calling = True

    def __init__(
        self,
        model: str,
        api_key: str | None,
        timeout_seconds: float = 20.0,
        base_url: str = "https://api.openai.com/v1/responses",
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=openai")
        self.name = "openai"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def plan(self, message: str) -> IntentPlan:
        return LocalRuleBasedProvider().plan(message)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        try:
            response = self.client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "input": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "parallel_tool_calls": False,
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("LLM provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc
        payload = response.json()
        return parse_openai_response(payload)


def parse_openai_response(payload: dict[str, Any]) -> ProviderResponse:
    tool_calls: list[ProviderToolCall] = []
    final_text = payload.get("output_text")
    for item in payload.get("output", []):
        item_type = item.get("type")
        if item_type in {"function_call", "tool_call"}:
            raw_arguments = item.get("arguments") or item.get("input") or "{}"
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"malformed tool arguments for {item.get('name')}") from exc
            tool_calls.append(
                ProviderToolCall(
                    id=str(item.get("call_id") or item.get("id") or f"call_{len(tool_calls)}"),
                    name=str(item.get("name")),
                    arguments=arguments,
                )
            )
        elif item_type == "message" and not final_text:
            content = item.get("content", [])
            text_parts = [part.get("text", "") for part in content if part.get("type") in {"output_text", "text"}]
            final_text = "\n".join(part for part in text_parts if part)
    if final_text is None and not tool_calls:
        raise ValueError("malformed provider response: no final text or tool calls")
    return ProviderResponse(final_text=final_text, tool_calls=tool_calls, raw=payload)


class MockToolCallingProvider(LLMProvider):
    supports_tool_calling = True
    name = "mock"
    model = "mock-tool-calling-model"

    def __init__(self, responses: list[ProviderResponse] | None = None, fail: Exception | None = None) -> None:
        self.responses = responses or []
        self.fail = fail
        self.calls = 0

    def plan(self, message: str) -> IntentPlan:
        return LocalRuleBasedProvider().plan(message)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        if self.fail is not None:
            raise self.fail
        if self.calls >= len(self.responses):
            return ProviderResponse(final_text="Done.")
        response = self.responses[self.calls]
        self.calls += 1
        return response


def build_provider(provider_name: str, model: str, api_key: str | None = None, timeout_seconds: float = 20.0) -> LLMProvider:
    if provider_name == "local":
        return LocalRuleBasedProvider()
    if provider_name == "openai":
        return OpenAIResponsesProvider(model=model, api_key=api_key, timeout_seconds=timeout_seconds)
    if provider_name == "hosted":
        return HostedProvider(model=model, api_key=api_key)
    if provider_name == "modal":
        return ModalProvider(model=model)
    raise ValueError(f"unsupported LLM provider: {provider_name}")
