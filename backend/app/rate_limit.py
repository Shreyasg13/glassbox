"""In-process sliding-window rate limiter (Phase 6, hardened).

State lives in this process's memory (per gunicorn worker), which is the
right trade for the single small VM this ships on: zero extra services to
run or pay for. A multi-instance deployment needs a shared store (Redis)
instead -- per-instance counters would each grant their own quota. See
docs/PERFORMANCE_AND_ORCHESTRATION.md section 6.

The client key is `request.client.host`. Behind Caddy that is only the
real visitor IP if uvicorn is told to trust the proxy's X-Forwarded-For
(the Dockerfile does: --forwarded-allow-ips). Without that every visitor
shares Caddy's IP and therefore ONE bucket -- one abusive client could
lock everyone out of login, and no one could be told apart.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

# Cap on distinct keys held at once. Without a cap, a flood of unique keys
# (e.g. spoofed or rotating IPs) would grow this dict without bound.
_MAX_KEYS = 20_000


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_s: float = 60.0, detail: str = "Rate limit exceeded") -> None:
        self.max_calls = max_calls
        self.window_s = window_s
        self.detail = detail
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> Deque[float]:
        # Evict BEFORE fetching this key's deque: evicting afterwards could
        # delete the brand-new (still empty) deque we're about to return,
        # silently dropping the hit the caller then records on it.
        if len(self._hits) > _MAX_KEYS:
            self._evict(now)
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        return hits

    def _evict(self, now: float) -> None:
        for k in [k for k, h in self._hits.items() if not h or now - h[-1] > self.window_s]:
            del self._hits[k]
        # Still over the cap after dropping every idle key: drop the oldest
        # half rather than let it grow.
        if len(self._hits) > _MAX_KEYS:
            for k in list(self._hits)[: len(self._hits) // 2]:
                del self._hits[k]

    def _raise(self, hits: Deque[float], now: float) -> None:
        retry_after = max(1, int(self.window_s - (now - hits[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=self.detail,
            headers={"Retry-After": str(retry_after)},
        )

    def check(self, key: str) -> None:
        """Counts this call and raises 429 if it exceeds the budget."""
        now = time.monotonic()
        hits = self._prune(key, now)
        if len(hits) >= self.max_calls:
            self._raise(hits, now)
        hits.append(now)

    # -- failure-tracking form (login lockout): check first, record later --

    def raise_if_blocked(self, key: str) -> None:
        now = time.monotonic()
        hits = self._prune(key, now)
        if len(hits) >= self.max_calls:
            self._raise(hits, now)

    def record(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


_login_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_LOGIN_PER_MIN", 10))
_admin_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_ADMIN_PER_MIN", 60))
# Separate from login's limiter -- mass account creation is a distinct
# abuse concern from login brute-forcing, worth its own (tighter) budget
# rather than sharing login's counter/env var.
_signup_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_SIGNUP_PER_MIN", 5))

# Per-USERNAME failed-login budget, on top of the per-IP one above: a
# botnet spreading guesses across many IPs still hits this. Generous
# enough (default 20 / 15 min) that a real person fumbling a password
# never sees it; temporary, so it can't permanently lock anyone out.
login_lockout = SlidingWindowLimiter(
    _env_int("RATE_LIMIT_LOGIN_FAILS_PER_15MIN", 20),
    window_s=900.0,
    detail="Too many failed sign-in attempts for this account. Try again later.",
)

# Public, CPU-heavy simulation endpoint.
_monte_carlo_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_MONTE_CARLO_PER_MIN", 20))

# /api/tts is public and every cache MISS spends real provider quota
# (ElevenLabs is metered per character), so it gets a per-minute and a
# per-day budget per client. Cache hits are free and don't count -- see
# routers/tts.py, which only calls check_tts_limits() on a miss.
_tts_minute_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_TTS_PER_MIN", 10))
_tts_day_limiter = SlidingWindowLimiter(
    _env_int("RATE_LIMIT_TTS_PER_DAY", 150),
    window_s=86_400.0,
    detail="Daily voice limit reached.",
)

# Authenticated, LLM-backed actions (run-report, verify): per-USER budget.
_user_heavy_limiter = SlidingWindowLimiter(_env_int("RATE_LIMIT_USER_HEAVY_PER_MIN", 10))
# A full report run fans out to ~8 LLM calls, so it gets a much tighter,
# hourly per-user budget -- any self-serve signup can reach that endpoint.
_user_report_limiter = SlidingWindowLimiter(
    _env_int("RATE_LIMIT_USER_REPORTS_PER_HOUR", 6),
    window_s=3600.0,
    detail="Report run limit reached. Try again later.",
)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# Kept for callers/tests that used the old private name.
_client_key = client_key


async def rate_limit_login(request: Request) -> None:
    _login_limiter.check(client_key(request))


async def rate_limit_signup(request: Request) -> None:
    _signup_limiter.check(client_key(request))


async def rate_limit_admin_mutations(request: Request) -> None:
    if request.method in ("POST", "PUT", "DELETE"):
        _admin_limiter.check(client_key(request))


async def rate_limit_monte_carlo(request: Request) -> None:
    _monte_carlo_limiter.check(client_key(request))


def check_tts_limits(request: Request) -> None:
    key = client_key(request)
    _tts_minute_limiter.check(key)
    _tts_day_limiter.check(key)


def check_user_heavy(username: str) -> None:
    _user_heavy_limiter.check(username.lower())


def check_user_report(username: str) -> None:
    _user_report_limiter.check(username.lower())
