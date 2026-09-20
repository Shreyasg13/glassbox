"""OpenAI-compatible providers + cross-provider failover routing.

The point of this layer: when Gemini's free tier is spent, LLM work moves to the
next available provider instead of stalling. These tests pin the behaviours that
make that safe -- who gets skipped, how long a failed provider rests, which model
ids each provider is sent, that no key ever appears in an error, and that with
nowhere to fail over to the original error is raised unchanged."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from app import llm_call_logging as lcl
from app import llm_router
from app.providers import gemini_quota
from app.providers.base import ModelUnavailableError, NotConfiguredError, RateLimitedError
from app.providers.factory import get_provider
from app.providers.gemini import GeminiProvider
from app.providers.openai_compat import SPECS, OpenAICompatProvider

OR = SPECS["openrouter"].base_url
GROQ = SPECS["groq"].base_url
GEM = GeminiProvider.BASE_URL
KEY_ENVS = ["OPENROUTER_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "GITHUB_MODELS_TOKEN", "GITHUB_TOKEN", "DASHSCOPE_API_KEY", "QWEN_API_KEY",
            "DEEPSEEK_API_KEY", "XAI_API_KEY", "LLM_GATEWAY_API_KEY", "LLM_GATEWAY_BASE_URL", "LLM_FAILOVER", "LLM_FAILOVER_ENABLED",
            "LLM_ROUTE_BUDGET_S", "OLLAMA_BASE_URL"]


def chat(text="hello", **over):
    body = {"choices": [{"message": {"role": "assistant", "content": text}}]}
    body.update(over)
    return httpx.Response(200, json=body)


def gemini_ok(text="gemini says hi"):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in KEY_ENVS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(lcl.db, "create_llm_call", lambda *a, **k: None)
    monkeypatch.setattr(lcl.db, "update_llm_call", lambda *a, **k: None)
    monkeypatch.setattr("app.providers.gemini._BACKOFF_BASE_S", {429: 0.0, 503: 0.0})
    monkeypatch.setattr("app.providers.openai_compat.asyncio.sleep", _no_sleep)
    get_provider.cache_clear()
    llm_router.reset_state()
    gemini_quota.reset_unavailable()
    gemini_quota._call_log.clear()
    yield
    get_provider.cache_clear()
    llm_router.reset_state()
    gemini_quota.reset_unavailable()


async def _no_sleep(_s):
    return None


def with_key(monkeypatch, provider, key="test-key-abc"):
    monkeypatch.setenv(SPECS[provider].key_env[0], key)


def gemini_with_key():
    get_provider("gemini").api_key = "gem-key"


# =============================================================== provider ==


@respx.mock
async def test_completion_sends_an_openai_chat_request_and_returns_the_text(monkeypatch):
    with_key(monkeypatch, "groq")
    route = respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("the answer"))
    out = await get_provider("groq").complete("hi there", model="llama-x", system="be brief", temperature=0.2, max_tokens=50)
    assert out == "the answer"
    req = route.calls[0].request
    body = json.loads(req.content)
    assert req.headers["authorization"] == "Bearer test-key-abc"
    assert body["model"] == "llama-x" and body["max_tokens"] == 50 and body["temperature"] == 0.2 and body["stream"] is False
    assert body["messages"] == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi there"}]


@respx.mock
async def test_reasoning_blocks_are_stripped_and_content_parts_are_joined(monkeypatch):
    with_key(monkeypatch, "groq")
    respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("<think>secret chain of thought</think>Final answer."))
    assert await get_provider("groq").complete("q", model="m") == "Final answer."
    respx.reset()
    respx.post(f"{GROQ}/chat/completions").mock(return_value=chat([{"type": "text", "text": "part one "}, {"type": "text", "text": "part two"}]))
    assert await get_provider("groq").complete("q", model="m") == "part one part two"


@respx.mock
@pytest.mark.parametrize("content", ["", None, "<think>only thinking, never answered</think>", "   "])
async def test_an_empty_answer_is_a_failure_so_the_router_can_fail_over(monkeypatch, content):
    with_key(monkeypatch, "groq")
    respx.post(f"{GROQ}/chat/completions").mock(return_value=chat(content))
    with pytest.raises(RuntimeError, match="empty response"):
        await get_provider("groq").complete("q", model="m")


@respx.mock
async def test_tokens_are_delivered_to_on_token(monkeypatch):
    with_key(monkeypatch, "groq")
    respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("streamed text"))
    got = []

    async def on_token(p):
        got.append(p)

    await get_provider("groq").complete("q", model="m", on_token=on_token)
    assert got == ["streamed text"]


@respx.mock
@pytest.mark.parametrize(
    "status,exc,extra",
    [(401, NotConfiguredError, {}), (402, RateLimitedError, {"daily": True}), (404, ModelUnavailableError, {}), (429, RateLimitedError, {})],
)
async def test_http_errors_map_to_specific_exceptions_and_never_leak_the_key(monkeypatch, status, exc, extra):
    with_key(monkeypatch, "groq", "SUPER-SECRET-KEY-123")
    respx.post(f"{GROQ}/chat/completions").mock(
        return_value=httpx.Response(status, json={"error": {"message": "echoing SUPER-SECRET-KEY-123 and prompt text"}})
    )
    with pytest.raises(exc) as e:
        await get_provider("groq").complete("my private prompt", model="m", retry=False)
    assert "SUPER-SECRET-KEY-123" not in str(e.value) and "my private prompt" not in str(e.value)
    assert f"{status}" in str(e.value) or status == 401 or status == 402
    for k, v in extra.items():
        assert getattr(e.value, k) == v


@respx.mock
async def test_500s_are_generic_errors_with_only_the_status(monkeypatch):
    with_key(monkeypatch, "groq", "KEYKEY")
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(502, text="upstream said KEYKEY"))
    with pytest.raises(RuntimeError) as e:
        await get_provider("groq").complete("q", model="m", retry=False)
    assert str(e.value) == "groq API error: HTTP 502"


@respx.mock
async def test_429_reads_retry_after_and_detects_a_daily_limit(monkeypatch):
    with_key(monkeypatch, "groq")
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429, headers={"retry-after": "37"}, text="rate limit"))
    with pytest.raises(RateLimitedError) as e:
        await get_provider("groq").complete("q", model="m", retry=False)
    assert e.value.retry_after_s == 37.0 and e.value.daily is False
    respx.reset()
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429, text="You exceeded your daily quota (requests per day)"))
    with pytest.raises(RateLimitedError) as e2:
        await get_provider("groq").complete("q", model="m", retry=False)
    assert e2.value.daily is True


@respx.mock
async def test_429_is_retried_when_allowed_and_not_when_a_fallback_is_waiting(monkeypatch):
    with_key(monkeypatch, "groq")
    route = respx.post(f"{GROQ}/chat/completions").mock(side_effect=[httpx.Response(429), httpx.Response(429), chat("third time lucky")])
    assert await get_provider("groq").complete("q", model="m", retry=True) == "third time lucky"
    assert route.call_count == 3
    respx.reset()
    route = respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitedError):
        await get_provider("groq").complete("q", model="m", retry=False)
    assert route.call_count == 1


@respx.mock
async def test_a_429_reported_inside_a_200_body_is_still_a_rate_limit(monkeypatch):
    with_key(monkeypatch, "openrouter")
    respx.post(f"{OR}/chat/completions").mock(return_value=httpx.Response(200, json={"error": {"code": 429, "message": "slow down"}}))
    with pytest.raises(RateLimitedError):
        await get_provider("openrouter").complete("q", model="m")
    respx.reset()
    respx.post(f"{OR}/chat/completions").mock(return_value=httpx.Response(200, json={"error": {"code": 500, "message": "boom"}}))
    with pytest.raises(RuntimeError, match="openrouter API error: 500"):
        await get_provider("openrouter").complete("q", model="m")


@respx.mock
async def test_a_404_is_remembered_and_that_model_stops_being_offered(monkeypatch):
    with_key(monkeypatch, "groq")
    monkeypatch.setenv("GROQ_MODELS", "dead-model,live-model")
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(500))  # discovery unavailable: fail open
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(404))
    p = get_provider("groq")
    assert await p.candidate_models() == ["dead-model", "live-model"]
    with pytest.raises(ModelUnavailableError):
        await p.complete("q", model="dead-model", retry=False)
    assert await p.candidate_models() == ["live-model"]


def test_configuration_flags_and_missing_key_messages(monkeypatch):
    p = get_provider("groq")
    assert p.is_configured is False and p._missing_what() == "GROQ_API_KEY not set"
    with_key(monkeypatch, "groq")
    assert p.is_configured is True
    gw = get_provider("gateway")
    assert gw.is_configured is False and gw._missing_what() == "LLM_GATEWAY_BASE_URL not set"
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "http://omniroute:20128/v1/")
    assert gw.is_configured is True and gw.base_url == "http://omniroute:20128/v1"  # no key needed, trailing slash trimmed


@respx.mock
async def test_calling_an_unconfigured_provider_raises_not_configured_without_a_request():
    route = respx.post(f"{GROQ}/chat/completions").mock(return_value=chat())
    with pytest.raises(NotConfiguredError, match="GROQ_API_KEY not set"):
        await get_provider("groq").complete("q", model="m")
    assert route.call_count == 0


@respx.mock
async def test_a_keyless_gateway_sends_no_authorization_header(monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "http://gw.local/v1")
    route = respx.post("http://gw.local/v1/chat/completions").mock(return_value=chat("from the gateway"))
    assert await get_provider("gateway").complete("q", model="auto") == "from the gateway"
    assert "authorization" not in route.calls[0].request.headers


@respx.mock
async def test_openrouter_identifies_the_app_with_recommended_headers(monkeypatch):
    with_key(monkeypatch, "openrouter")
    monkeypatch.setenv("APP_DOMAIN", "glassbox.example.com")
    route = respx.post(f"{OR}/chat/completions").mock(return_value=chat())
    await get_provider("openrouter").complete("q", model="openrouter/free")
    h = route.calls[0].request.headers
    assert h["x-title"] == "GlassBox" and h["http-referer"] == "https://glassbox.example.com"


# ------------------------------------------------------------------ discovery


CATALOGUE = {"data": [
    {"id": "qwen/qwen3.8-27b:free", "context_length": 262144, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->text"}},
    {"id": "google/gemma-4-31b-it:free", "context_length": 262144, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->text"}},
    {"id": "nvidia/nemotron-3.5-content-safety:free", "context_length": 128000, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->text"}},
    {"id": "google/lyria-3-clip-preview", "context_length": 1048576, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->audio"}},
    {"id": "acme/vision-thing:free", "context_length": 9000, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text+image->text"}},
    {"id": "openai/gpt-paid", "context_length": 128000, "pricing": {"prompt": "0.000005", "completion": "0.00002"}, "architecture": {"modality": "text->text"}},
    {"id": "openrouter/free", "context_length": 200000, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->text"}},
    {"id": "zeta/plain-free:free", "context_length": 32000, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->text"}},
]}


@respx.mock
async def test_openrouter_free_models_are_discovered_filtered_and_ranked():
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(200, json=CATALOGUE))
    p = get_provider("openrouter")  # works with NO key: the catalogue is public
    free = await p.free_models()
    assert "openai/gpt-paid" not in free and "openrouter/free" not in free  # paid excluded; the meta-model is added separately
    assert "google/lyria-3-clip-preview" not in free and "nvidia/nemotron-3.5-content-safety:free" not in free and "acme/vision-thing:free" not in free
    assert set(free[:2]) == {"qwen/qwen3.8-27b:free", "google/gemma-4-31b-it:free"}  # known families first (same context: name order)
    assert free[-1] == "zeta/plain-free:free"  # unknown family last
    assert len(free) == 3


@respx.mock
async def test_openrouter_candidates_start_with_the_auto_router_then_discovered_free_models(monkeypatch):
    with_key(monkeypatch, "openrouter")
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(200, json=CATALOGUE))
    c = await get_provider("openrouter").candidate_models()
    assert c[0] == "openrouter/free" and "qwen/qwen3.8-27b:free" in c and len(c) <= 6


@respx.mock
async def test_candidates_are_narrowed_to_what_the_key_offers_but_fail_open(monkeypatch):
    with_key(monkeypatch, "groq")
    monkeypatch.setenv("GROQ_MODELS", "a,b,c")
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "b"}, {"id": "zzz"}]}))
    assert await get_provider("groq").candidate_models() == ["b"]
    get_provider.cache_clear()
    respx.reset()
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "only-unrelated"}]}))
    assert await get_provider("groq").candidate_models() == ["a", "b", "c"]  # nothing matched -> trust the configured list
    get_provider.cache_clear()
    respx.reset()
    respx.get(f"{GROQ}/models").mock(side_effect=httpx.ConnectError("down"))
    assert await get_provider("groq").candidate_models() == ["a", "b", "c"]  # discovery down -> trust the configured list


@respx.mock
async def test_a_gateway_with_no_configured_models_uses_what_it_offers(monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "http://gw.local/v1")
    respx.get("http://gw.local/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "z-model"}, {"id": "a-model"}]}))
    assert await get_provider("gateway").candidate_models() == ["a-model", "z-model"]


@respx.mock
async def test_health_check_reports_free_model_count_and_missing_keys(monkeypatch):
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(200, json=CATALOGUE))
    h = await get_provider("openrouter").health_check()
    assert h.reachable is False and "OPENROUTER_API_KEY not set" in h.detail  # can't complete without a key, so not "healthy"
    with_key(monkeypatch, "openrouter")
    h = await get_provider("openrouter").health_check()
    assert h.reachable is True and "free model(s)" in h.detail


# =================================================================== router ==


def cooling(name):
    return llm_router.cooldown_remaining(name)[0]


@respx.mock
async def test_the_requested_provider_answers_and_nothing_else_is_touched(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    g = respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=gemini_ok())
    o = respx.post(f"{OR}/chat/completions").mock(return_value=chat("openrouter"))
    r = await llm_router.complete_routed("gemini", "gemini-x", "hi")
    assert (r.provider, r.model, r.text, r.tried) == ("gemini", "gemini-x", "gemini says hi", [])
    assert g.call_count == 1 and o.call_count == 0


@respx.mock
async def test_a_spent_gemini_quota_fails_over_to_openrouter_with_its_own_model_ids(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    g = respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429, text="quota exceeded PerDay"))
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(200, json=CATALOGUE))
    o = respx.post(f"{OR}/chat/completions").mock(return_value=chat("answered by the free router"))
    r = await llm_router.complete_routed("gemini", "gemini-x", "hi", system="s")
    assert (r.provider, r.text) == ("openrouter", "answered by the free router")
    assert r.model == "openrouter/free"  # never the Gemini model id
    assert json.loads(o.calls[0].request.content)["model"] == "openrouter/free"
    assert any(t["provider"] == "gemini" for t in r.tried) and g.call_count >= 1


@respx.mock
async def test_after_a_daily_quota_error_gemini_is_skipped_entirely_until_it_recovers(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(500))
    g = respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429, text="exceeded PerDay quota"))
    respx.post(f"{OR}/chat/completions").mock(return_value=chat("ok"))
    await llm_router.complete_routed("gemini", "gemini-x", "one")
    assert cooling("gemini") >= 3500  # a per-day limit rests for about an hour, not a minute
    calls_after_first = g.call_count
    for _ in range(4):  # a whole committee of agents
        r = await llm_router.complete_routed("gemini", "gemini-x", "again")
        assert r.provider == "openrouter"
    assert g.call_count == calls_after_first  # exhausted provider was not hit again


@respx.mock
async def test_success_clears_a_providers_cooldown(monkeypatch):
    gemini_with_key()
    llm_router.note_failure("gemini", RuntimeError("blip"))
    assert cooling("gemini") > 0
    llm_router.note_success("gemini")
    assert cooling("gemini") == 0 and llm_router._streak.get("gemini") is None


@respx.mock
async def test_unconfigured_providers_are_skipped_and_the_original_error_is_raised_when_nothing_else_exists():
    gemini_with_key()
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429, text="slow"))
    with pytest.raises(RateLimitedError) as e:  # the ORIGINAL type, exactly as before failover existed
        await llm_router.complete_routed("gemini", "gemini-x", "hi")
    assert "HTTP 429" in str(e.value) and not isinstance(e.value, llm_router.AllProvidersFailedError)


@respx.mock
async def test_when_every_configured_provider_fails_the_error_says_who_and_why(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    with_key(monkeypatch, "groq")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(500))
    respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429))
    respx.post(f"{OR}/chat/completions").mock(return_value=httpx.Response(503))
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429, text="per day"))
    with pytest.raises(llm_router.AllProvidersFailedError) as e:
        await llm_router.complete_routed("gemini", "gemini-x", "hi")
    msg = str(e.value)
    assert "gemini:" in msg and "openrouter: openrouter API error: HTTP 503" in msg and "groq:" in msg
    real = [t["provider"] for t in e.value.tried if not t["result"].startswith("skipped")]
    assert real == ["gemini", "openrouter", "groq"]  # tried in failover order, primary first
    assert cooling("gemini") and cooling("openrouter") and cooling("groq")


@respx.mock
async def test_a_cooling_primary_is_still_tried_as_a_last_resort(monkeypatch):
    gemini_with_key()
    llm_router.note_failure("gemini", RateLimitedError("HTTP 429", daily=True))
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    g = respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=gemini_ok("quota came back"))
    r = await llm_router.complete_routed("gemini", "gemini-x", "hi")  # no other provider configured
    assert r.text == "quota came back" and g.call_count == 1


@respx.mock
async def test_failover_can_be_switched_off_globally_and_per_call(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429))
    o = respx.post(f"{OR}/chat/completions").mock(return_value=chat("should not be reached"))
    with pytest.raises(RateLimitedError):
        await llm_router.complete_routed("gemini", "gemini-x", "hi", allow_failover=False)
    llm_router.reset_state()
    monkeypatch.setenv("LLM_FAILOVER_ENABLED", "0")
    with pytest.raises(RateLimitedError):
        await llm_router.complete_routed("gemini", "gemini-x", "hi")
    assert o.call_count == 0


@respx.mock
async def test_on_fallback_announces_the_provider_switch(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "groq")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(500))
    respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429))
    respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("ok"))
    seen = []

    async def on_fb(candidate, reason):
        seen.append((candidate, reason))

    await llm_router.complete_routed("gemini", "gemini-x", "hi", on_fallback=on_fb)
    assert any(c == "groq" and "provider 'gemini' failed" in r and "trying 'groq'" in r for c, r in seen)
    assert not any("openrouter" in r and c == "groq" for c, r in seen)  # never blames a provider that was merely skipped


@respx.mock
async def test_the_failover_order_env_is_respected(monkeypatch):
    with_key(monkeypatch, "openrouter")
    with_key(monkeypatch, "groq")
    monkeypatch.setenv("LLM_FAILOVER", "groq,openrouter,bogus,groq")
    assert llm_router.failover_order() == ["groq", "openrouter"]  # unknown ignored, duplicates dropped
    respx.get(f"{GROQ}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(500))
    g = respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("groq first"))
    o = respx.post(f"{OR}/chat/completions").mock(return_value=chat("openrouter"))
    r = await llm_router.complete_routed("gemini", "gemini-x", "hi")  # gemini has no key -> skipped
    assert r.provider == "groq" and g.call_count == 1 and o.call_count == 0


@respx.mock
async def test_the_time_budget_stops_a_long_walk(monkeypatch):
    gemini_with_key()
    with_key(monkeypatch, "groq")
    monkeypatch.setenv("LLM_ROUTE_BUDGET_S", "0")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.post(f"{GEM}/models/gemini-x:generateContent").mock(return_value=httpx.Response(429))
    groq = respx.post(f"{GROQ}/chat/completions").mock(return_value=chat("x"))
    with pytest.raises(RateLimitedError):  # only the primary was really tried
        await llm_router.complete_routed("gemini", "gemini-x", "hi")
    assert groq.call_count == 0


async def test_an_unreachable_local_ollama_is_skipped_not_hung(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")  # nothing listens here
    get_provider.cache_clear()
    ok, why = await llm_router._configured("ollama")
    assert ok is False and why == "server not reachable"


def test_cooldown_lengths_match_what_the_provider_told_us():
    f = llm_router._cooldown_for
    assert f(RateLimitedError("x", daily=True), 1) == 3600
    assert f(RateLimitedError("x"), 1) == 90
    assert f(RateLimitedError("x", retry_after_s=7), 1) == 8
    assert f(RateLimitedError("x", retry_after_s=99999), 1) == 3600  # capped
    assert f(NotConfiguredError("key rejected"), 1) == 6 * 3600
    assert f(ModelUnavailableError("404"), 1) == 0  # model-level, not a provider outage
    assert [f(RuntimeError("boom"), n) for n in (1, 2, 3, 4, 9)] == [30, 60, 120, 240, 600]


@respx.mock
async def test_status_lists_every_provider_with_configuration_and_cooldown(monkeypatch):
    with_key(monkeypatch, "groq")
    llm_router.note_failure("groq", RateLimitedError("HTTP 429", daily=True))
    st = await llm_router.status()
    rows = {r["provider"]: r for r in st["providers"]}
    assert {"gemini", "openrouter", "groq", "cerebras", "github", "qwen", "deepseek", "xai", "gateway", "ollama"} <= set(rows)
    assert rows["groq"]["configured"] is True and rows["groq"]["cooling_down_s"] >= 3500 and "HTTP 429" in rows["groq"]["cooldown_reason"]
    assert rows["cerebras"]["configured"] is False and rows["cerebras"]["not_configured_reason"] == "CEREBRAS_API_KEY not set"
    assert rows["openrouter"]["get_a_key"].startswith("https://openrouter.ai") and rows["openrouter"]["tier"] == "free"
    assert st["enabled"] is True and st["order"][0] == "gemini"


# ============================================================= integration ==


async def test_agents_report_the_provider_that_actually_answered(monkeypatch):
    from app import orchestration
    from app.models import AgentConfig

    async def fake_routed(provider, model, prompt, **kw):
        return llm_router.RoutedResult(text="analysis", provider="groq", model="llama-3.3-70b-versatile")

    monkeypatch.setattr(llm_router, "complete_routed", fake_routed)
    agent = AgentConfig(id="a1", name="Risk Manager", role="r", type="llm", provider="gemini", model="gemini-x", system_prompt="s")
    out = await orchestration.run_llm_agent(agent, "AAPL?", None)
    assert out["provider"] == "groq" and out["model"] == "llama-3.3-70b-versatile" and out["failed_over_from"] == "gemini"
    same = AgentConfig(id="a2", name="Q", role="r", type="llm", provider="groq", model="m", system_prompt="s")
    assert "failed_over_from" not in await orchestration.run_llm_agent(same, "x", None)


async def test_the_allow_failover_flag_reaches_the_router(monkeypatch):
    from app import orchestration
    from app.models import AgentConfig

    seen = {}

    async def fake_routed(provider, model, prompt, **kw):
        seen.update(kw)
        return llm_router.RoutedResult(text="t", provider=provider, model=model)

    monkeypatch.setattr(llm_router, "complete_routed", fake_routed)
    agent = AgentConfig(id="a1", name="A", role="r", type="llm", provider="gemini", model="m", system_prompt="s")
    await orchestration.run_agent(agent, "x", allow_failover=False)
    assert seen["allow_failover"] is False


def test_user_started_runs_can_be_kept_off_third_party_providers(monkeypatch):
    assert llm_router.user_runs_may_fail_over() is True
    monkeypatch.setenv("LLM_FAILOVER_USER_RUNS", "0")
    assert llm_router.user_runs_may_fail_over() is False


def test_estimated_cost_of_free_openrouter_models_is_zero_and_others_stay_unknown():
    from app.pricing import estimate_cost

    assert estimate_cost("openrouter", "qwen/qwen3.8-27b:free", 100, 100) == 0.0
    assert estimate_cost("openrouter", "openrouter/free", 100, 100) == 0.0
    assert estimate_cost("openrouter", "openai/gpt-paid", 100, 100) is None
    assert estimate_cost("groq", "llama-3.3-70b-versatile", 100, 100) is None  # plan-dependent: never guess


# ==================================================================== admin ==


def _admin_client():
    from fastapi.testclient import TestClient

    from app import auth, rate_limit
    from app.main import app

    rate_limit._admin_limiter._hits.clear()
    tok = lambda role, sub: {"Authorization": "Bearer " + auth.create_access_token(auth.TokenPayload(sub=sub, role=role))}  # noqa: E731
    return TestClient(app), tok("admin", "admin"), tok("viewer", "v")


def test_routing_endpoints_are_admin_only():
    c, admin, viewer = _admin_client()
    for method, path, kw in [("get", "/api/admin/providers/routing", {}), ("post", "/api/admin/providers/routing/test", {"json": {}})]:
        assert getattr(c, method)(path, **kw).status_code == 401
        assert getattr(c, method)(path, headers=viewer, **kw).status_code == 403


@respx.mock
def test_routing_test_proves_failover_end_to_end(monkeypatch):
    from app.routers import admin as admin_router

    monkeypatch.setattr(admin_router.db, "log_audit", lambda *a, **k: None)
    gemini_with_key()
    with_key(monkeypatch, "openrouter")
    respx.get(f"{GEM}/models").mock(return_value=httpx.Response(500))
    respx.get(f"{OR}/models").mock(return_value=httpx.Response(500))
    respx.post(url__regex=rf"{GEM}/models/.*:generateContent").mock(return_value=httpx.Response(429, text="PerDay"))
    respx.post(f"{OR}/chat/completions").mock(return_value=chat("ready"))
    c, admin, _ = _admin_client()
    r = c.post("/api/admin/providers/routing/test", json={}, headers=admin)
    body = r.json()
    assert r.status_code == 200 and body["ok"] and body["answered_by"] == "openrouter" and body["failed_over"] is True and body["reply"] == "ready"
    st = c.get("/api/admin/providers/routing", headers=admin).json()
    assert next(p for p in st["providers"] if p["provider"] == "gemini")["cooling_down_s"] > 0


@respx.mock
def test_routing_test_reports_503_with_the_attempts_when_nothing_works(monkeypatch):
    from app.routers import admin as admin_router

    monkeypatch.setattr(admin_router.db, "log_audit", lambda *a, **k: None)
    monkeypatch.setattr(llm_router, "_configured", _nothing_configured)
    c, admin, _ = _admin_client()
    r = c.post("/api/admin/providers/routing/test", json={"provider": "gemini"}, headers=admin)
    assert r.status_code == 503 and r.json()["detail"]["tried"]


async def _nothing_configured(name):
    return False, "no key"
