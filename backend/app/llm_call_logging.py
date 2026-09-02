"""Shared `llm_calls` bookkeeping wrapper around `LLMProvider.complete()`.

Used by both `app/orchestration.py` (agent test-runs / orchestration runs)
and `app/routers/reports.py` (daily report narration) so every LLM call
made anywhere in the app -- not just agent runs -- gets a row in
`llm_calls` with duration/tokens/status/estimated cost. Before this
existed, report generation called the provider directly with no logging,
which would have left a blind spot in the cost dashboard.

Token counts are a rough whitespace-based estimate (`len(text.split()) *
~1.3`), not an exact tokenizer count -- good enough to compare providers
directionally on this dashboard, not a billing-grade number. See
app/pricing.py for the same caveat on the resulting dollar estimate.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import db
from .pricing import estimate_cost
from .providers.base import OnToken
from .providers.factory import get_provider


def _estimate_tokens(text: Optional[str]) -> int:
    if not text:
        return 0
    return max(1, int(len(text.split()) * 1.3))


async def complete_with_logging(
    provider_name: str,
    model: str,
    prompt: str,
    *,
    agent_id: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 1024,
    on_token: Optional[OnToken] = None,
) -> str:
    provider = get_provider(provider_name)
    call_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    tokens_in = _estimate_tokens(prompt) + _estimate_tokens(system)

    db.create_llm_call(
        {
            "id": call_id,
            "agent_id": agent_id,
            "provider": provider_name,
            "model": model,
            "started_at": started.isoformat(),
            "status": "running",
        }
    )
    t0 = time.monotonic()

    try:
        text = await provider.complete(
            prompt,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            system=system,
            on_token=on_token,
        )
    except asyncio.TimeoutError as exc:
        db.update_llm_call(
            call_id,
            {
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "tokens_in": tokens_in,
                "status": "timeout",
                "error": str(exc),
            },
        )
        raise
    except Exception as exc:
        db.update_llm_call(
            call_id,
            {
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "tokens_in": tokens_in,
                "status": "error",
                "error": str(exc),
            },
        )
        raise

    tokens_out = _estimate_tokens(text)
    cost = estimate_cost(provider_name, model, tokens_in, tokens_out)
    db.update_llm_call(
        call_id,
        {
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "status": "ok",
            "estimated_cost_usd": cost,
        },
    )
    return text
