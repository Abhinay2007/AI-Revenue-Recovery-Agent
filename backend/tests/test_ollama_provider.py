import json

import httpx
import pytest

from app.agent.agent import AgentToolset, RevenueRecoveryAgent
from app.agent.provider import OllamaProvider, ProviderToolCall, build_provider, parse_ollama_response
from app.agent.schemas import AgentChatRequest


class FakeResponse:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, posts=None, get_response=None, error=None):
        self.posts = list(posts or [])
        self.get_response = get_response
        self.error = error
        self.post_requests = []

    def post(self, *args, **kwargs):
        self.post_requests.append({"args": args, "kwargs": kwargs})
        if self.error:
            raise self.error
        return self.posts.pop(0)

    def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.get_response


def test_ollama_provider_parses_native_tool_call():
    response = parse_ollama_response(
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "get_order", "arguments": {"order_id": "ORD-1"}}}],
            }
        }
    )

    assert response.tool_calls == [ProviderToolCall(id="ollama_call_0", name="get_order", arguments={"order_id": "ORD-1"})]


def test_ollama_provider_parses_python_tag_tool_call_without_executing_code():
    response = parse_ollama_response(
        {"message": {"content": '<|python_tag|>{"name":"get_rto_risk","parameters":{"order_id":"RZP-TEST-8FCD7B2B5AE7483C"}}'}},
        allowed_tool_names={"get_rto_risk"},
    )

    assert response.tool_calls == [
        ProviderToolCall(
            id="ollama_python_tag_0",
            name="get_rto_risk",
            arguments={"order_id": "RZP-TEST-8FCD7B2B5AE7483C"},
        )
    ]


def test_ollama_python_tag_rejects_arbitrary_python_and_unknown_tools():
    with pytest.raises(ValueError, match="python_tag tool call"):
        parse_ollama_response({"message": {"content": "<|python_tag|>__import__('os').system('id')"}}, {"get_order"})

    with pytest.raises(ValueError, match="unsupported Ollama tool"):
        parse_ollama_response(
            {"message": {"content": '<|python_tag|>{"name":"run_shell","parameters":{}}'}},
            {"get_order"},
        )


def test_ollama_python_tag_continues_existing_agent_tool_loop():
    client = FakeClient(
        posts=[
            FakeResponse({"message": {"content": "", "tool_calls": [{"function": {"name": "get_order", "arguments": {"order_id": "ORD-0042-0009754"}}}]}}),
            FakeResponse({"message": {"content": '<|python_tag|>{"name":"get_rto_risk","parameters":{"order_id":"ORD-0042-0009754"}}'}}),
            FakeResponse({"message": {"content": "", "tool_calls": [{"function": {"name": "calculate_revenue_at_risk", "arguments": {"order_id": "ORD-0042-0009754"}}}]}}),
            FakeResponse({"message": {"content": '<|python_tag|>{"name":"evaluate_recovery","parameters":{"order_id":"ORD-0042-0009754"}}'}}),
            FakeResponse({"message": {"content": "The deterministic recovery recommendation is ready."}}),
        ]
    )
    provider = OllamaProvider(model="llama3.2:latest", client=client)
    agent = RevenueRecoveryAgent(provider=provider, tools=AgentToolset())

    response = agent.chat(AgentChatRequest(message="Analyze ORD-0042-0009754"))

    assert response.status == "RECOMMENDATION"
    assert response.approval_required is False
    assert [call["tool_name"] for call in response.tool_calls if "tool_name" in call] == [
        "get_order",
        "get_rto_risk",
        "calculate_revenue_at_risk",
        "evaluate_recovery",
    ]
    assert response.recommendation is not None


def test_ollama_provider_continues_with_tool_result():
    client = FakeClient(
        posts=[
            FakeResponse({"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_order", "arguments": {"order_id": "ORD-1"}}}]}}),
            FakeResponse({"message": {"role": "assistant", "content": "The order is ready."}}),
        ]
    )
    provider = OllamaProvider(model="llama3.2:latest", client=client)
    tools = [{"type": "function", "name": "get_order", "description": "Get order", "parameters": {"type": "object"}, "strict": True}]

    first = provider.complete([{"role": "user", "content": "Analyze ORD-1"}], tools)
    second = provider.complete(
        [{"type": "function_call_output", "call_id": first.tool_calls[0].id, "output": json.dumps({"order_id": "ORD-1"})}],
        tools,
    )

    assert second.final_text == "The order is ready."
    second_messages = client.post_requests[1]["kwargs"]["json"]["messages"]
    assert second_messages[-1] == {"role": "tool", "content": '{"order_id": "ORD-1"}'}


def test_ollama_provider_uses_native_endpoint_and_translates_tools():
    client = FakeClient(posts=[FakeResponse({"message": {"role": "assistant", "content": "Done."}})])
    provider = OllamaProvider(model="llama3.2:latest", base_url="http://ollama:11434", client=client)

    provider.complete([{"role": "user", "content": "hi"}], [])

    request = client.post_requests[0]
    assert request["args"] == ("http://ollama:11434/api/chat",)
    assert request["kwargs"]["json"]["stream"] is False
    assert request["kwargs"]["json"]["model"] == "llama3.2:latest"


def test_ollama_provider_handles_timeout_without_fabricating_result():
    provider = OllamaProvider(model="llama3.2:latest", client=FakeClient(error=httpx.TimeoutException("slow")))

    with pytest.raises(TimeoutError, match="timed out"):
        provider.complete([], [])


def test_ollama_provider_rejects_malformed_response():
    with pytest.raises(ValueError, match="missing message"):
        parse_ollama_response({})

    with pytest.raises(ValueError, match="malformed tool arguments"):
        parse_ollama_response({"message": {"tool_calls": [{"function": {"name": "get_order", "arguments": "{"}}]}})


def test_ollama_provider_status_is_safe_and_does_not_require_api_key():
    client = FakeClient(get_response=FakeResponse({"models": [{"name": "llama3.2:latest"}]}))
    provider = OllamaProvider(model="llama3.2:latest", client=client)

    assert provider.status() == {"provider": "ollama", "model": "llama3.2:latest", "status": "ready"}


def test_ollama_provider_unavailable_status_is_explicit():
    provider = OllamaProvider(model="llama3.2:latest", client=FakeClient(error=httpx.ConnectError("offline")))

    status = provider.status()

    assert status["provider"] == "ollama"
    assert status["status"] == "unavailable"
    assert "offline" in status["error"]


def test_ollama_provider_selection():
    provider = build_provider("ollama", "llama3.2:latest", timeout_seconds=120, ollama_base_url="http://ollama:11434")

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://ollama:11434"
