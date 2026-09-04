"""Local, best-effort rate-limit tracking so the fallback chain in
llm_call_logging.py can skip a model it already knows is exhausted,
rather than only reacting to a 429/402 *after* wasting a call on it.

IMPORTANT LIMITATION -- read before trusting this module's output:
there is no public Gemini/AI-Studio API to query real-time quota usage.
The RPM/TPM/RPD ceilings below are the free-tier numbers the user read
directly off their own Google AI Studio quota dashboard (a UI-only
view, not a queryable endpoint) on 2026-09-04. This tracker counts
calls made by THIS PROCESS and compares them against those ceilings in
a sliding window -- it has zero visibility into calls made from other
tools, sessions, or API keys against the same account, so it can
under-report real usage and still occasionally see a live 429/402
despite reporting headroom. The reactive fallback (any failure -> try
the next candidate) is the actual backstop for that gap; this tracker
only reduces how often the backstop needs to fire by skipping calls we
already suspect are doomed, it doesn't replace it.

These ceilings will drift as Google changes free-tier limits or the
account's tier changes -- there is no automated way to re-sync them.
Update GEMINI_LIMITS by hand if the numbers on the dashboard change.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

# model id -> (RPM, TPM, RPD) ceiling. Only rows the user's dashboard
# showed under the "Text-out models" category with nonzero capacity are
# included -- rows shown as 0/0 (not available on this tier/key at all,
# e.g. Gemini 2 Flash, Gemini 2.5 Pro, Gemini 3.1 Pro at capture time)
# are deliberately excluded, since no amount of waiting gives a 0-ceiling
# model headroom. Non-text-out categories (Agents, Live API, Multi-modal
# generative, Other) are out of scope -- this chain serves the LLM agent
# narration/reasoning use case, not image/audio/embedding generation.
# Source: user-pasted AI Studio quota table, captured 2026-09-04.
GEMINI_LIMITS: Dict[str, Tuple[int, int, int]] = {
    "gemini-3.8-flash": (5, 250_000, 20),
    "gemini-3.7-flash": (5, 250_000, 20),
    "gemini-3.6-flash": (5, 250_000, 20),
    "gemini-3.5-flash": (5, 250_000, 20),
    "gemini-3.5-flash-lite": (15, 250_000, 500),
    "gemini-3.1-flash-lite": (15, 250_000, 500),
    "gemini-3-flash": (5, 250_000, 20),
    "gemini-2.5-flash": (5, 250_000, 20),
    "gemini-2.5-flash-lite": (10, 250_000, 20),
}

_RPM_WINDOW_S = 60.0
_RPD_WINDOW_S = 24 * 60 * 60.0

# model -> deque of (monotonic_timestamp, tokens_used) for calls this
# process has made. Bounded implicitly by _prune() dropping anything
# older than the RPD window (the widest window we care about).
_call_log: Dict[str, Deque[Tuple[float, int]]] = defaultdict(deque)


def _prune(model: str, now: float) -> None:
    dq = _call_log[model]
    while dq and now - dq[0][0] > _RPD_WINDOW_S:
        dq.popleft()


def has_headroom(model: str, estimated_tokens: int = 0) -> bool:
    """True if this process's own recent usage suggests `model` has
    headroom under its RPM/TPM/RPD ceiling. Models with no known ceiling
    (not in GEMINI_LIMITS -- includes alias names like
    "gemini-flash-latest", which resolve to a real model server-side that
    we can't identify locally) always report headroom: we simply don't
    have data either way, so let the reactive fallback in
    llm_call_logging.py be the only guard for those.
    """
    limits = GEMINI_LIMITS.get(model)
    if limits is None:
        return True
    rpm_limit, tpm_limit, rpd_limit = limits
    now = time.monotonic()
    _prune(model, now)
    dq = _call_log[model]
    rpm_used = sum(1 for ts, _tok in dq if now - ts <= _RPM_WINDOW_S)
    tpm_used = sum(tok for ts, tok in dq if now - ts <= _RPM_WINDOW_S)
    rpd_used = len(dq)
    return rpm_used < rpm_limit and tpm_used + estimated_tokens <= tpm_limit and rpd_used < rpd_limit


def record_call(model: str, tokens: int = 0) -> None:
    """Call after a successful completion so future has_headroom() checks
    for this model reflect it. Silently a no-op for models with no known
    ceiling -- nothing to track against."""
    if model not in GEMINI_LIMITS:
        return
    _call_log[model].append((time.monotonic(), tokens))
