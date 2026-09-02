"""Provider-layer correctness: request shape, streaming, timeout, and
circuit-breaker behavior -- the properties that matter without needing
real credentials or a running local server."""
from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.providers.base import BaseProvider, CircuitOpenError
from app.providers.ollama import OllamaProvider


@respx.mock
async def test_ollama_parses_ndjson_stream_into_full_text():
    respx.post("http://fake-ollama/api/generate").mock(
        return_value=httpx.Response(200, text='{"response":"Hel","done":false}\n{"response":"lo","done":true}\n')
    )
    provider = OllamaProvider(base_url="http://fake-ollama")
    result = await provider.complete("hi", model="llama3")
    assert result == "Hello"


@respx.mock
async def test_ollama_streaming_invokes_on_token_per_chunk():
    respx.post("http://fake-ollama/api/generate").mock(
        return_value=httpx.Response(200, text='{"response":"A","done":false}\n{"response":"B","done":true}\n')
    )
    provider = OllamaProvider(base_url="http://fake-ollama")
    seen: list[str] = []

    async def on_token(piece: str) -> None:
        seen.append(piece)

    await provider.complete("hi", model="llama3", on_token=on_token)
    assert seen == ["A", "B"]


@respx.mock
async def test_ollama_health_check_reports_unreachable_on_connection_error():
    respx.get("http://fake-ollama/api/tags").mock(side_effect=httpx.ConnectError("refused"))
    provider = OllamaProvider(base_url="http://fake-ollama")
    health = await provider.health_check()
    assert health.reachable is False
    assert "refused" in (health.detail or "")


class _SlowProvider(BaseProvider):
    name = "ollama"

    async def _do_complete(self, prompt, **kwargs):
        await asyncio.sleep(0.2)
        return "done"

    async def _do_health_check(self) -> str:
        return "ok"


async def test_timeout_triggers_after_configured_duration():
    provider = _SlowProvider(default_timeout_s=0.05)
    with pytest.raises(asyncio.TimeoutError):
        await provider.complete("hi", model="m")


class _FlakyProvider(BaseProvider):
    name = "ollama"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = 0

    async def _do_complete(self, prompt, **kwargs):
        self.calls += 1
        raise RuntimeError("boom")

    async def _do_health_check(self) -> str:
        return "ok"


async def test_circuit_breaker_opens_after_n_failures_and_short_circuits():
    provider = _FlakyProvider(failure_threshold=2, cooldown_s=60)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await provider.complete("hi", model="m")
    assert provider.calls == 2

    with pytest.raises(CircuitOpenError):
        await provider.complete("hi", model="m")
    # Short-circuited: the underlying call was never attempted a 3rd time.
    assert provider.calls == 2
