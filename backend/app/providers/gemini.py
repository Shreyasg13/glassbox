"""Gemini provider -- raw REST client against the Generative Language API.

Deliberately uses `httpx` directly instead of the `google-generativeai`
SDK to keep the dependency footprint small; the REST surface
(`models/{model}:generateContent`) is small and stable enough that a thin
client is simpler to reason about (and test with a mocked transport) than
pulling in the full SDK.

SECURITY NOTE (Phase 6 secrets-hygiene audit): the API key is sent as a
`?key=...` query param, which Gemini's REST API requires. `httpx`'s
`HTTPStatusError.__str__` includes the full request URL -- query string
and all -- so letting that exception propagate unmodified would leak the
key into `llm_calls.error`, the admin job WS log, and
`/admin/providers/health`'s `detail` field, all of which are surfaced to
the admin UI (and, for job logs, persisted in SQLite). Both methods below
catch `httpx.HTTPError` and re-raise a message built from only the status
code, never the exception's own string form.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional, Set

import httpx

from .base import BaseProvider, ModelUnavailableError, NotConfiguredError, OnToken, RateLimitedError

# 429 (rate limit) and 503 (transient overload) are the only Gemini errors
# worth retrying here -- both observed live: a fresh free-tier key firing
# several parallel calls trips 429s, and 503 "high demand" is Google-side
# and self-resolves within seconds. Anything else (400/404/auth) retrying
# would never fix. Observed live: quota fully recovers within a few
# minutes of a burst, and a fresh isolated call succeeds cleanly -- so a
# 429 needs a real wait (the RPM ceiling on a free-tier key is much
# lower than initially assumed: staggering launches 0.4s apart still
# left 6 of 7 calls 429'd), while a 503 "high demand" typically clears
# in a couple seconds and doesn't need as long a wait.
_MODELS_TTL_S = 6 * 60 * 60.0  # how long a successful ListModels result is trusted
_MODELS_FAIL_TTL_S = 5 * 60.0  # how long a FAILED lookup suppresses re-asking
# Models observed to reject "thinking disabled" (thinkingBudget: 0) with HTTP 400 --
# remembered so later calls omit it up front instead of failing first.
_NO_THINKING: Set[str] = set()


def _error_message(resp: httpx.Response, api_key: Optional[str]) -> str:
    """The short human message from Google's JSON error body (e.g. "Budget 0 is
    invalid ..."), whitespace-collapsed and truncated. Google's 400 messages
    describe the REQUEST SHAPE, not credentials, and the key is scrubbed anyway;
    used for 400s only so a rejected model says WHY instead of a bare status."""
    try:
        msg = str(resp.json()["error"]["message"])
    except Exception:  # noqa: BLE001 -- any non-JSON / unexpected body
        return ""
    if api_key and len(api_key) >= 8:  # real keys are ~39 chars; never mangle text over a trivially short value
        msg = msg.replace(api_key, "***")
    return " ".join(msg.split())[:140]


_RETRYABLE_STATUS = {429, 503}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = {429: 12.0, 503: 2.0}


class GeminiProvider(BaseProvider):
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: Optional[str] = None, **kwargs) -> None:
        # 30, not the base default of 12: this provider's callers (see
        # llm_call_logging.py's fallback loop) can try up to ~10 candidate
        # models in one logical agent turn when an agent has fallback_models
        # configured -- a fully-exhausted chain on a bad day is ~10
        # consecutive failures against this ONE shared singleton, which
        # would trip a threshold of 12 within roughly one turn instead of
        # after genuinely sustained trouble across many turns.
        kwargs.setdefault("failure_threshold", 30)
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._models_cache: Optional[tuple] = None  # (fetched_at_monotonic, set-or-None)

    async def available_models(self) -> Optional[Set[str]]:
        """Model ids this key can actually call generateContent on (from the
        API's own ListModels), cached. None = unknown (no key, or the lookup
        failed) -- callers must treat None as "don't filter", never as "none
        available". Errors are swallowed WITHOUT logging their text: httpx
        error strings contain the request URL, which contains the API key."""
        if not self.api_key:
            return None
        now = time.monotonic()
        if self._models_cache is not None:
            fetched, value = self._models_cache
            if now - fetched < (_MODELS_TTL_S if value is not None else _MODELS_FAIL_TTL_S):
                return value
        names: Set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                token: Optional[str] = None
                for _page in range(5):
                    params = {"key": self.api_key, "pageSize": 1000}
                    if token:
                        params["pageToken"] = token
                    resp = await client.get(f"{self.BASE_URL}/models", params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    for m in data.get("models", []):
                        if "generateContent" in m.get("supportedGenerationMethods", []):
                            names.add(str(m["name"]).removeprefix("models/"))
                    token = data.get("nextPageToken")
                    if not token:
                        break
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            self._models_cache = (now, None)
            return None
        value = names or None
        self._models_cache = (now, value)
        return value

    async def _do_complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        system: Optional[str],
        on_token: Optional[OnToken],
        retry: bool = True,
    ) -> str:
        if not self.api_key:
            raise NotConfiguredError("GEMINI_API_KEY not set")
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"[system]\n{system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": max_tokens,
                # Gemini 2.5+/3.x models spend part of maxOutputTokens on
                # invisible "thinking" tokens before the visible answer --
                # observed live consuming 517 of a 600-token budget, leaving
                # too little room for the actual answer and truncating it
                # mid-sentence. These agent prompts want a direct analytical
                # answer, not a reasoning chain, so thinking is disabled.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if model in _NO_THINKING:
            payload["generationConfig"].pop("thinkingConfig", None)
        url = f"{self.BASE_URL}/models/{model}:generateContent"
        # When a caller has other fallback models ready to try immediately
        # (llm_call_logging.py's chain loop passes retry=False for every
        # non-final candidate), backing off and retrying THIS already-
        # rate-limited model is strictly worse than moving on: it burns up
        # to ~36s waiting on a model we're about to abandon anyway, and
        # risks the whole chain blowing past the orchestration's
        # agent_timeout_s before ever reaching a model that might work.
        # retry=True (the default, used for a single model with nothing to
        # fall back to) keeps the original backoff-and-retry behavior.
        max_attempts = _MAX_ATTEMPTS if retry else 1
        last_exc: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=None) as client:
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    resp = await client.post(url, params={"key": self.api_key}, json=payload)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status == 404:
                        raise ModelUnavailableError("Gemini API error: HTTP 404") from None
                    if status == 400 and "thinkingConfig" in payload["generationConfig"] and "thinking" in _error_message(exc.response, self.api_key).lower():
                        # e.g. the lite tier rejects "thinking disabled". Drop it, remember the
                        # model, and retry right away without spending a retry attempt.
                        _NO_THINKING.add(model)
                        payload["generationConfig"].pop("thinkingConfig", None)
                        attempt -= 1
                        continue
                    if status in _RETRYABLE_STATUS and attempt < max_attempts:
                        retry_after = exc.response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after else _BACKOFF_BASE_S[status] * attempt
                        await asyncio.sleep(delay)
                        last_exc = RuntimeError(f"Gemini API error: HTTP {status}")
                        continue
                    if status == 429:
                        # A per-DAY quota ("...PerDay...") won't clear in a minute --
                        # tell the failover router so it stops asking for a while.
                        body = exc.response.text or ""
                        retry_hdr = exc.response.headers.get("retry-after")
                        raise RateLimitedError(
                            "Gemini API error: HTTP 429",
                            retry_after_s=float(retry_hdr) if retry_hdr and retry_hdr.replace(".", "", 1).isdigit() else None,
                            daily="PerDay" in body or "per day" in body.lower(),
                        ) from None
                    why = _error_message(exc.response, self.api_key) if status == 400 else ""
                    raise RuntimeError(f"Gemini API error: HTTP {status}" + (f" ({why})" if why else "")) from None
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Gemini API request failed: {exc.__class__.__name__}") from None
                else:
                    data = resp.json()
                    # Concatenate every text part rather than assuming the
                    # answer is entirely in parts[0] -- defensive against
                    # any response shape where content is split across parts.
                    parts = data["candidates"][0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts)
                    if on_token:
                        # The non-streaming generateContent endpoint returns
                        # the full text in one shot; deliver it as a single
                        # chunk so callers relying on on_token still see output.
                        await on_token(text)
                    return text
            # Unreachable in practice (loop always returns or raises), but
            # keeps type-checkers honest about every path having an exit.
            raise last_exc or RuntimeError("Gemini API request failed")

    async def _do_health_check(self) -> str:
        if not self.api_key:
            raise NotConfiguredError("GEMINI_API_KEY not set")
        url = f"{self.BASE_URL}/models"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url, params={"key": self.api_key})
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"Gemini API error: HTTP {exc.response.status_code}") from None
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Gemini API request failed: {exc.__class__.__name__}") from None
            data = resp.json()
            n = len(data.get("models", []))
            return f"{n} model(s) available"
