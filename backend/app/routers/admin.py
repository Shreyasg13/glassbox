"""Admin-gated CRUD for the Agent Factory (Phase 4) plus test-run,
orchestration-run, job polling, and provider health (Phase 5).

Phase 6: every mutation is rate-limited (rate_limit.py) and written to
the audit log (db.log_audit), and /api/admin/audit-log + /api/admin/llm-calls
expose that history + the LLM cost/latency log to the admin dashboard.

Prefix is /api/admin, not /admin -- the frontend's own /admin/* pages
(Agent Factory UI) live at that exact path, so under single-domain
path-based routing (see deploy/Caddyfile) a bare /admin prefix here
would collide with them. Joining the /api convention already used by
data.py/monte_carlo.py/tts.py sidesteps that.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, jobs, orchestration, snapshot_store
from ..auth import TokenPayload, require_admin
from ..models import (
    AgentConfig,
    AgentTestRunRequest,
    JobAccepted,
    JobStatus,
    OrchestrationConfig,
    OrchestrationRunRequest,
    PaginatedAuditLog,
    PaginatedLLMCalls,
    Provider,
    ProviderHealth,
)
from ..providers.factory import get_provider
from ..rate_limit import rate_limit_admin_mutations

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(rate_limit_admin_mutations)],
)


# ---- Agents ----

@router.get("/agents", response_model=List[AgentConfig])
async def list_agents():
    return db.list_agents()


@router.post("/agents", response_model=AgentConfig, status_code=201)
async def create_agent(agent: AgentConfig, user: TokenPayload = Depends(require_admin)):
    created = db.create_agent(agent.model_dump(exclude={"id"}))
    db.log_audit(user.sub, "agent.create", "agent", created["id"], {"name": created.get("name")})
    return created


@router.get("/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str):
    agent = db.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentConfig)
async def update_agent(agent_id: str, agent: AgentConfig, user: TokenPayload = Depends(require_admin)):
    updated = db.update_agent(agent_id, agent.model_dump(exclude={"id"}))
    if updated is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.log_audit(user.sub, "agent.update", "agent", agent_id, {"name": updated.get("name")})
    return updated


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, user: TokenPayload = Depends(require_admin)):
    if not db.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    db.log_audit(user.sub, "agent.delete", "agent", agent_id, {})


# ---- Orchestrations ----

@router.get("/orchestrations", response_model=List[OrchestrationConfig])
async def list_orchestrations():
    return db.list_orchestrations()


@router.post("/orchestrations", response_model=OrchestrationConfig, status_code=201)
async def create_orchestration(orch: OrchestrationConfig, user: TokenPayload = Depends(require_admin)):
    created = db.create_orchestration(orch.model_dump(exclude={"id"}))
    db.log_audit(user.sub, "orchestration.create", "orchestration", created["id"], {"name": created.get("name")})
    return created


@router.get("/orchestrations/{orch_id}", response_model=OrchestrationConfig)
async def get_orchestration(orch_id: str):
    orch = db.get_orchestration(orch_id)
    if orch is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return orch


@router.put("/orchestrations/{orch_id}", response_model=OrchestrationConfig)
async def update_orchestration(orch_id: str, orch: OrchestrationConfig, user: TokenPayload = Depends(require_admin)):
    updated = db.update_orchestration(orch_id, orch.model_dump(exclude={"id"}))
    if updated is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    db.log_audit(user.sub, "orchestration.update", "orchestration", orch_id, {"name": updated.get("name")})
    return updated


@router.delete("/orchestrations/{orch_id}", status_code=204)
async def delete_orchestration(orch_id: str, user: TokenPayload = Depends(require_admin)):
    if not db.delete_orchestration(orch_id):
        raise HTTPException(status_code=404, detail="Orchestration not found")
    db.log_audit(user.sub, "orchestration.delete", "orchestration", orch_id, {})


# ---- Test-run / orchestration-run (Phase 4/5) ----
#
# Both endpoints return immediately with a job id -- the actual agent/LLM
# work happens in a background task per PERFORMANCE_AND_ORCHESTRATION.md
# section 1 (never await an LLM call inline in a request handler).

@router.post("/agents/{agent_id}/test-run", response_model=JobAccepted, status_code=202)
async def test_run_agent(agent_id: str, body: AgentTestRunRequest, user: TokenPayload = Depends(require_admin)):
    agent_data = db.get_agent(agent_id)
    if agent_data is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = AgentConfig(**agent_data)
    job = jobs.new_job("agent_test_run")
    job_id = job["job_id"]
    db.log_audit(user.sub, "agent.test_run", "agent", agent_id, {"job_id": job_id})

    async def _work():
        return await orchestration.run_agent(agent, body.input, job_id=job_id)

    asyncio.create_task(jobs.run_job(job_id, _work))
    return JobAccepted(job_id=job_id)


@router.post("/orchestrations/{orch_id}/run", response_model=JobAccepted, status_code=202)
async def run_orchestration_endpoint(
    orch_id: str, body: OrchestrationRunRequest, user: TokenPayload = Depends(require_admin)
):
    orch_data = db.get_orchestration(orch_id)
    if orch_data is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    orch = OrchestrationConfig(**orch_data)
    job = jobs.new_job("orchestration_run")
    job_id = job["job_id"]
    db.log_audit(user.sub, "orchestration.run", "orchestration", orch_id, {"job_id": job_id})

    async def _work():
        return await orchestration.run_orchestration(orch, body.input, job_id=job_id)

    asyncio.create_task(jobs.run_job(job_id, _work))
    return JobAccepted(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---- Provider health (Phase 5) ----

@router.get("/providers/gemini/models")
async def gemini_models():
    """Why are Gemini calls failing? Compares the models agents are configured
    to use with the models this API key is actually offered, and shows which
    have recently 404'd and the free-tier ceilings we track."""
    from ..providers import gemini_quota
    from ..providers.factory import get_provider

    provider = get_provider("gemini")
    offered = await provider.available_models()
    configured = sorted(
        {
            m
            for a in db.list_agents()
            if a.get("provider") == "gemini"
            for m in [a.get("model"), *(a.get("fallback_models") or [])]
            if m
        }
    )
    return {
        "key_configured": bool(getattr(provider, "api_key", None)),
        "configured_models": configured,
        "offered_by_key": sorted(offered) if offered is not None else None,
        "configured_but_not_offered": [m for m in configured if offered is not None and m not in offered],
        "recently_404_retry_in_s": gemini_quota.unavailable_models(),
        "free_tier_ceilings": {m: {"rpm": r, "tpm": t, "rpd": d} for m, (r, t, d) in gemini_quota.GEMINI_LIMITS.items()},
    }


@router.get("/providers/health", response_model=List[ProviderHealth])
async def providers_health():
    from ..providers.factory import all_provider_names

    names: List[Provider] = all_provider_names()  # native + every OpenAI-compatible failover provider
    results = await asyncio.gather(*(get_provider(name).health_check() for name in names))
    return list(results)


class RoutingTestRequest(BaseModel):
    provider: Provider = "gemini"
    model: str = "gemini-2.5-flash-lite"
    prompt: str = Field(default="Reply with the single word: ready", max_length=500)


@router.get("/providers/routing")
async def routing_status(models: bool = False):
    """Failover routing: the order, which providers are configured (a key is all
    it takes), which are cooling down after a quota error and for how long, and
    where to get a free key for the rest."""
    from .. import llm_router

    return await llm_router.status(include_models=models)


@router.post("/providers/routing/test")
async def routing_test(body: RoutingTestRequest, user: TokenPayload = Depends(require_admin)):
    """Send one tiny prompt through the router and report which provider answered
    (or why every one failed). The quickest way to prove failover works."""
    from .. import llm_router

    try:
        r = await llm_router.complete_routed(body.provider, body.model, body.prompt, max_tokens=40, temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        tried = getattr(exc, "tried", [])
        db.log_audit(user.sub, "routing.test_failed", "provider", None, {"requested": body.provider})
        raise HTTPException(status_code=503, detail={"error": str(exc)[:300], "tried": tried}) from None
    db.log_audit(user.sub, "routing.test", "provider", None, {"requested": body.provider, "answered": r.provider})
    return {"ok": True, "answered_by": r.provider, "model": r.model, "failed_over": r.provider != body.provider, "reply": r.text[:120], "skipped_or_failed": r.tried}


# ---- Observability (Phase 6) ----

@router.get("/audit-log", response_model=PaginatedAuditLog)
async def audit_log(limit: int = 50, offset: int = 0):
    items, total = db.list_audit_log(limit=limit, offset=offset)
    return {"items": items, "total": total}


@router.get("/llm-calls", response_model=PaginatedLLMCalls)
async def llm_calls(limit: int = 50, offset: int = 0):
    items, total = db.list_llm_calls_page(limit=limit, offset=offset)
    return {"items": items, "total": total}


# ---- Snapshots (S3 T10) ----


class SnapshotListItem(BaseModel):
    id: str
    source: str
    ticker: str
    as_of: str
    fetched_at: str
    payload_hash: str


@router.get("/snapshots")
async def list_snapshots(source: Optional[str] = None, ticker: Optional[str] = None, limit: int = 50) -> List[SnapshotListItem]:
    """Metadata only (no payload) for the admin inspector."""
    items = snapshot_store.list(source=source, ticker=ticker, limit=limit)
    return [SnapshotListItem(**item) for item in items]


@router.get("/snapshots/{snap_id}")
async def get_snapshot(snap_id: str):
    """Full row including payload, for the admin detail view."""
    item = snapshot_store.get_by_id(snap_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return item
