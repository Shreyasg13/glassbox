"""Unit tests for the sliding-window rate limiter (Phase 6).

Exercises SlidingWindowLimiter.check() directly rather than through the
HTTP layer -- that keeps the test deterministic and independent of the
module-level singletons' shared state across the rest of the test suite.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.rate_limit import SlidingWindowLimiter


def test_limiter_allows_up_to_max_calls():
    limiter = SlidingWindowLimiter(max_calls=3, window_s=60.0)
    for _ in range(3):
        limiter.check("client-a")  # should not raise


def test_limiter_trips_after_max_calls():
    limiter = SlidingWindowLimiter(max_calls=3, window_s=60.0)
    for _ in range(3):
        limiter.check("client-a")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_limiter_keys_independently_per_client():
    limiter = SlidingWindowLimiter(max_calls=1, window_s=60.0)
    limiter.check("client-a")
    limiter.check("client-b")  # different key -- should not raise
    with pytest.raises(HTTPException):
        limiter.check("client-a")
