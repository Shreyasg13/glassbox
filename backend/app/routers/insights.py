"""LLM narration for client-derived "missed opportunity" rows.

Mirrors reports.py's generate_report exactly (background job via
jobs.run_job, complete_with_logging for cost/latency logging + audit),
the one difference being the input: the frontend already runs its own
detection rule client-side (same pattern InsightsAlertsPanel uses for
signal-derived alerts), so this endpoint narrates the rows it's handed
rather than re-deriving its own, possibly-diverging definition of
"missed opportunity" on the backend.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from .. import db
from .. import jobs
from ..auth import TokenPayload, require_admin
from .. import llm_router
from ..models import InsightNarrateRequest, JobAccepted

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _build_prompt(candidates: list) -> str:
    rows = "\n".join(
        f"- {c.symbol}: {c.signal} signal at {c.confidence:.0f}% confidence -- {c.reason}"
        for c in candidates
    )
    return "\n".join(
        [
            "The following live trading signals fired with no matching trade on record "
            "(possible missed opportunities):",
            rows,
            "In 3-5 sentences for an investor audience: summarize the pattern across these "
            "rows, note which look most worth a second look, and be explicit that this is "
            "commentary on signals, not a recommendation to trade.",
        ]
    )


@router.post("/narrate", response_model=JobAccepted, status_code=202, dependencies=[Depends(require_admin)])
async def narrate_insights(body: InsightNarrateRequest, user: TokenPayload = Depends(require_admin)):
    job = jobs.new_job("insight_narrate")
    job_id = job["job_id"]
    db.log_audit(
        user.sub,
        "insight.narrate",
        "report",
        None,
        {"job_id": job_id, "provider": body.provider, "model": body.model, "candidate_count": len(body.candidates)},
    )

    async def _work():
        await jobs.log(job_id, f"Calling {body.provider}/{body.model}")
        prompt = _build_prompt(body.candidates)

        async def _on_token(piece: str) -> None:
            await jobs.token(job_id, piece)

        async def _on_fallback(candidate: str, reason: str) -> None:
            await jobs.log(job_id, f"trying '{candidate}' ({reason})")

        routed = await llm_router.complete_routed(body.provider, body.model, prompt, on_token=_on_token, on_fallback=_on_fallback)
        return {"narrative": routed.text, "model": routed.model, "provider": routed.provider}

    asyncio.create_task(jobs.run_job(job_id, _work))
    return JobAccepted(job_id=job_id)
