"""Phase 5: LLM-narrated daily reports.

Reuses the same "latest daily_*.json on disk" resolution `data_source.py`
already implements for /api/historical-reports and /api/daily-summary
(`ds.load_latest_data`) rather than reimplementing report-file lookup.
Generation always runs as a background job -- see jobs.py -- so a slow
provider round-trip can never block this or any other request.

Phase 6: narration now goes through `complete_with_logging` (same helper
`orchestration.py` uses) instead of calling the provider directly, so
report-generation calls show up in the `llm_calls` cost/latency log too
-- previously this was the one LLM call path with no observability. The
generate call is also written to the audit log.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from .. import data_source as ds
from .. import db
from .. import jobs
from ..auth import TokenPayload, require_admin
from ..llm_call_logging import complete_with_logging
from ..models import DailyReportNarrative, JobAccepted, ReportGenerateRequest

router = APIRouter(prefix="/reports", tags=["reports"])


def _build_prompt(report_date: str, report_data: list, live_signals: dict) -> str:
    latest = report_data[-1] if report_data else {}
    return "\n".join(
        [
            f"Daily trading report for {report_date}.",
            (
                f"Portfolio value: {latest.get('portfolio_value')}, "
                f"daily return: {latest.get('daily_return')}, "
                f"signal: {latest.get('signal')}, positions: {latest.get('positions')}."
            ),
            f"Live signal summary: {live_signals.get('summary')}.",
            "Write a concise, professional narrative (3-5 sentences) summarizing the "
            "day's performance and current signal posture for an investor audience.",
        ]
    )


@router.post("/generate", response_model=JobAccepted, status_code=202, dependencies=[Depends(require_admin)])
async def generate_report(body: ReportGenerateRequest, user: TokenPayload = Depends(require_admin)):
    data = await asyncio.to_thread(ds.load_latest_data)
    if not data:
        raise HTTPException(status_code=404, detail="No report data available to narrate")

    system_prompt = None
    if body.agent_id:
        agent_row = db.get_agent(body.agent_id)
        if agent_row:
            system_prompt = agent_row.get("system_prompt")

    job = jobs.new_job("report_generate")
    job_id = job["job_id"]
    report_date = body.date or datetime.now(timezone.utc).strftime("%Y%m%d")
    db.log_audit(
        user.sub,
        "report.generate",
        "report",
        None,
        {"job_id": job_id, "date": report_date, "provider": body.provider, "model": body.model},
    )

    async def _work():
        await jobs.log(job_id, "Loading latest report and live signals")
        live = await asyncio.to_thread(ds.get_live_signals)
        prompt = _build_prompt(report_date, data, live)

        async def _on_token(piece: str) -> None:
            await jobs.token(job_id, piece)

        await jobs.log(job_id, f"Calling {body.provider}/{body.model}")
        text, model_used = await complete_with_logging(
            body.provider,
            body.model,
            prompt,
            agent_id=body.agent_id,
            system=system_prompt,
            on_token=_on_token,
        )

        narrative = {
            "id": str(uuid.uuid4()),
            "date": report_date,
            "provider": body.provider,
            "model": model_used,
            "narrative": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db.create_report_narrative(narrative)
        return narrative

    asyncio.create_task(jobs.run_job(job_id, _work))
    return JobAccepted(job_id=job_id)


@router.get("/narratives", response_model=List[DailyReportNarrative], dependencies=[Depends(require_admin)])
async def list_narratives():
    return db.list_report_narratives()


@router.get("/narratives/{narrative_id}", response_model=DailyReportNarrative)
async def get_narrative(narrative_id: str):
    narrative = db.get_report_narrative(narrative_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail="Narrative not found")
    return narrative
