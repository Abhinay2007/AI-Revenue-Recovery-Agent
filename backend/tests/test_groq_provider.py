import json

import pytest

from app.agent.provider import GroqProvider, ProviderToolCall, build_provider, parse_groq_response


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses=None, error=None):
        self.completions = FakeCompletions(responses, error)

    @property
    def chat(self):
        return self


def test_groq_provider_normal_completion():
    client = FakeClient([FakeResponse(FakeMessage(content="Hello from Groq"))])
    provider = GroqProvider(model="llama-test", api_key="key", client=client)

    response = provider.complete([{"role": "user", "content": "hi"}], [])

    assert response.final_text == "Hello from Groq"
    assert client.completions.requests[0]["model"] == "llama-test"


def test_groq_provider_parses_tool_call():
    response = parse_groq_response(
        FakeResponse(FakeMessage(tool_calls=[FakeToolCall("call-1", "get_order", '{"order_id":"ORD-1"}')]))
    )

    assert response.tool_calls == [ProviderToolCall(id="call-1", name="get_order", arguments={"order_id": "ORD-1"})]


def test_groq_provider_preserves_assistant_tool_call_for_continuation():
    client = FakeClient(
        [
            FakeResponse(FakeMessage(tool_calls=[FakeToolCall("call-1", "get_order", '{"order_id":"ORD-1"}')])),
            FakeResponse(FakeMessage(content="Done.")),
        ]
    )
    provider = GroqProvider(model="llama-test", api_key="key", client=client)
    tools = [{"type": "function", "name": "get_order", "description": "Get order", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}]

    first = provider.complete([{"role": "user", "content": "Analyze ORD-1"}], tools)
    second = provider.complete([{"type": "function_call_output", "call_id": first.tool_calls[0].id, "output": json.dumps({"order_id": "ORD-1"})}], tools)

    assert second.final_text == "Done."
    messages = client.completions.requests[1]["messages"]
    assert messages[-2]["role"] == "assistant"
    assert messages[-2]["tool_calls"][0]["id"] == "call-1"
    assert messages[-1] == {"role": "tool", "tool_call_id": "call-1", "content": '{"order_id": "ORD-1"}'}


def test_groq_provider_malformed_arguments_fail_before_tool_result_continuation():
    client = FakeClient([FakeResponse(FakeMessage(tool_calls=[FakeToolCall("call-1", "get_order", "{" )]))])
    provider = GroqProvider(model="llama-test", api_key="key", client=client)

    with pytest.raises(ValueError, match="malformed tool arguments"):
        provider.complete([{"role": "user", "content": "hi"}], [])

    assert len(client.completions.requests) == 1


def test_groq_provider_timeout_is_safe_error():
    provider = GroqProvider(model="llama-test", api_key="key", client=FakeClient(error=TimeoutError("slow")))

    with pytest.raises(TimeoutError, match="timed out"):
        provider.complete([], [])


def test_groq_provider_api_error_is_safe_error():
    provider = GroqProvider(model="llama-test", api_key="key", client=FakeClient(error=RuntimeError("upstream")))

    with pytest.raises(RuntimeError, match="request failed"):
        provider.complete([], [])


def test_groq_provider_requires_api_key():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        GroqProvider(model="llama-test", api_key=None, client=FakeClient())


def test_groq_provider_translates_empty_and_parameterized_tools():
    client = FakeClient([FakeResponse(FakeMessage(content="Done."))])
    provider = GroqProvider(model="llama-test", api_key="key", client=client)

    provider.complete(
        [{"role": "user", "content": "hi"}],
        [
            {"type": "function", "name": "summary", "description": "Summary", "parameters": {"type": "object", "required": []}},
            {"type": "function", "name": "get_order", "description": "Get order", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
        ],
    )

    translated = client.completions.requests[0]["tools"]
    assert translated[0]["function"]["parameters"] == {"type": "object", "properties": {}, "required": []}
    assert translated[1]["function"]["parameters"]["required"] == ["order_id"]


def test_groq_provider_parses_multiple_tool_calls():
    response = parse_groq_response(
        FakeResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall("call-1", "get_order", '{"order_id":"ORD-1"}'),
                    FakeToolCall("call-2", "get_rto_risk", '{"order_id":"ORD-1"}'),
                ]
            )
        )
    )

    assert [call.name for call in response.tool_calls] == ["get_order", "get_rto_risk"]


def test_groq_provider_selection():
    assert isinstance(build_provider("groq", "llama-test", api_key="key"), GroqProvider)
