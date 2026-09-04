"""Self-service endpoints any logged-in user (viewer or admin) can call
on their own behalf -- distinct from /api/admin/* (admin-role-gated CRUD
over every agent/orchestration) and from the fully public /api/* data
endpoints. Backs the "subscribe to agents; only those run for my report"
feature: a user's subscriptions are stored on their own `users` row
(db.update_user), and running "my report" filters the seeded Investment
Committee orchestration's agent list down to that subscription before
calling the exact same orchestration.run_orchestration() the admin-
triggered run already uses -- no separate execution path to maintain.

Dev accounts (admin/user, app/auth.py's _DEV_USERS) have no real `users`
row to persist a subscription onto -- PUT rejects them with a clear
400 rather than silently no-op'ing or crashing on a None row.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from .. import jobs
from .. import orchestration
from ..auth import RESERVED_USERNAMES, TokenPayload, get_current_user
from ..models import (
    AgentSubscriptions,
    AgentSummary,
    JobAccepted,
    JobStatus,
    OrchestrationConfig,
    OrchestrationRunRequest,
)
from ..scripts.seed_agents import ORCHESTRATION_NAME

router = APIRouter(prefix="/api/me", tags=["me"])


def _require_real_user_row(user: TokenPayload) -> Dict[str, Any]:
    if user.sub.lower() in RESERVED_USERNAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dev accounts (admin/user) can't save preferences -- sign up for a real account",
        )
    row = db.get_user_by_username(user.sub)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return row


@router.get("/agents", response_model=List[AgentSummary])
async def list_available_agents(user: TokenPayload = Depends(get_current_user)):
    return db.list_agents()


@router.get("/agent-subscriptions", response_model=AgentSubscriptions)
async def get_my_subscriptions(user: TokenPayload = Depends(get_current_user)):
    if user.sub.lower() in RESERVED_USERNAMES:
        return AgentSubscriptions(agent_ids=[])
    row = db.get_user_by_username(user.sub)
    return AgentSubscriptions(agent_ids=(row or {}).get("subscribed_agent_ids") or [])


@router.put("/agent-subscriptions", response_model=AgentSubscriptions)
async def set_my_subscriptions(body: AgentSubscriptions, user: TokenPayload = Depends(get_current_user)):
    row = _require_real_user_row(user)
    known_ids = {a["id"] for a in db.list_agents()}
    unknown = [aid for aid in body.agent_ids if aid not in known_ids]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown agent id(s): {unknown}")
    db.update_user(row["id"], {"subscribed_agent_ids": body.agent_ids})
    db.log_audit(user.sub, "me.agent_subscriptions_updated", "user", row["id"], {"agent_ids": body.agent_ids})
    return AgentSubscriptions(agent_ids=body.agent_ids)


@router.post("/run-report", response_model=JobAccepted, status_code=202)
async def run_my_report(body: OrchestrationRunRequest, user: TokenPayload = Depends(get_current_user)):
    """Runs the seeded Investment Committee orchestration filtered to
    the caller's own subscribed agents -- falls back to that
    orchestration's full agent list if the caller has no subscription
    set (every dev account, and any real account that hasn't visited
    the subscriptions page yet), so "no subscription" means "everyone",
    not "nobody"."""
    orchestrations_by_name = {o["name"]: o for o in db.list_orchestrations()}
    orch_data = orchestrations_by_name.get(ORCHESTRATION_NAME)
    if orch_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ORCHESTRATION_NAME!r} orchestration isn't seeded yet -- run app.scripts.seed_agents first",
        )
    orch = OrchestrationConfig(**orch_data)

    subscribed: Optional[List[str]] = None
    if user.sub.lower() not in RESERVED_USERNAMES:
        row = db.get_user_by_username(user.sub)
        subscribed = (row or {}).get("subscribed_agent_ids") or None

    if subscribed:
        filtered_ids = [aid for aid in orch.agent_ids if aid in set(subscribed)]
        orch = orch.model_copy(update={"agent_ids": filtered_ids})

    job = jobs.new_job("my_agents_run", owner=user.sub)
    job_id = job["job_id"]
    db.log_audit(user.sub, "me.run_report", "orchestration", orch_data["id"], {"job_id": job_id, "agent_count": len(orch.agent_ids)})

    async def _work():
        return await orchestration.run_orchestration(orch, body.input, job_id=job_id)

    asyncio.create_task(jobs.run_job(job_id, _work))
    return JobAccepted(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_my_job(job_id: str, user: TokenPayload = Depends(get_current_user)):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.get("owner") != user.sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")
    return job
