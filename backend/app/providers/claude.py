"""Claude provider -- wraps the official `anthropic` async SDK.

Health check deliberately does NOT make a real API call: a `messages.create`
health ping would burn tokens/cost on every admin dashboard poll of
`/admin/providers/health`. Instead it confirms the key is present and the
client constructs cleanly, and reports "not configured" the same way the
other cloud adapters do when the key is absent. A real generation still
goes through the full timeout/circuit-breaker path in `BaseProvider`.
"""
from __future__ import annotations

import os
from typing import Optional

from anthropic import AsyncAnthropic

from .base import BaseProvider, NotConfiguredError, OnToken


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self, api_key: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Optional[AsyncAnthropic] = None

    def _client_or_raise(self) -> AsyncAnthropic:
        if not self.api_key:
            raise NotConfiguredError("ANTHROPIC_API_KEY not set")
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

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
        client = self._client_or_raise()
        if on_token:
            text_parts: list[str] = []
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    text_parts.append(text)
                    await on_token(text)
            return "".join(text_parts)
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    async def _do_health_check(self) -> str:
        self._client_or_raise()
        return "API key configured (no live call made -- avoids per-poll token cost)"
