"""Strategy views: the admin's one-page answer to "is it working?" and the users' calm,
read-only view of the same system (their stance for the day, and the simulated track record).

Admin (/api/admin/strategy/*): decisions with the full per-agent inspector, today's risk table,
capital results incl. tax, accuracy of the engine / risk signal / committee, the agent leaderboard.
Users (/api/me/stance, /api/me/track-record): only reference strategies and their own watchlist --
never another user's paper account.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from .. import db, research, strategy
from ..auth import TokenPayload, get_current_user, require_admin
from ..rate_limit import rate_limit_admin_mutations

admin_router = APIRouter(prefix="/api/admin/strategy", tags=["strategy"], dependencies=[Depends(require_admin), Depends(rate_limit_admin_mutations)])
me_router = APIRouter(prefix="/api/me", tags=["strategy"])


def _book_or_503():
    try:
        return strategy.cached_book()
    except Exception as exc:  # noqa: BLE001 -- e.g. no price data on this machine
        raise HTTPException(status_code=503, detail=f"Price data unavailable: {type(exc).__name__}") from None


@admin_router.get("/overview")
async def overview() -> Dict[str, Any]:
    return await run_in_threadpool(lambda: strategy.overview(_book_or_503()))


@admin_router.get("/accuracy")
async def accuracy() -> Dict[str, Any]:
    """Whole-history scorecards (cached per data version) plus the live committee scorecard and leaderboard."""
    return await run_in_threadpool(lambda: strategy.accuracy(_book_or_503()))


@admin_router.get("/research")
async def research_view() -> Dict[str, Any]:
    """Today's correlations / clusters / cohesion / lead-lag, the live-evidence gate for every strategy,
    standing proposals (advice only) and the latest weekly digest."""
    return await run_in_threadpool(lambda: research.view(_book_or_503()))


@admin_router.get("/data-sources")
async def data_sources() -> Dict[str, Any]:
    return await run_in_threadpool(lambda: strategy.data_sources(_book_or_503()))


@me_router.get("/track-record")
async def track_record(user: TokenPayload = Depends(get_current_user)) -> Dict[str, Any]:
    return await run_in_threadpool(strategy.track_record)


@me_router.get("/stance")
async def stance(user: TokenPayload = Depends(get_current_user)) -> Dict[str, Any]:
    def _compute() -> Dict[str, Any]:
        row = db.get_user_by_username(user.sub)
        tickers = (row.get("tickers") or None) if row else None
        return strategy.stance(_book_or_503(), tickers)

    return await run_in_threadpool(_compute)
