"""Ported read routes from DASHBOARD_PRO.py (see app/data_source.py).

Phase 6: hot reads go through `cache.hot_read_cache` -- a short TTL cache
keyed by the underlying source file(s)' mtime, per
docs/PERFORMANCE_AND_ORCHESTRATION.md section 1. This also moves the
actual (blocking, parquet/pandas-touching) read off the event loop via
`asyncio.to_thread` inside `get_or_compute_async`, closing a gap where
these handlers previously ran that I/O directly inline.

`/api/track1/agents`, `/api/track2/agents`, and `/api/agent-performance`
return static in-memory constants with no I/O -- there's nothing to
cache there, so they're left as-is.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from .. import data_source as ds
from ..cache import hot_read_cache
from ..models import (
    AgentPerformance,
    DailySummary,
    HistoricalReport,
    HoldingsResponse,
    LiveSignalsResponse,
    TrackAgentsResponse,
    TrackDataPoint,
)

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/data", response_model=List[TrackDataPoint])
async def api_data():
    result = await hot_read_cache.get_or_compute_async(
        "api_data", ds.report_source_paths(), ds.load_latest_data
    )
    return result or []


@router.get("/track1/data", response_model=List[TrackDataPoint])
async def api_track1_data():
    return await hot_read_cache.get_or_compute_async(
        "track1_data", ds.track_source_paths("track1_performance.json"), ds.get_track1_data
    )


@router.get("/track2/data", response_model=List[TrackDataPoint])
async def api_track2_data():
    return await hot_read_cache.get_or_compute_async(
        "track2_data", ds.track_source_paths("track2_performance.json"), ds.get_track2_data
    )


@router.get("/track1/agents", response_model=TrackAgentsResponse)
async def api_track1_agents():
    return {"agents": ds.TRACK1_AGENTS, "vn_score": 0.85, "total_agents": 3}


@router.get("/track2/agents", response_model=TrackAgentsResponse)
async def api_track2_agents():
    return {"agents": ds.TRACK2_AGENTS, "vn_score": 0.92, "total_agents": 7}


@router.get("/agent-performance", response_model=List[AgentPerformance])
async def api_agent_performance():
    return ds.AGENT_PERFORMANCE


@router.get("/holdings", response_model=HoldingsResponse)
async def api_holdings():
    return await hot_read_cache.get_or_compute_async(
        "holdings", ds.live_signals_source_paths(), ds.get_holdings
    )


@router.get("/live-signals", response_model=LiveSignalsResponse)
async def api_live_signals():
    return await hot_read_cache.get_or_compute_async(
        "live_signals", ds.live_signals_source_paths(), ds.get_live_signals
    )


@router.get("/historical-reports", response_model=List[HistoricalReport])
async def api_historical_reports():
    return await hot_read_cache.get_or_compute_async(
        "historical_reports", ds.report_source_paths(), ds.get_historical_reports
    )


@router.get("/daily-summary", response_model=DailySummary | dict)
async def api_daily_summary():
    return await hot_read_cache.get_or_compute_async(
        "daily_summary", ds.report_source_paths(), ds.get_daily_summary
    )
