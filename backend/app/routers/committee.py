"""Admin view of the daily Investment Committee: recent decisions, how they have
scored so far, and a manual "review now" button (the same code cron runs)."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import committee_daily, data_source as ds, db, paper_cycle
from ..auth import TokenPayload, require_admin
from ..rate_limit import rate_limit_admin_mutations

log = logging.getLogger("glassbox.committee")

router = APIRouter(
    prefix="/api/admin/committee",
    tags=["committee"],
    dependencies=[Depends(require_admin), Depends(rate_limit_admin_mutations)],
)


class CommitteeAskRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    question: str = Field(default="", max_length=committee_daily.ASK_MAX_QUESTION)


class CommitteeRunRequest(BaseModel):
    symbols: Optional[List[str]] = Field(default=None, max_length=15)
    force: bool = False
    dry_run: bool = False  # preview the picks without calling any model


@router.get("/runs")
async def runs(limit: int = Query(40, ge=1, le=300)):
    return {"running": await run_in_threadpool(committee_daily.is_running), "runs": await run_in_threadpool(db.list_committee_runs, limit)}


@router.get("/scorecard")
async def scorecard():
    """Forward returns of the committee's decisions and how often it echoed the engine."""

    def _compute():
        return committee_daily.committee_scorecard(paper_cycle.load_book(), db.list_all_committee_runs())

    try:
        return await run_in_threadpool(_compute)
    except Exception as exc:  # noqa: BLE001 -- e.g. no price data on this machine
        raise HTTPException(status_code=503, detail=f"Scorecard unavailable: {type(exc).__name__}") from None


@router.post("/ask")
async def ask(body: CommitteeAskRequest, user: TokenPayload = Depends(require_admin)):
    """Sandbox: put a question about one symbol to the whole committee and read every agent's
    answer. Never saved as a decision. Returns 202 with an id to poll at GET /asks/{id}."""
    symbol = body.symbol.strip().upper()
    if symbol not in ds.STOCK_INFO:
        raise HTTPException(status_code=422, detail=f"Unknown symbol {symbol!r}")
    if await run_in_threadpool(committee_daily.ask_in_flight):
        raise HTTPException(status_code=409, detail="Another question is still being answered")
    doc = committee_daily.new_ask_doc(symbol, body.question)
    await run_in_threadpool(db.save_committee_ask, doc)

    async def _bg():
        try:
            await committee_daily.run_ask(doc)
        except Exception as exc:  # noqa: BLE001 -- run_ask records its own failures; this is the last line of defence
            log.error("committee ask crashed: %s", exc)

    asyncio.create_task(_bg())
    db.log_audit(user.sub, "committee.ask", "committee", None, {"symbol": symbol})
    return JSONResponse({"started": True, "id": doc["id"]}, status_code=202)


@router.get("/asks")
async def asks(limit: int = Query(10, ge=1, le=30)):
    rows = await run_in_threadpool(db.list_committee_asks, limit)
    return [{"id": a["id"], "symbol": a.get("symbol"), "question": a.get("question"), "status": a.get("status"), "created_at": a.get("created_at"), "action": a.get("action"), "decision": a.get("decision")} for a in rows]


@router.get("/asks/{ask_id}")
async def get_ask(ask_id: str):
    doc = await run_in_threadpool(db.get_committee_ask, ask_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No such question")
    return doc


@router.post("/run")
async def run(body: CommitteeRunRequest, user: TokenPayload = Depends(require_admin)):
    """dry_run=true returns today's picks immediately. Otherwise the review starts in
    the background (a full run takes a few minutes) and this returns 202; watch
    GET /runs for the decisions as they land."""
    symbols = [s.strip().upper() for s in body.symbols] if body.symbols else None
    try:
        if body.dry_run:
            return await committee_daily.run_daily(symbols=symbols, dry_run=True, force=body.force)
        if await run_in_threadpool(committee_daily.is_running):
            raise HTTPException(status_code=409, detail="A committee review is already running")

        async def _bg():
            try:
                await committee_daily.run_daily(symbols=symbols, force=body.force)
            except Exception as exc:  # noqa: BLE001 -- background task: log, never crash the server
                log.error("manual committee run failed: %s", exc)

        asyncio.create_task(_bg())
    except committee_daily.CommitteeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    db.log_audit(user.sub, "committee.run", "committee", None, {"symbols": symbols, "force": body.force})
    return JSONResponse({"started": True}, status_code=202)
