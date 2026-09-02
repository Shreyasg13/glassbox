"""In-process sliding-window rate limiter (Phase 6).

Dev-deployment scope only: state lives in this process's memory. A
multi-instance production deployment needs a shared store (Redis)
instead -- per-instance in-memory counters would let each instance grant
its own quota, defeating the limit. See
docs/PERFORMANCE_AND_ORCHESTRATION.md section 6.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_s: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window_s = window_s
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.max_calls:
            retry_after = max(1, int(self.window_s - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


_login_limiter = SlidingWindowLimiter(int(os.environ.get("RATE_LIMIT_LOGIN_PER_MIN", "10")))
_admin_limiter = SlidingWindowLimiter(int(os.environ.get("RATE_LIMIT_ADMIN_PER_MIN", "60")))


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def rate_limit_login(request: Request) -> None:
    _login_limiter.check(_client_key(request))


async def rate_limit_admin_mutations(request: Request) -> None:
    if request.method in ("POST", "PUT", "DELETE"):
        _admin_limiter.check(_client_key(request))
