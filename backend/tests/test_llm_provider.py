import httpx
import pytest

from app.agent.provider import (
    MockToolCallingProvider,
    OpenAIResponsesProvider,
    ProviderResponse,
    ProviderToolCall,
    parse_openai_response,
)


class FakeResponse:
    def __init__(self, payload, status_error: Exception | None = None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.requests = []

    def post(self, *args, **kwargs):
        self.requests.append({"args": args, "kwargs": kwargs})
        if self.error:
            raise self.error
        return self.response


def test_openai_provider_successful_text_response():
    client = FakeClient(FakeResponse({"output_text": "Hello"}))
    provider = OpenAIResponsesProvider(model="gpt-test", api_key="key", client=client)

    response = provider.complete([{"role": "user", "content": "hi"}], [])

    assert response.final_text == "Hello"
    assert client.requests[0]["kwargs"]["headers"]["Authorization"] == "Bearer key"


def test_openai_provider_tool_call_response():
    payload = {
        "output": [
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "get_order",
                "arguments": '{"order_id":"ORD-1"}',
            }
        ]
    }

    response = parse_openai_response(payload)

    assert response.tool_calls == [ProviderToolCall(id="call-1", name="get_order", arguments={"order_id": "ORD-1"})]


def test_openai_provider_uses_previous_response_id_for_tool_outputs():
    client = FakeClient(FakeResponse({"id": "resp_1", "output": [{"type": "function_call", "call_id": "call-1", "name": "get_order", "arguments": "{}"}]}))
    provider = OpenAIResponsesProvider(model="gpt-test", api_key="key", client=client)

    provider.complete([{"role": "user", "content": "hi"}], [])
    client.response = FakeResponse({"id": "resp_2", "output_text": "Done"})
    provider.complete([{"type": "function_call_output", "call_id": "call-1", "output": "{}"}], [])

    assert client.requests[1]["kwargs"]["json"]["previous_response_id"] == "resp_1"


def test_openai_provider_reset_clears_response_continuation():
    client = FakeClient(FakeResponse({"id": "resp_1", "output_text": "Hello"}))
    provider = OpenAIResponsesProvider(model="gpt-test", api_key="key", client=client)

    provider.complete([{"role": "user", "content": "hi"}], [])
    provider.reset()
    provider.complete([{"role": "user", "content": "new chat"}], [])

    assert "previous_response_id" not in client.requests[1]["kwargs"]["json"]


def test_openai_provider_malformed_response_fails():
    with pytest.raises(ValueError, match="no final text"):
        parse_openai_response({"output": []})


def test_openai_provider_malformed_tool_arguments_fail():
    with pytest.raises(ValueError, match="malformed tool arguments"):
        parse_openai_response({"output": [{"type": "function_call", "name": "get_order", "arguments": "{"}]})


def test_openai_provider_failure_and_timeout():
    provider = OpenAIResponsesProvider(model="gpt-test", api_key="key", client=FakeClient(error=httpx.TimeoutException("slow")))

    with pytest.raises(TimeoutError):
        provider.complete([], [])

    provider = OpenAIResponsesProvider(model="gpt-test", api_key="key", client=FakeClient(error=httpx.HTTPError("boom")))
    with pytest.raises(RuntimeError, match="request failed"):
        provider.complete([], [])


def test_openai_provider_requires_api_key():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenAIResponsesProvider(model="gpt-test", api_key=None)


def test_mock_provider_returns_scripted_tool_calls():
    provider = MockToolCallingProvider(
        [ProviderResponse(tool_calls=[ProviderToolCall(id="1", name="get_order", arguments={"order_id": "ORD-1"})])]
    )

    response = provider.complete([], [])

    assert response.tool_calls[0].name == "get_order"
