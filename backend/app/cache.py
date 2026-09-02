"""Tiny TTL + source-mtime cache for hot read endpoints.

Hand-rolled instead of `cachetools` -- the invalidation rule needed here
isn't pure TTL, it's "TTL, but a genuinely new source file invalidates
immediately" (a report landing mid-window shouldn't wait out the TTL),
which `cachetools.TTLCache` doesn't provide on its own. See
docs/PERFORMANCE_AND_ORCHESTRATION.md section 1.

`get_or_compute_async` also fixes a pre-existing gap: the routes calling
into this cache were previously running blocking file/pandas I/O
directly inside an `async def` handler with no `asyncio.to_thread`,
which stalls the event loop for every other request during that read.
Routing the (now-cached) compute through a thread closes that gap too.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple


class MtimeTTLCache:
    def __init__(self, ttl_s: float = 2.5) -> None:
        self.ttl_s = ttl_s
        self._store: Dict[str, Tuple[float, float, Any]] = {}  # key -> (cached_at, fingerprint, value)

    @staticmethod
    def _fingerprint(paths: Iterable[Path]) -> float:
        latest = 0.0
        for p in paths:
            try:
                latest = max(latest, p.stat().st_mtime)
            except OSError:
                continue
        return latest

    async def get_or_compute_async(
        self, key: str, source_paths: Iterable[Path], compute: Callable[[], Any]
    ) -> Any:
        paths = list(source_paths)
        fingerprint = self._fingerprint(paths)
        entry = self._store.get(key)
        now = time.monotonic()
        if entry is not None:
            cached_at, cached_fingerprint, value = entry
            if cached_fingerprint == fingerprint and now - cached_at < self.ttl_s:
                return value
        value = await asyncio.to_thread(compute)
        self._store[key] = (now, fingerprint, value)
        return value


# Shared by app/routers/data.py and app/routers/ws.py so N REST clients and
# the /ws/signals broadcast loop don't each trigger their own redundant
# parquet/JSON reads within the same TTL window.
hot_read_cache = MtimeTTLCache(ttl_s=2.5)
