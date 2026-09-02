"""vLLM provider -- calls a self-hosted vLLM server's OpenAI-compatible API.

vLLM's `--api-server` speaks the standard `/v1/chat/completions` and
`/v1/models` shapes, so this adapter is a thin OpenAI-protocol client
rather than anything vLLM-specific -- swapping in another OpenAI-compatible
GPU server later is just a base_url change.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from .base import BaseProvider, OnToken


class VLLMProvider(BaseProvider):
    name = "vllm"

    def __init__(self, base_url: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.base_url = base_url or os.environ.get("VLLM_BASE_URL", "http://localhost:8001")

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": bool(on_token),
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            if on_token:
                text_parts: list[str] = []
                async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[len("data: ") :]
                        if data.strip() == "[DONE]":
                            break
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content")
                        if delta:
                            text_parts.append(delta)
                            await on_token(delta)
                return "".join(text_parts)
            resp = await client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _do_health_check(self) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
            resp = await client.get("/v1/models")
            resp.raise_for_status()
            data = resp.json()
            n = len(data.get("data", []))
            return f"{n} model(s) available"
