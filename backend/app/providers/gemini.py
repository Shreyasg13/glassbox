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
from typing import Optional

import httpx

from .base import BaseProvider, NotConfiguredError, OnToken

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
_RETRYABLE_STATUS = {429, 503}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = {429: 12.0, 503: 2.0}


class GeminiProvider(BaseProvider):
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

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
        url = f"{self.BASE_URL}/models/{model}:generateContent"
        last_exc: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=None) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    resp = await client.post(url, params={"key": self.api_key}, json=payload)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                        retry_after = exc.response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after else _BACKOFF_BASE_S[status] * attempt
                        await asyncio.sleep(delay)
                        last_exc = RuntimeError(f"Gemini API error: HTTP {status}")
                        continue
                    raise RuntimeError(f"Gemini API error: HTTP {status}") from None
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
