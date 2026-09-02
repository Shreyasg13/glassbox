"""Unit tests for MtimeTTLCache (Phase 6): serves cached values within
the TTL window, and invalidates immediately when a source file's mtime
changes even inside that window."""
from __future__ import annotations

import time

import pytest

from app.cache import MtimeTTLCache


@pytest.mark.asyncio
async def test_cache_hit_skips_recompute_within_ttl(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("v1")
    cache = MtimeTTLCache(ttl_s=5.0)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"computed-{calls['n']}"

    first = await cache.get_or_compute_async("key", [source], compute)
    second = await cache.get_or_compute_async("key", [source], compute)
    assert first == second == "computed-1"
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cache_invalidates_on_source_mtime_change(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("v1")
    cache = MtimeTTLCache(ttl_s=5.0)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"computed-{calls['n']}"

    first = await cache.get_or_compute_async("key", [source], compute)
    assert first == "computed-1"

    # Force a distinct mtime (some filesystems have 1s+ resolution).
    future = time.time() + 2
    source.write_text("v2")
    import os

    os.utime(source, (future, future))

    second = await cache.get_or_compute_async("key", [source], compute)
    assert second == "computed-2"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("v1")
    cache = MtimeTTLCache(ttl_s=0.05)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    await cache.get_or_compute_async("key", [source], compute)
    time.sleep(0.1)
    second = await cache.get_or_compute_async("key", [source], compute)
    assert second == 2
