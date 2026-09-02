"""Shared provider protocol + timeout/circuit-breaker wrapper.

Every adapter (Ollama/vLLM/Gemini/Claude) subclasses BaseProvider and
implements `_do_complete` / `_do_health_check`. `BaseProvider.complete()`
wraps that with a hard per-call timeout and a consecutive-failure circuit
breaker, per docs/PERFORMANCE_AND_ORCHESTRATION.md sections 1 and 3 --
no provider is allowed to skip this, since a stuck/failing provider must
never be able to block dashboard traffic or hang an orchestration run.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional, Protocol, runtime_checkable

from ..models import Provider, ProviderHealth

OnToken = Callable[[str], Awaitable[None]]


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        on_token: Optional[OnToken] = None,
    ) -> str: ...

    async def health_check(self) -> ProviderHealth: ...


class CircuitOpenError(RuntimeError):
    """Raised instead of making a call while the breaker is open."""


class NotConfiguredError(RuntimeError):
    """Raised by cloud providers when a required API key is absent."""


class BaseProvider:
    name: Provider

    def __init__(
        self,
        *,
        # 60s, not the original 30s: a retried call (e.g. Gemini's 429
        # backoff, up to ~36s across 2 retries) must fit inside this outer
        # wait_for or the retry logic never gets a chance to finish -- 30s
        # was cutting retries off mid-backoff and converting a recoverable
        # 429 into an unrecoverable timeout instead.
        default_timeout_s: float = 60.0,
        failure_threshold: int = 3,
        cooldown_s: float = 30.0,
    ) -> None:
        self.default_timeout_s = default_timeout_s
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._consecutive_failures = 0
        self._circuit_opened_at: Optional[float] = None

    # -- circuit breaker --

    def _circuit_is_open(self) -> bool:
        if self._circuit_opened_at is None:
            return False
        if time.monotonic() - self._circuit_opened_at >= self.cooldown_s:
            # Cooldown elapsed: half-open, let the next call attempt through.
            self._circuit_opened_at = None
            self._consecutive_failures = 0
            return False
        return True

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_opened_at = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._circuit_opened_at = time.monotonic()

    # -- public API --

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        on_token: Optional[OnToken] = None,
        timeout_s: Optional[float] = None,
    ) -> str:
        if self._circuit_is_open():
            raise CircuitOpenError(
                f"{self.name} circuit open after {self._consecutive_failures} consecutive "
                f"failures; cooling down {self.cooldown_s}s"
            )
        try:
            result = await asyncio.wait_for(
                self._do_complete(
                    prompt,
                    model=model,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    system=system,
                    on_token=on_token,
                ),
                timeout=timeout_s or self.default_timeout_s,
            )
        except NotConfiguredError:
            # Not a transient failure -- don't trip the breaker for a
            # missing API key, there's nothing a retry would fix.
            raise
        except Exception:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    async def health_check(self) -> ProviderHealth:
        try:
            detail = await asyncio.wait_for(self._do_health_check(), timeout=5.0)
            return ProviderHealth(
                provider=self.name,
                reachable=True,
                detail=detail,
                checked_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.name,
                reachable=False,
                detail=str(exc) or exc.__class__.__name__,
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

    # -- override in subclasses --

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
        raise NotImplementedError

    async def _do_health_check(self) -> str:
        raise NotImplementedError
