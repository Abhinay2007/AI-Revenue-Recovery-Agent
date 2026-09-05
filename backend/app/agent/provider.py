from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from groq import Groq


class AgentIntent(StrEnum):
    INSPECT_ORDER = "INSPECT_ORDER"
    RECOMMEND_RECOVERY = "RECOMMEND_RECOVERY"
    FIND_REVENUE_AT_RISK = "FIND_REVENUE_AT_RISK"
    REVENUE_SUMMARY = "REVENUE_SUMMARY"
    PRIORITY_RECOVERY = "PRIORITY_RECOVERY"
    RECOVERY_OPPORTUNITY = "RECOVERY_OPPORTUNITY"
    ACTION_DISTRIBUTION = "ACTION_DISTRIBUTION"
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

    def reset(self) -> None:
        return None

    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.model, "status": "ready"}


class LocalRuleBasedProvider(LLMProvider):
    name = "local"
    model = "rule-based-recovery-agent"

    ORDER_PATTERN = re.compile(r"\bORD-[A-Z0-9-]+\b", re.IGNORECASE)

    def plan(self, message: str) -> IntentPlan:
        normalized = message.lower()
        order_match = self.ORDER_PATTERN.search(message)
        order_id = order_match.group(0).upper() if order_match else None

        if any(term in normalized for term in ["how much revenue", "revenue is currently at risk", "merchant summary"]):
            return IntentPlan(AgentIntent.REVENUE_SUMMARY)
        if any(term in normalized for term in ["prioritize", "priority recovery", "top recovery"]):
            return IntentPlan(AgentIntent.PRIORITY_RECOVERY)
        if any(term in normalized for term in ["potentially recover", "recovery opportunity", "can the recovery system"]):
            return IntentPlan(AgentIntent.RECOVERY_OPPORTUNITY)
        if any(term in normalized for term in ["what actions", "action distribution", "actions is the recovery system"]):
            return IntentPlan(AgentIntent.ACTION_DISTRIBUTION)
        if any(term in normalized for term in ["highest revenue", "revenue at risk", "at-risk orders"]) and not order_id:
            return IntentPlan(AgentIntent.FIND_REVENUE_AT_RISK)
        if any(term in normalized for term in ["should i recover", "should we recover", "what should", "recommend", "do about", "do with"]):
            return IntentPlan(AgentIntent.RECOMMEND_RECOVERY, order_id)
        if any(term in normalized for term in ["recover", "execute", "run recovery"]):
            return IntentPlan(AgentIntent.REQUEST_EXECUTION, order_id)
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


class OllamaProvider(LLMProvider):
    """Ollama adapter using its native chat and tool-calling API."""

    supports_tool_calling = True

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120.0,
        client: Any | None = None,
    ) -> None:
        self.name = "ollama"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self._messages: list[dict[str, Any]] = []

    def plan(self, message: str) -> IntentPlan:
        return LocalRuleBasedProvider().plan(message)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        if not self._messages:
            self._messages = [self._translate_message(message) for message in messages]
        else:
            self._messages.extend(self._translate_message(message) for message in messages)

        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages,
            "stream": False,
            "tools": [self._translate_tool(tool) for tool in tools],
        }
        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=request_body)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("Ollama provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama provider request failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Ollama provider request failed: {exc}") from exc

        payload = response.json()
        allowed_tool_names = {
            str(tool.get("name") or tool.get("function", {}).get("name") or "")
            for tool in tools
        }
        provider_response = parse_ollama_response(payload, allowed_tool_names=allowed_tool_names)
        if provider_response.tool_calls:
            message: dict[str, Any] = {
                "role": "assistant",
                "content": provider_response.final_text or "",
                "tool_calls": [
                    {"function": {"name": call.name, "arguments": call.arguments}}
                    for call in provider_response.tool_calls
                ],
            }
            self._messages.append(message)
        return provider_response

    def status(self) -> dict[str, Any]:
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return {"provider": self.name, "model": self.model, "status": "ready"}
        except Exception as exc:
            return {
                "provider": self.name,
                "model": self.model,
                "status": "unavailable",
                "error": str(exc),
            }

    @staticmethod
    def _translate_message(message: dict[str, Any]) -> dict[str, Any]:
        if message.get("type") == "function_call_output":
            output = message.get("output", "")
            if not isinstance(output, str):
                output = json.dumps(output, sort_keys=True)
            return {"role": "tool", "content": output}
        translated = {key: value for key, value in message.items() if key in {"role", "content"}}
        return translated

    @staticmethod
    def _translate_tool(tool: dict[str, Any]) -> dict[str, Any]:
        if tool.get("type") == "function" and "function" in tool:
            function = dict(tool["function"])
        else:
            function = {
                "name": str(tool.get("name") or ""),
                "description": str(tool.get("description") or ""),
                "parameters": tool.get("parameters") or {},
            }
        function.pop("strict", None)
        return {"type": "function", "function": function}

    def reset(self) -> None:
        self._messages = []


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
        self._previous_response_id: str | None = None

    def plan(self, message: str) -> IntentPlan:
        return LocalRuleBasedProvider().plan(message)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        payload_input = messages
        request_body: dict[str, Any] = {
            "model": self.model,
            "input": payload_input,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
        }
        if self._previous_response_id and all(message.get("type") == "function_call_output" for message in messages):
            request_body["previous_response_id"] = self._previous_response_id
        try:
            response = self.client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=request_body,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("LLM provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc
        payload = response.json()
        self._previous_response_id = str(payload.get("id") or self._previous_response_id or "")
        return parse_openai_response(payload)

    def reset(self) -> None:
        self._previous_response_id = None


class GroqProvider(LLMProvider):
    supports_tool_calling = True

    def __init__(self, model: str, api_key: str | None, timeout_seconds: float = 20.0, client: Any | None = None) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=groq")
        self.name = "groq"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.client = client or Groq(api_key=api_key, timeout=timeout_seconds)
        self._messages: list[dict[str, Any]] = []

    def plan(self, message: str) -> IntentPlan:
        return LocalRuleBasedProvider().plan(message)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: str = "auto") -> ProviderResponse:
        if not self._messages:
            self._messages = [dict(message) for message in messages]
        else:
            self._messages.extend(self._translate_tool_output(message) for message in messages)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                tools=[self._translate_tool(tool) for tool in tools],
                tool_choice=tool_choice,
                parallel_tool_calls=False,
            )
        except Exception as exc:
            if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
                raise TimeoutError("Groq provider request timed out") from exc
            if getattr(exc, "status_code", None) == 429:
                raise RuntimeError("Groq provider rate limited") from exc
            raise RuntimeError(f"Groq provider request failed: {exc}") from exc

        provider_response = parse_groq_response(response)
        if provider_response.tool_calls:
            self._messages.append({
                "role": "assistant",
                "content": provider_response.final_text,
                "tool_calls": [
                    {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
                    for call in provider_response.tool_calls
                ],
            })
        return provider_response

    @staticmethod
    def _translate_tool_output(message: dict[str, Any]) -> dict[str, Any]:
        output = message.get("output", "")
        if not isinstance(output, str):
            output = json.dumps(output, sort_keys=True)
        return {"role": "tool", "tool_call_id": str(message.get("call_id") or ""), "content": output}

    @staticmethod
    def _translate_tool(tool: dict[str, Any]) -> dict[str, Any]:
        if tool.get("type") == "function" and "function" in tool:
            function = dict(tool["function"])
        else:
            function = {
                "name": str(tool.get("name") or ""),
                "description": str(tool.get("description") or ""),
                "parameters": tool.get("parameters") or {},
            }
            if "strict" in tool:
                function["strict"] = bool(tool["strict"])
        parameters = dict(function.get("parameters") or {})
        if parameters.get("type") == "object":
            parameters.setdefault("properties", {})
            parameters.setdefault("required", [])
        else:
            parameters = {"type": "object", "properties": {}, "required": []}
        function["parameters"] = parameters
        return {"type": "function", "function": function}

    def reset(self) -> None:
        self._messages = []


def parse_groq_response(payload: Any) -> ProviderResponse:
    if hasattr(payload, "choices"):
        choice = payload.choices[0] if payload.choices else None
        message = getattr(choice, "message", None) if choice else None
    else:
        message = payload.get("message") if isinstance(payload, dict) else None
    if message is None:
        raise ValueError("malformed Groq response: missing message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    final_text = content if isinstance(content, str) else None
    raw_tool_calls = getattr(message, "tool_calls", None)
    if raw_tool_calls is None and isinstance(message, dict):
        raw_tool_calls = message.get("tool_calls")
    tool_calls: list[ProviderToolCall] = []
    for raw_call in raw_tool_calls or []:
        function = getattr(raw_call, "function", None)
        if function is None and isinstance(raw_call, dict):
            function = raw_call.get("function")
        if function is None:
            raise ValueError("malformed Groq response: missing tool function")
        name = getattr(function, "name", None) if not isinstance(function, dict) else function.get("name")
        arguments = getattr(function, "arguments", None) if not isinstance(function, dict) else function.get("arguments")
        try:
            parsed_arguments = json.loads(arguments or "{}") if isinstance(arguments, str) else dict(arguments or {})
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"malformed tool arguments for {name}") from exc
        call_id = getattr(raw_call, "id", None) if not isinstance(raw_call, dict) else raw_call.get("id")
        tool_calls.append(ProviderToolCall(id=str(call_id or f"call_{len(tool_calls)}"), name=str(name), arguments=parsed_arguments))
    if final_text is None and not tool_calls:
        raise ValueError("malformed Groq response: no final text or tool calls")
    return ProviderResponse(final_text=final_text, tool_calls=tool_calls, raw=payload)


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


def parse_ollama_response(
    payload: dict[str, Any],
    allowed_tool_names: set[str] | None = None,
) -> ProviderResponse:
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        raise ValueError("malformed Ollama response: missing message")
    final_text = message.get("content")
    if final_text is not None and not isinstance(final_text, str):
        raise ValueError("malformed Ollama response: invalid message content")
    tool_calls: list[ProviderToolCall] = []
    for index, raw_call in enumerate(message.get("tool_calls") or []):
        function = raw_call.get("function") if isinstance(raw_call, dict) else None
        if not isinstance(function, dict) or not function.get("name"):
            raise ValueError("malformed Ollama response: missing tool function")
        name = str(function["name"])
        if allowed_tool_names is not None and name not in allowed_tool_names:
            raise ValueError(f"unsupported Ollama tool: {name}")
        raw_arguments = function.get("arguments") or {}
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"malformed tool arguments for {function.get('name')}") from exc
        tool_calls.append(
            ProviderToolCall(
                id=str(raw_call.get("id") or f"ollama_call_{index}"),
                name=name,
                arguments=arguments,
            )
        )
    if not tool_calls and isinstance(final_text, str) and "<|python_tag|>" in final_text:
        compatibility_call = _parse_ollama_python_tag(final_text, allowed_tool_names)
        return ProviderResponse(final_text=None, tool_calls=[compatibility_call], raw=payload)
    if final_text is None and not tool_calls:
        raise ValueError("malformed Ollama response: no final text or tool calls")
    return ProviderResponse(final_text=final_text, tool_calls=tool_calls, raw=payload)


def _parse_ollama_python_tag(content: str, allowed_tool_names: set[str] | None) -> ProviderToolCall:
    match = re.fullmatch(r"\s*<\|python_tag\|>\s*(\{.*\})\s*", content, flags=re.DOTALL)
    if match is None:
        raise ValueError("malformed Ollama python_tag tool call")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("malformed Ollama python_tag JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
        raise ValueError("malformed Ollama python_tag tool call")
    name = payload["name"]
    if allowed_tool_names is not None and name not in allowed_tool_names:
        raise ValueError(f"unsupported Ollama tool: {name}")
    arguments = payload.get("parameters", {})
    if not isinstance(arguments, dict):
        raise ValueError("malformed Ollama python_tag parameters")
    return ProviderToolCall(id="ollama_python_tag_0", name=name, arguments=arguments)


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


def build_provider(
    provider_name: str,
    model: str,
    api_key: str | None = None,
    timeout_seconds: float = 20.0,
    ollama_base_url: str = "http://localhost:11434",
) -> LLMProvider:
    if provider_name == "ollama":
        return OllamaProvider(model=model, base_url=ollama_base_url, timeout_seconds=timeout_seconds)
    if provider_name == "local":
        return LocalRuleBasedProvider()
    if provider_name == "openai":
        return OpenAIResponsesProvider(model=model, api_key=api_key, timeout_seconds=timeout_seconds)
    if provider_name == "groq":
        return GroqProvider(model=model, api_key=api_key, timeout_seconds=timeout_seconds)
    if provider_name == "hosted":
        return HostedProvider(model=model, api_key=api_key)
    if provider_name == "modal":
        return ModalProvider(model=model)
    raise ValueError(f"unsupported LLM provider: {provider_name}")
