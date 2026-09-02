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

import os
from typing import Optional

import httpx

from .base import BaseProvider, NotConfiguredError, OnToken


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
            },
        }
        url = f"{self.BASE_URL}/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                resp = await client.post(url, params={"key": self.api_key}, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"Gemini API error: HTTP {exc.response.status_code}") from None
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Gemini API request failed: {exc.__class__.__name__}") from None
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            if on_token:
                # The non-streaming generateContent endpoint returns the
                # full text in one shot; deliver it as a single chunk so
                # callers relying on on_token still see output.
                await on_token(text)
            return text

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
