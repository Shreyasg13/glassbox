"""LLM cost estimation for the admin observability dashboard (Phase 6).

Pricing is a static table, not a live API -- rates change over time and
must be kept current by hand. Claude rates below were verified via the
claude-api skill (its cached pricing table, dated 2026-06-24) as
$ per 1M tokens.

Gemini pricing is deliberately NOT hardcoded: this project has no
equivalently authoritative live source for it. Gemini cost is computed
only from admin-supplied GEMINI_INPUT_COST_PER_1M / GEMINI_OUTPUT_COST_PER_1M
env vars, and is `None` (the UI should render "--", not "$0.00") when
those are unset -- guessing a number here would be worse than admitting
we don't know it.

Ollama and vLLM are self-hosted: compute cost isn't metered by this
service, so their estimated cost is always $0.00 (a known, correct
answer, not a missing one).

Token counts fed into `estimate_cost` are themselves approximate (see
app/llm_call_logging.py) -- a whitespace-based estimate, not an exact
tokenizer count -- so treat the resulting dollar figure as directional,
not a billing-grade number.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

# provider -> {model name prefix: (input_$_per_1M, output_$_per_1M)}
PRICING: Dict[str, Dict[str, Tuple[float, float]]] = {
    "claude": {
        "claude-fable-5-1": (10.0, 50.0),
        "claude-mythos-5-1": (10.0, 50.0),
        "claude-fable-5": (10.0, 50.0),
        "claude-opus-5": (5.0, 25.0),
        "claude-opus-4-8": (5.0, 25.0),
        "claude-opus-4-7": (5.0, 25.0),
        "claude-opus-4-6": (5.0, 25.0),
        "claude-sonnet-5": (2.0, 10.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-haiku-4-5": (1.0, 5.0),
    },
}


def _match_claude_rate(model: str) -> Optional[Tuple[float, float]]:
    # Longest-prefix match, so e.g. a dated/suffixed variant of a known
    # model id still resolves to the right entry instead of missing.
    candidates = [name for name in PRICING["claude"] if model.startswith(name)]
    if not candidates:
        return None
    best = max(candidates, key=len)
    return PRICING["claude"][best]


def estimate_cost(provider: str, model: str, tokens_in: Optional[int], tokens_out: Optional[int]) -> Optional[float]:
    if provider in ("ollama", "vllm"):
        return 0.0
    # OpenRouter's ":free" models and its "openrouter/free" router cost exactly
    # nothing -- a known answer. Every other OpenAI-compatible provider's price
    # depends on the plan/model and is deliberately left unknown (None -> "--")
    # rather than guessed.
    if provider == "openrouter" and (model.endswith(":free") or model == "openrouter/free"):
        return 0.0

    tokens_in = tokens_in or 0
    tokens_out = tokens_out or 0

    if provider == "claude":
        rate = _match_claude_rate(model)
        if rate is None:
            return None
        input_rate, output_rate = rate
    elif provider == "gemini":
        in_env = os.environ.get("GEMINI_INPUT_COST_PER_1M")
        out_env = os.environ.get("GEMINI_OUTPUT_COST_PER_1M")
        if not in_env or not out_env:
            return None
        try:
            input_rate, output_rate = float(in_env), float(out_env)
        except ValueError:
            return None
    else:
        return None

    return round((tokens_in / 1_000_000) * input_rate + (tokens_out / 1_000_000) * output_rate, 6)
