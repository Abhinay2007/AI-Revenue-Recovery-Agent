"""Developer-only smoke test for the host Ollama tool-calling provider."""

from __future__ import annotations

import sys
from pathlib import Path
from time import monotonic

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.agent.agent import RevenueRecoveryAgent
from app.agent.provider import OllamaProvider
from app.agent.schemas import AgentChatRequest
from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    provider = OllamaProvider(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.llm_request_timeout_seconds,
    )
    started = monotonic()
    status = provider.status()
    if status["status"] != "ready":
        print(f"Ollama unavailable: {status.get('error', 'service is not ready')}", file=sys.stderr)
        return 1

    response = RevenueRecoveryAgent(provider=provider).chat(
        AgentChatRequest(message="Analyze order ORD-0042-0009754. Use the available tools and explain the recovery recommendation.")
    )
    elapsed = monotonic() - started
    tool_names = [call.get("tool_name") for call in response.tool_calls if call.get("tool_name")]
    expected = ["get_order", "get_rto_risk", "calculate_revenue_at_risk", "evaluate_recovery"]
    if response.status == "FAILURE" or not all(name in tool_names for name in expected):
        print(f"Ollama smoke test failed: {response.summary}", file=sys.stderr)
        return 1

    print(f"provider: {provider.name}")
    print(f"model: {provider.model}")
    print(f"tool_calls: {', '.join(tool_names)}")
    print(f"duration_seconds: {elapsed:.2f}")
    print("grounded_response:")
    print(response.natural_language_response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
