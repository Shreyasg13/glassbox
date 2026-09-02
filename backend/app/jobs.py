"""Background-job bookkeeping shared by agent test-runs, orchestration
runs, and report generation.

Per docs/PERFORMANCE_AND_ORCHESTRATION.md section 1: request handlers
that touch an LLM must return immediately with a job id and do the actual
work in a background task (`asyncio.create_task(jobs.run_job(...))`),
never await it inline. `run_job` marks the row running, awaits the
caller's work coroutine, and always records a terminal frame -- even on
an unexpected exception -- so a WS client can never be left hanging.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from . import db
from .job_events import broadcaster


def new_job(kind: str) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "error": None,
    }
    db.create_job(job)
    return job


async def log(job_id: str, message: str) -> None:
    await broadcaster.publish(
        job_id,
        {"type": "log", "data": {"message": message, "ts": datetime.now(timezone.utc).isoformat()}},
    )


async def token(job_id: str, text: str) -> None:
    await broadcaster.publish(job_id, {"type": "token", "data": {"text": text}})


async def run_job(job_id: str, work: Callable[[], Awaitable[dict]]) -> None:
    db.update_job(job_id, {"status": "running"})
    await broadcaster.publish(job_id, {"type": "status", "data": db.get_job(job_id)})
    try:
        result = await work()
    except Exception as exc:  # noqa: BLE001 -- terminal frame must always fire
        await log(job_id, f"error: {exc}")
        db.update_job(job_id, {"status": "error", "error": str(exc)})
        await broadcaster.finish(job_id, {"type": "status", "data": db.get_job(job_id)})
        return
    db.update_job(job_id, {"status": "done", "result": result})
    await broadcaster.finish(job_id, {"type": "status", "data": db.get_job(job_id)})
