"""Local Ollama provider -- calls a locally running `ollama serve`.

Uses the native `/api/generate` endpoint with `stream: true` so token
chunks can be forwarded to `on_token` as they arrive. If no Ollama server
is running (the common case on a fresh dev machine), `_do_complete` /
`_do_health_check` raise a connection error, which `BaseProvider` turns
into a clean circuit-breaker failure / `ProviderHealth(reachable=False)`
-- there is no special-casing needed for "not running" here.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from .base import BaseProvider, OnToken


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, base_url: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

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
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system or "",
            "stream": True,
            "options": {"temperature": temperature, "top_p": top_p, "num_predict": max_tokens},
        }
        text_parts: list[str] = []
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            async with client.stream("POST", "/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    piece = chunk.get("response", "")
                    if piece:
                        text_parts.append(piece)
                        if on_token:
                            await on_token(piece)
                    if chunk.get("done"):
                        break
        return "".join(text_parts)

    async def _do_health_check(self) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            n = len(data.get("models", []))
            return f"{n} model(s) available"
