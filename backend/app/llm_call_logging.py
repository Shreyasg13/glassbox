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

FALLBACK CHAIN: when `fallback_models` is given, this function tries
`model`, then each entry in `fallback_models` in order, until one
succeeds -- so an agent configured with a chain keeps producing output
across individual-model rate limits instead of failing the whole call.
Only the gemini provider currently benefits from the quota pre-check
(app/providers/gemini_quota.py) and the fail-fast retry=False behavior
on non-final candidates; other providers still get a plain "try model,
on failure try the next" loop with no quota awareness, since there's no
known per-model ceiling data for them.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional, Tuple

from . import db
from .pricing import estimate_cost
from .providers import gemini_quota
from .providers.base import OnToken
from .providers.factory import get_provider

OnFallback = Callable[[str, str], Awaitable[None]]


def _estimate_tokens(text: Optional[str]) -> int:
    if not text:
        return 0
    return max(1, int(len(text.split()) * 1.3))


def _candidate_chain(model: str, fallback_models: Optional[List[str]]) -> List[str]:
    """[model] + fallback_models, de-duplicated while preserving order --
    a fallback list that accidentally repeats the primary model (or
    itself) shouldn't cause a redundant retry against the same model."""
    seen = set()
    chain = []
    for m in [model, *(fallback_models or [])]:
        if m and m not in seen:
            seen.add(m)
            chain.append(m)
    return chain


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
    fallback_models: Optional[List[str]] = None,
    on_fallback: Optional[OnFallback] = None,
) -> Tuple[str, str]:
    """Returns (text, model_actually_used) -- the second element matters
    whenever `fallback_models` is set, since the model that actually
    served the request may differ from `model` (the first choice)."""
    provider = get_provider(provider_name)
    chain = _candidate_chain(model, fallback_models)
    tokens_in = _estimate_tokens(prompt) + _estimate_tokens(system)

    last_exc: Optional[Exception] = None
    prev_outcome: Optional[str] = None  # "failed" | "skipped", for accurate log wording below
    for i, candidate in enumerate(chain):
        is_final = i == len(chain) - 1

        # Skip a candidate our own local tracker believes is already
        # exhausted -- unless it's the last one, in which case there's
        # nothing to gain by refusing to try (see gemini_quota.py's
        # module docstring for why this check can be wrong in either
        # direction and is a pre-filter, not an authority).
        if provider_name == "gemini" and not is_final and not gemini_quota.has_headroom(candidate, tokens_in):
            if on_fallback:
                await on_fallback(candidate, "skipped: local quota tracker reports no headroom")
            prev_outcome = "skipped"
            continue

        if i > 0 and on_fallback:
            verb = "failed" if prev_outcome == "failed" else "was skipped"
            await on_fallback(candidate, f"trying after '{chain[i - 1]}' {verb}")

        call_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc)
        db.create_llm_call(
            {
                "id": call_id,
                "agent_id": agent_id,
                "provider": provider_name,
                "model": candidate,
                "started_at": started.isoformat(),
                "status": "running",
            }
        )
        t0 = time.monotonic()

        try:
            text = await provider.complete(
                prompt,
                model=candidate,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                system=system,
                on_token=on_token,
                # Fail fast on a non-final candidate: backing off and
                # retrying a model we're about to abandon anyway just
                # burns time better spent trying the next one. The final
                # candidate keeps the provider's normal retry behavior
                # since there's nothing left to fall back to.
                retry=is_final,
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
            last_exc = exc
            prev_outcome = "failed"
            if is_final:
                raise
            continue
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
            last_exc = exc
            prev_outcome = "failed"
            if is_final:
                raise
            continue

        tokens_out = _estimate_tokens(text)
        cost = estimate_cost(provider_name, candidate, tokens_in, tokens_out)
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
        if provider_name == "gemini":
            gemini_quota.record_call(candidate, tokens_in + tokens_out)
        return text, candidate

    # Every candidate was skipped by the quota pre-check (none actually
    # attempted) -- extremely unlikely given the final candidate always
    # attempts regardless, but keeps this function's contract ("returns
    # str or raises") intact rather than implicitly returning None.
    raise last_exc or RuntimeError(f"No candidate model available for provider '{provider_name}'")
