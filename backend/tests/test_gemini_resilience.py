"""Gemini resilience: a 404 (model id the API doesn't serve) is its own,
non-retried, remembered error; ListModels discovery narrows the fallback chain
to models the key actually has; and all of it fails OPEN so a discovery hiccup
can never break a working configuration. Live logs showed 14 of 46 calls were
404s against invented model ids -- each one a wasted call and a noisy row."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from app import llm_call_logging as lcl
from app.providers import gemini_quota
from app.providers.gemini import GeminiProvider, ModelUnavailableError

BASE = GeminiProvider.BASE_URL
GEN = lambda m: f"{BASE}/models/{m}:generateContent"  # noqa: E731
OK = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}


def _listing(*names, methods=("generateContent",), token=None):
    body = {"models": [{"name": f"models/{n}", "supportedGenerationMethods": list(methods)} for n in names]}
    if token:
        body["nextPageToken"] = token
    return httpx.Response(200, json=body)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    gemini_quota.reset_unavailable()
    gemini_quota._call_log.clear()
    monkeypatch.setattr(lcl.db, "create_llm_call", lambda *a, **k: None)
    monkeypatch.setattr(lcl.db, "update_llm_call", lambda *a, **k: None)
    yield
    gemini_quota.reset_unavailable()


@pytest.fixture
def provider(monkeypatch):
    p = GeminiProvider(api_key="test-key-123")
    monkeypatch.setattr(lcl, "get_provider", lambda _name: p)
    return p


# ------------------------------------------------------------------- 404 --


@respx.mock
async def test_a_404_raises_model_unavailable_and_is_not_retried():
    route = respx.post(GEN("gemini-nope")).mock(return_value=httpx.Response(404, json={"error": {"message": "not found"}}))
    with pytest.raises(ModelUnavailableError, match="HTTP 404"):
        await GeminiProvider(api_key="k").complete("hi", model="gemini-nope")
    assert route.call_count == 1  # 429/503 retry; a 404 never will


@respx.mock
async def test_429_and_503_are_still_ordinary_retryable_errors_not_model_unavailable(monkeypatch):
    monkeypatch.setattr("app.providers.gemini._BACKOFF_BASE_S", {429: 0.0, 503: 0.0})
    respx.post(GEN("gemini-busy")).mock(return_value=httpx.Response(429))
    with pytest.raises(RuntimeError) as e:
        await GeminiProvider(api_key="k").complete("hi", model="gemini-busy")
    assert not isinstance(e.value, ModelUnavailableError) and "HTTP 429" in str(e.value)


@respx.mock
async def test_error_text_never_contains_the_api_key():
    respx.post(GEN("gemini-nope")).mock(return_value=httpx.Response(404))
    with pytest.raises(ModelUnavailableError) as e:
        await GeminiProvider(api_key="super-secret-key").complete("hi", model="gemini-nope")
    assert "super-secret-key" not in str(e.value)


@respx.mock
async def test_404_marks_the_model_and_later_calls_skip_it_entirely(provider):
    bad = respx.post(GEN("gemini-3.8-flash")).mock(return_value=httpx.Response(404))
    good = respx.post(GEN("gemini-2.5-flash")).mock(return_value=httpx.Response(200, json=OK))
    respx.get(f"{BASE}/models").mock(side_effect=httpx.ConnectError("no listing"))  # discovery unavailable
    for _ in range(3):
        text, used = await lcl.complete_with_logging("gemini", "gemini-3.8-flash", "hi", fallback_models=["gemini-2.5-flash"])
        assert (text, used) == ("hello", "gemini-2.5-flash")
    assert bad.call_count == 1  # tried once, remembered, never again
    assert good.call_count == 3
    assert gemini_quota.is_unavailable("gemini-3.8-flash")


def test_the_unavailable_memory_expires():
    gemini_quota.mark_unavailable("m", ttl=-1)  # already expired
    assert not gemini_quota.is_unavailable("m")
    gemini_quota.mark_unavailable("m", ttl=3600)
    assert gemini_quota.is_unavailable("m") and 3500 < gemini_quota.unavailable_models()["m"] <= 3600


# ------------------------------------------------------------- discovery --


@respx.mock
async def test_available_models_lists_only_generate_content_models_and_strips_the_prefix():
    respx.get(f"{BASE}/models").mock(
        side_effect=[_listing("gemini-2.5-flash", "gemini-flash-latest"), _listing("text-embedding-004", methods=("embedContent",))]
    )
    p = GeminiProvider(api_key="k")
    assert await p.available_models() == {"gemini-2.5-flash", "gemini-flash-latest"}


@respx.mock
async def test_available_models_follows_pagination():
    route = respx.get(f"{BASE}/models").mock(side_effect=[_listing("a", token="p2"), _listing("b", token="p3"), _listing("c")])
    assert await GeminiProvider(api_key="k").available_models() == {"a", "b", "c"}
    assert route.call_count == 3


@respx.mock
async def test_available_models_is_cached_and_a_failure_is_cached_briefly_too():
    ok = respx.get(f"{BASE}/models").mock(return_value=_listing("a"))
    p = GeminiProvider(api_key="k")
    await p.available_models()
    await p.available_models()
    assert ok.call_count == 1
    respx.reset()
    bad = respx.get(f"{BASE}/models").mock(return_value=httpx.Response(500))
    q = GeminiProvider(api_key="k")
    assert await q.available_models() is None
    assert await q.available_models() is None
    assert bad.call_count == 1  # a failing lookup doesn't get hammered


async def test_available_models_is_none_without_a_key():
    assert await GeminiProvider(api_key="").available_models() is None


@respx.mock
async def test_the_chain_is_narrowed_to_models_the_key_actually_has(provider):
    respx.get(f"{BASE}/models").mock(return_value=_listing("gemini-2.5-flash", "gemini-2.5-flash-lite"))
    invented = [respx.post(GEN(m)).mock(return_value=httpx.Response(404)) for m in ("gemini-3.8-flash", "gemini-3.7-flash")]
    good = respx.post(GEN("gemini-2.5-flash")).mock(return_value=httpx.Response(200, json=OK))
    text, used = await lcl.complete_with_logging(
        "gemini", "gemini-3.8-flash", "hi", fallback_models=["gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    )
    assert used == "gemini-2.5-flash" and good.call_count == 1
    assert all(r.call_count == 0 for r in invented)  # never even asked


@respx.mock
async def test_discovery_failure_fails_open_and_uses_the_configured_chain(provider):
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(503))
    good = respx.post(GEN("gemini-2.5-flash")).mock(return_value=httpx.Response(200, json=OK))
    _text, used = await lcl.complete_with_logging("gemini", "gemini-2.5-flash", "hi")
    assert used == "gemini-2.5-flash" and good.call_count == 1


@respx.mock
async def test_if_discovery_would_remove_every_candidate_the_configured_chain_still_runs(provider):
    # e.g. ListModels doesn't list an alias that generateContent nonetheless accepts.
    respx.get(f"{BASE}/models").mock(return_value=_listing("something-else"))
    good = respx.post(GEN("gemini-flash-latest")).mock(return_value=httpx.Response(200, json=OK))
    _text, used = await lcl.complete_with_logging("gemini", "gemini-flash-latest", "hi")
    assert used == "gemini-flash-latest" and good.call_count == 1


@respx.mock
async def test_when_everything_is_marked_unavailable_it_still_tries_rather_than_giving_up(provider):
    gemini_quota.mark_unavailable("gemini-2.5-flash")
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(500))
    good = respx.post(GEN("gemini-2.5-flash")).mock(return_value=httpx.Response(200, json=OK))
    _text, used = await lcl.complete_with_logging("gemini", "gemini-2.5-flash", "hi")
    assert used == "gemini-2.5-flash" and good.call_count == 1  # a 404 marker must not brick a model that came back


async def test_non_gemini_providers_are_untouched_by_discovery(monkeypatch):
    class Fake:
        async def complete(self, prompt, *, model, **kw):
            return "claude says hi"

    monkeypatch.setattr(lcl, "get_provider", lambda _n: Fake())
    assert await lcl.complete_with_logging("claude", "claude-x", "hi") == ("claude says hi", "claude-x")


# ------------------------------------------------------------- admin API --


def test_admin_diagnostics_endpoint_compares_configured_with_offered_models(monkeypatch):
    from fastapi.testclient import TestClient

    from app import auth, rate_limit
    from app.main import app
    from app.providers.factory import get_provider
    from app.routers import admin

    prov = get_provider("gemini")
    monkeypatch.setattr(prov, "api_key", "k")
    monkeypatch.setattr(prov, "_models_cache", None)
    monkeypatch.setattr(admin.db, "list_agents", lambda: [
        {"provider": "gemini", "model": "gemini-flash-latest", "fallback_models": ["gemini-3.8-flash", "gemini-2.5-flash"]},
        {"provider": "claude", "model": "claude-x", "fallback_models": []},
    ])
    rate_limit._admin_limiter._hits.clear()
    gemini_quota.mark_unavailable("gemini-3.8-flash")
    client = TestClient(app)
    admin_h = {"Authorization": "Bearer " + auth.create_access_token(auth.TokenPayload(sub="admin", role="admin"))}
    viewer_h = {"Authorization": "Bearer " + auth.create_access_token(auth.TokenPayload(sub="v", role="viewer"))}
    assert client.get("/api/admin/providers/gemini/models").status_code == 401
    assert client.get("/api/admin/providers/gemini/models", headers=viewer_h).status_code == 403
    with respx.mock:
        respx.get(f"{BASE}/models").mock(return_value=_listing("gemini-flash-latest", "gemini-2.5-flash"))
        body = client.get("/api/admin/providers/gemini/models", headers=admin_h).json()
    assert body["key_configured"] is True
    assert body["configured_models"] == ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]  # claude agent excluded
    assert body["configured_but_not_offered"] == ["gemini-3.8-flash"]
    assert "gemini-3.8-flash" in body["recently_404_retry_in_s"]
    assert body["free_tier_ceilings"]["gemini-2.5-flash-lite"]["rpd"] == 20


# ----------------------------------------------- 400s: readable, and thinking-config retry --


@respx.mock
async def test_a_400_now_says_why_with_the_key_scrubbed():
    respx.post(GEN("gemini-x")).mock(return_value=httpx.Response(400, json={"error": {"message": "Invalid value at 'contents' for key-abc-123\n  (type)"}}))
    with pytest.raises(RuntimeError) as e:
        await GeminiProvider(api_key="key-abc-123").complete("hi", model="gemini-x", retry=False)
    text = str(e.value)
    assert text.startswith("Gemini API error: HTTP 400 (") and "Invalid value at 'contents'" in text
    assert "key-abc-123" not in text and "\n" not in text


@respx.mock
async def test_a_400_with_an_unreadable_body_is_still_a_clean_status_only_error():
    respx.post(GEN("gemini-x")).mock(return_value=httpx.Response(400, text="<html>not json</html>"))
    with pytest.raises(RuntimeError) as e:
        await GeminiProvider(api_key="k").complete("hi", model="gemini-x", retry=False)
    assert str(e.value) == "Gemini API error: HTTP 400"


@respx.mock
async def test_a_model_that_rejects_thinking_disabled_is_retried_without_it_even_with_no_retries_allowed():
    from app.providers import gemini as g

    g._NO_THINKING.discard("gemini-lite-x")
    route = respx.post(GEN("gemini-lite-x")).mock(
        side_effect=[httpx.Response(400, json={"error": {"message": "Budget 0 is invalid. This model only works in thinking mode."}}), httpx.Response(200, json=OK)]
    )
    out = await GeminiProvider(api_key="k").complete("hi", model="gemini-lite-x", retry=False)  # retry=False: no ordinary retries
    assert out == "hello" and route.call_count == 2
    assert "thinkingConfig" in json.loads(route.calls[0].request.content)["generationConfig"]
    assert "thinkingConfig" not in json.loads(route.calls[1].request.content)["generationConfig"]


@respx.mock
async def test_the_model_is_remembered_so_the_next_call_omits_thinking_up_front():
    from app.providers import gemini as g

    g._NO_THINKING.add("gemini-lite-y")
    route = respx.post(GEN("gemini-lite-y")).mock(return_value=httpx.Response(200, json=OK))
    await GeminiProvider(api_key="k").complete("hi", model="gemini-lite-y")
    assert route.call_count == 1 and "thinkingConfig" not in json.loads(route.calls[0].request.content)["generationConfig"]
    g._NO_THINKING.discard("gemini-lite-y")


@respx.mock
async def test_the_thinking_retry_happens_once_and_a_second_400_surfaces():
    from app.providers import gemini as g

    g._NO_THINKING.discard("gemini-lite-z")
    route = respx.post(GEN("gemini-lite-z")).mock(return_value=httpx.Response(400, json={"error": {"message": "thinking is not supported, and something else"}}))
    with pytest.raises(RuntimeError, match="HTTP 400"):
        await GeminiProvider(api_key="k").complete("hi", model="gemini-lite-z", retry=False)
    assert route.call_count == 2  # original + one retry without thinkingConfig, not a loop
    g._NO_THINKING.discard("gemini-lite-z")
