"""Cross-provider failover: keep LLM work moving when one provider is out.

Gemini's free tier is 20 requests/day on most flash models, so a single-provider
setup stalls the moment it is spent. complete_routed() wraps the existing
per-provider model chain (llm_call_logging.complete_with_logging) in a loop over
a FAILOVER ORDER of other providers -- free ones first (OpenRouter's free models,
Groq, Cerebras, GitHub Models, Qwen, a gateway you run such as OmniRoute or
LiteLLM), then cheap paid ones (DeepSeek, xAI Grok) if you have set their keys,
then a local Ollama container. A provider with no key is simply skipped, so
setting a key is all it takes to enable one.

WHAT IT DECIDES
* The requested provider is always tried first (unless it is cooling down).
* A provider that is rate-limited or out of credits gets a COOLDOWN sized to
  what it told us (Retry-After; an hour for a per-day/credit limit; ~90s for a
  per-minute one), and is skipped until it expires -- so a spent Gemini quota
  costs one failed call, not one per agent. Other failures back off
  exponentially (30s -> 10min); a rejected key rests for hours.
* Failover targets use their OWN model lists (never the primary's model ids).
* A total time budget (LLM_ROUTE_BUDGET_S, default 120s) stops a long walk.
* If nothing else is usable, a cooling primary is still tried as a last resort.
* If only the primary was ever tried, its original exception is re-raised
  unchanged, so behaviour is identical to before when no failover is configured.

CONFIG (env): LLM_FAILOVER (comma order), LLM_FAILOVER_ENABLED=0 to switch it
off, LLM_ROUTE_BUDGET_S, and per-provider model overrides <NAME>_MODELS.

PRIVACY: a failover provider sees the prompt. Free tiers often log requests and
may train on them; do not enable them for prompts containing real customers'
personal data unless you accept that (LLM_FAILOVER_USER_RUNS=0 turns failover
off for runs started by end users, see routers/me.py).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import llm_call_logging
from .providers.base import CircuitOpenError, ModelUnavailableError, NotConfiguredError, OnToken, RateLimitedError
from .providers.factory import get_provider
from .providers.openai_compat import SPECS

log = logging.getLogger("glassbox.router")

# Free first, then cheap-paid (only if you set their keys), then local.
DEFAULT_ORDER = "gemini,gateway,openrouter,groq,cerebras,github,qwen,deepseek,xai,ollama"

# Failover model lists for providers that are not OpenAI-compatible.
_FAILOVER_MODELS = {
    # The lite Gemini models carry the highest free daily quota (500 vs 20).
    "gemini": ("GEMINI_FAILOVER_MODELS", "gemini-2.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash-lite"),
    "ollama": ("OLLAMA_FAILOVER_MODELS", "qwen2.5:1.5b-instruct"),
    "claude": ("CLAUDE_FAILOVER_MODELS", ""),
    "vllm": ("VLLM_FAILOVER_MODELS", ""),
}

# Friendly names + where to get a key, for the providers that are not OpenAI-compatible.
_NATIVE_INFO = {
    "gemini": ("Google Gemini", "free", "https://aistudio.google.com/apikey"),
    "claude": ("Anthropic Claude", "paid", "https://console.anthropic.com/settings/keys"),
    "ollama": ("Ollama (local container)", "local", ""),
    "vllm": ("vLLM (self-hosted)", "local", ""),
}

_RATE_LIMIT_COOLDOWN_S = 90.0
_DAILY_COOLDOWN_S = 3600.0
_KEY_REJECTED_COOLDOWN_S = 6 * 3600.0

_cooldowns: Dict[str, Tuple[float, str]] = {}  # provider -> (until_monotonic, reason)
_streak: Dict[str, int] = {}
_last: Dict[str, Dict[str, Any]] = {}  # provider -> {"ok": bool, "at": iso, "detail": str}
_ollama_probe: Dict[str, Tuple[float, bool]] = {}


class AllProvidersFailedError(RuntimeError):
    """Every usable provider in the failover order failed. `tried` lists who and why."""

    def __init__(self, message: str, tried: List[Dict[str, str]]) -> None:
        super().__init__(message)
        self.tried = tried


@dataclass
class RoutedResult:
    text: str
    provider: str
    model: str
    tried: List[Dict[str, str]] = field(default_factory=list)  # providers that failed before the winner


# ------------------------------------------------------------------ config --


def enabled() -> bool:
    return os.environ.get("LLM_FAILOVER_ENABLED", "1").strip() != "0"


def user_runs_may_fail_over() -> bool:
    return os.environ.get("LLM_FAILOVER_USER_RUNS", "1").strip() != "0"


def failover_order() -> List[str]:
    raw = os.environ.get("LLM_FAILOVER", "").strip() or DEFAULT_ORDER
    known = set(SPECS) | set(_FAILOVER_MODELS)
    out: List[str] = []
    for name in (p.strip().lower() for p in raw.split(",")):
        if name in known and name not in out:
            out.append(name)
        elif name and name not in known:
            log.warning("LLM_FAILOVER names unknown provider %r -- ignored", name)
    return out


def _budget_s() -> float:
    try:
        return float(os.environ.get("LLM_ROUTE_BUDGET_S", "120"))
    except ValueError:
        return 120.0


# --------------------------------------------------------------- cooldowns --


def cooldown_remaining(provider: str) -> Tuple[int, str]:
    entry = _cooldowns.get(provider)
    if not entry:
        return 0, ""
    left = entry[0] - time.monotonic()
    if left <= 0:
        _cooldowns.pop(provider, None)
        return 0, ""
    return int(left) + 1, entry[1]


def _cooldown_for(exc: BaseException, streak: int) -> float:
    if isinstance(exc, RateLimitedError):
        if exc.retry_after_s:
            return min(exc.retry_after_s + 1.0, _DAILY_COOLDOWN_S)
        return _DAILY_COOLDOWN_S if exc.daily else _RATE_LIMIT_COOLDOWN_S
    if isinstance(exc, NotConfiguredError):
        return _KEY_REJECTED_COOLDOWN_S
    if isinstance(exc, CircuitOpenError):
        return 30.0
    if isinstance(exc, ModelUnavailableError):
        return 0.0  # a model-level problem, tracked per model (gemini_quota), not per provider
    return min(30.0 * (2 ** max(streak - 1, 0)), 600.0)


def _reason(exc: BaseException) -> str:
    # Provider messages are built from the provider name + HTTP status only
    # (see openai_compat / gemini), so this is safe to store and display.
    return (str(exc) or exc.__class__.__name__)[:140]


def note_failure(provider: str, exc: BaseException) -> None:
    from datetime import datetime, timezone

    _streak[provider] = _streak.get(provider, 0) + 1
    secs = _cooldown_for(exc, _streak[provider])
    if secs > 0:
        _cooldowns[provider] = (time.monotonic() + secs, _reason(exc))
        log.warning("llm provider %s cooling down %ds: %s", provider, int(secs), _reason(exc))
    _last[provider] = {"ok": False, "at": datetime.now(timezone.utc).isoformat(), "detail": _reason(exc)}


def note_success(provider: str) -> None:
    from datetime import datetime, timezone

    _streak.pop(provider, None)
    _cooldowns.pop(provider, None)
    _last[provider] = {"ok": True, "at": datetime.now(timezone.utc).isoformat(), "detail": "ok"}


def reset_state() -> None:
    """For tests."""
    _cooldowns.clear()
    _streak.clear()
    _last.clear()
    _ollama_probe.clear()


# ---------------------------------------------------------- provider access --


async def _configured(name: str) -> Tuple[bool, str]:
    inst = get_provider(name)  # type: ignore[arg-type]
    if name in SPECS:
        return (True, "") if inst.is_configured else (False, inst._missing_what())
    if name in ("gemini", "claude"):
        return (True, "") if getattr(inst, "api_key", None) else (False, "API key not set")
    if name in ("ollama", "vllm"):
        now = time.monotonic()
        cached = _ollama_probe.get(name)
        if cached is None or now - cached[0] > 60:
            cached = (now, (await inst.health_check()).reachable)
            _ollama_probe[name] = cached
        return (True, "") if cached[1] else (False, "server not reachable")
    return False, "unknown provider"


async def _models_for(name: str, primary: str, model: str, fallbacks: Optional[List[str]]) -> List[str]:
    if name == primary:
        return llm_call_logging._candidate_chain(model, fallbacks)
    if name in SPECS:
        return await get_provider(name).candidate_models()  # type: ignore[union-attr]
    env, default = _FAILOVER_MODELS.get(name, ("", ""))
    return [m.strip() for m in (os.environ.get(env, "") or default).split(",") if m.strip()]


async def _plan(primary: str, allow_failover: bool) -> List[str]:
    order = [primary]
    if allow_failover and enabled():
        order += [p for p in failover_order() if p != primary]
    return order


# ------------------------------------------------------------------ routing --


async def complete_routed(
    provider: str,
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
    on_fallback: Optional[llm_call_logging.OnFallback] = None,
    allow_failover: bool = True,
) -> RoutedResult:
    """Complete on `provider` (with its own model chain); if that fails, walk the
    failover order. Returns which provider/model actually answered."""
    started = time.monotonic()
    plan = await _plan(provider, allow_failover)
    tried: List[Dict[str, str]] = []
    primary_exc: Optional[BaseException] = None
    primary_skipped = False
    last_exc: Optional[BaseException] = None

    async def attempt(name: str) -> Optional[RoutedResult]:
        nonlocal last_exc, primary_exc
        ok, why = await _configured(name)
        if not ok:
            tried.append({"provider": name, "result": f"skipped: {why}"})
            return None
        try:
            models = await _models_for(name, provider, model, fallback_models)
        except Exception as exc:  # noqa: BLE001 -- discovery trouble must never abort the whole route
            tried.append({"provider": name, "result": f"skipped: could not list models ({exc.__class__.__name__})"})
            return None
        if not models:
            tried.append({"provider": name, "result": "skipped: no models configured"})
            return None
        failed = [t for t in tried if not t["result"].startswith("skipped")]
        if failed and on_fallback:  # name the provider that actually FAILED, not one we merely skipped
            await on_fallback(name, f"provider '{failed[-1]['provider']}' failed ({failed[-1]['result']}); trying '{name}'")
        try:
            text, used = await llm_call_logging.complete_with_logging(
                name, models[0], prompt, agent_id=agent_id, system=system, temperature=temperature, top_p=top_p,
                max_tokens=max_tokens, on_token=on_token, fallback_models=models[1:], on_fallback=on_fallback,
            )
        except Exception as exc:  # noqa: BLE001 -- any provider failure means "try the next one"
            note_failure(name, exc)
            last_exc = exc
            if name == provider:
                primary_exc = exc
            tried.append({"provider": name, "result": _reason(exc)})
            return None
        note_success(name)
        return RoutedResult(text=text, provider=name, model=used, tried=[t for t in tried if not t["result"].startswith("skipped")])

    for name in plan:
        if name != provider and time.monotonic() - started > _budget_s():
            tried.append({"provider": name, "result": "skipped: time budget spent"})
            break
        left, why = cooldown_remaining(name)
        if left:
            if name == provider:
                primary_skipped = True
            tried.append({"provider": name, "result": f"skipped: cooling down {left}s ({why})"})
            continue
        result = await attempt(name)
        if result is not None:
            return result

    if primary_skipped:  # everything else failed or was unusable: a cooling primary beats giving up
        result = await attempt(provider)
        if result is not None:
            return result

    real = [t for t in tried if not t["result"].startswith("skipped")]
    if len(real) <= 1 and primary_exc is not None and last_exc is primary_exc:
        raise primary_exc  # no failover was possible: behave exactly as before
    summary = "; ".join(f"{t['provider']}: {t['result']}" for t in tried) or "no provider available"
    raise AllProvidersFailedError(f"All LLM providers failed or unavailable ({summary})", tried) from last_exc


# --------------------------------------------------------------- diagnostics --


async def status(include_models: bool = False) -> Dict[str, Any]:
    order = failover_order()
    names = list(dict.fromkeys(["gemini", "claude", *order, *SPECS, "ollama", "vllm"]))
    rows = []
    for name in names:
        ok, why = await _configured(name)
        left, cool_reason = cooldown_remaining(name)
        spec = SPECS.get(name)
        native = _NATIVE_INFO.get(name, (name, "paid", ""))
        row: Dict[str, Any] = {
            "provider": name,
            "label": spec.label if spec else native[0],
            "tier": spec.tier if spec else native[1],
            "configured": ok,
            "not_configured_reason": "" if ok else why,
            "in_failover_order": name in order,
            "cooling_down_s": left,
            "cooldown_reason": cool_reason,
            "last": _last.get(name),
            "get_a_key": spec.signup if spec else native[2],
        }
        if include_models and ok:
            try:
                row["models"] = (await _models_for(name, "", "", None))[:8]
            except Exception:  # noqa: BLE001
                row["models"] = []
        rows.append(row)
    return {"enabled": enabled(), "order": order, "budget_s": _budget_s(), "user_runs_may_fail_over": user_runs_may_fail_over(), "providers": rows}
