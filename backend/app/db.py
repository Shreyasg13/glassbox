"""SQLAlchemy Core storage for the Agent Factory (Phase 4).

SQLite by default (file at backend/app/glassbox.db, or GLASSBOX_DB_PATH).
Set DATABASE_URL directly (e.g. Neon's "postgresql+psycopg://..." connection
string) to run against Postgres instead -- plain SQLAlchemy Core throughout,
JSON stored as text columns rather than SQLite-specific JSON1 functions, so
no query changes are needed either way. connect_args differs per dialect:
SQLite's check_same_thread=False lets the same connection be reused across
the threadpool FastAPI dispatches sync endpoints on; Postgres needs no such
override and Neon requires TLS, so sslmode=require is added if the caller's
DATABASE_URL didn't already specify one.

pool_pre_ping=True on the Postgres branch is not a defensive guess -- it
fixes a real failure hit during the first live Google OAuth test after
this app's Neon cutover: the backend sat idle for a few minutes, Neon's
pooled (PgBouncer) endpoint silently closed the backend connection on
its side, and the next query through SQLAlchemy's pool (which still
considered that connection valid) failed with
`psycopg.OperationalError: consuming input failed: SSL connection has
been closed unexpectedly` -- a 500 on an otherwise-correct request, not
an OAuth bug. pre_ping issues a cheap liveness check before handing out
a pooled connection and transparently reconnects on failure instead of
surfacing it to the caller -- SQLAlchemy's own documented fix for
exactly this class of problem (docs.sqlalchemy.org/en/20/core/pooling.html
-> "Disconnect Handling - Pessimistic"). pool_recycle=280 additionally
retires any connection older than that outright, comfortably under
Neon's own pooled-connection idle window, as a second line of defense
pre_ping alone doesn't cover (a connection can go stale between pings).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Column, String, Boolean, create_engine, MetaData, Table, select, delete, update, insert
from sqlalchemy.engine import make_url

DB_PATH = Path(os.environ.get("GLASSBOX_DB_PATH", str(Path(__file__).parent / "glassbox.db")))
_env_url = os.environ.get("DATABASE_URL")
DATABASE_URL = _env_url if _env_url else f"sqlite:///{DB_PATH}"


def build_engine(database_url: str):
    """Extracted from module scope so the dialect-branching logic can be
    exercised directly in tests (app/db.py's engine otherwise binds at
    import time -- see test_auth.py's docstring -- so this is the one
    piece of that logic worth making independently testable)."""
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    url = make_url(database_url)
    if "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"})
    return create_engine(url, pool_pre_ping=True, pool_recycle=280)


engine = build_engine(DATABASE_URL)
metadata = MetaData()

agents_table = Table(
    "agents",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded AgentConfig
)

orchestrations_table = Table(
    "orchestrations",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded OrchestrationConfig
)

jobs_table = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded job dict (see jobs.py)
)

llm_calls_table = Table(
    "llm_calls",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded LLMCallLog
)

report_narratives_table = Table(
    "report_narratives",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded DailyReportNarrative
)

audit_log_table = Table(
    "audit_log",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded AuditLogEntry
)

users_table = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("config", String, nullable=False),  # JSON-encoded: username, username_lower, password_hash, role, created_at
)

metadata.create_all(engine)


def _list(table: Table) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(select(table)).fetchall()
        return [json.loads(row.config) for row in rows]


def _get(table: Table, item_id: str) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(select(table).where(table.c.id == item_id)).fetchone()
        return json.loads(row.config) if row else None


def _create(table: Table, data: Dict[str, Any]) -> Dict[str, Any]:
    new_id = data.get("id") or str(uuid.uuid4())
    data["id"] = new_id
    with engine.begin() as conn:
        conn.execute(insert(table).values(id=new_id, config=json.dumps(data)))
    return data


def _update(table: Table, item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data["id"] = item_id
    with engine.begin() as conn:
        result = conn.execute(update(table).where(table.c.id == item_id).values(config=json.dumps(data)))
        if result.rowcount == 0:
            return None
    return data


def _delete(table: Table, item_id: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(delete(table).where(table.c.id == item_id))
        return result.rowcount > 0


def list_agents() -> List[Dict[str, Any]]:
    return _list(agents_table)


def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    return _get(agents_table, agent_id)


def create_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(agents_table, data)


def update_agent(agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _update(agents_table, agent_id, data)


def delete_agent(agent_id: str) -> bool:
    return _delete(agents_table, agent_id)


def list_orchestrations() -> List[Dict[str, Any]]:
    return _list(orchestrations_table)


def get_orchestration(orch_id: str) -> Optional[Dict[str, Any]]:
    return _get(orchestrations_table, orch_id)


def create_orchestration(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(orchestrations_table, data)


def update_orchestration(orch_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _update(orchestrations_table, orch_id, data)


def delete_orchestration(orch_id: str) -> bool:
    return _delete(orchestrations_table, orch_id)


# ---- Jobs (Phase 4/5 background runs) ----

def create_job(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(jobs_table, data)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _get(jobs_table, job_id)


def update_job(job_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Merge `patch` over the existing row so partial updates (e.g. just
    `status`) don't clobber fields written earlier (e.g. `created_at`)."""
    existing = get_job(job_id) or {}
    existing.update(patch)
    return _update(jobs_table, job_id, existing)


# ---- LLM call log (Phase 5 cost/latency observability) ----

def create_llm_call(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(llm_calls_table, data)


def update_llm_call(call_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = _get(llm_calls_table, call_id) or {}
    existing.update(patch)
    return _update(llm_calls_table, call_id, existing)


def list_llm_calls() -> List[Dict[str, Any]]:
    return _list(llm_calls_table)


def get_agent_performance() -> List[Dict[str, Any]]:
    """Real per-agent call stats aggregated from llm_calls -- replaces
    an earlier hardcoded 3-agent mock at this same call site
    (data_source.AGENT_PERFORMANCE). Deliberately only exposes call
    volume/reliability/latency, not a trading win-rate: this system
    doesn't link a past signal to its later real-world outcome, so a
    "win_rate" field would either be fabricated or require a genuinely
    separate feature (see docs/PROJECT_STATUS.md's roadmap) -- reporting
    a number we don't actually have would be worse than not having it.

    Public endpoint (routers/data.py, no auth) -- deliberately excludes
    estimated_cost_usd and error detail, which stay admin-only via the
    existing /api/admin/llm-calls, so this stays safe to expose without
    leaking real operational cost/error internals to unauthenticated
    visitors.
    """
    agent_names = {a["id"]: a.get("name", a["id"]) for a in _list(agents_table)}
    calls = _list(llm_calls_table)

    by_agent: Dict[str, List[Dict[str, Any]]] = {}
    for call in calls:
        agent_id = call.get("agent_id")
        if not agent_id:
            continue
        by_agent.setdefault(agent_id, []).append(call)

    results = []
    for agent_id, agent_calls in by_agent.items():
        total = len(agent_calls)
        ok_count = sum(1 for c in agent_calls if c.get("status") == "ok")
        durations = [c["duration_ms"] for c in agent_calls if c.get("duration_ms") is not None]
        started_ats = [c["started_at"] for c in agent_calls if c.get("started_at")]
        results.append(
            {
                "name": agent_names.get(agent_id, agent_id),
                "call_count": total,
                "success_rate": round(100 * ok_count / total, 1) if total else 0.0,
                "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else None,
                "last_active_at": max(started_ats) if started_ats else None,
            }
        )
    results.sort(key=lambda r: r["call_count"], reverse=True)
    return results


# ---- Daily report narratives (Phase 5) ----

def create_report_narrative(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(report_narratives_table, data)


def get_report_narrative(narrative_id: str) -> Optional[Dict[str, Any]]:
    return _get(report_narratives_table, narrative_id)


def list_report_narratives() -> List[Dict[str, Any]]:
    return _list(report_narratives_table)


# ---- Pagination + audit log (Phase 6) ----
#
# Tables here store one JSON blob per row rather than typed columns (the
# pattern already used throughout this file), so "order by timestamp,
# then page" is done in Python rather than pushed to SQL. At this
# deployment's scale (a single dev SQLite file) that's simpler and more
# obviously correct than a partial ORDER BY over a JSON column.

def _list_paginated_sorted(table: Table, limit: int, offset: int, sort_key: str) -> Tuple[List[Dict[str, Any]], int]:
    items = _list(table)
    items.sort(key=lambda x: x.get(sort_key, ""), reverse=True)
    total = len(items)
    return items[offset : offset + limit], total


def log_audit(
    actor: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4()),
        "actor": actor,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "detail": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return _create(audit_log_table, entry)


def list_audit_log(limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    return _list_paginated_sorted(audit_log_table, limit, offset, "created_at")


def list_llm_calls_page(limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    return _list_paginated_sorted(llm_calls_table, limit, offset, "started_at")


# ---- Users (real signup/login accounts, distinct from the hardcoded dev
# accounts in app/auth.py's _DEV_USERS -- see that module for how the two
# are reconciled at authentication time) ----

def list_users() -> List[Dict[str, Any]]:
    return _list(users_table)


def create_user(data: Dict[str, Any]) -> Dict[str, Any]:
    return _create(users_table, data)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Case-insensitive lookup -- every row's config carries a
    pre-lowercased `username_lower` field precisely so this can be a
    linear scan without needing a second indexed column at the SQL layer
    (consistent with this file's existing JSON-blob-per-row pattern)."""
    target = username.strip().lower()
    for row in _list(users_table):
        if row.get("username_lower") == target:
            return row
    return None


def get_user_by_oauth(provider: str, subject: str) -> Optional[Dict[str, Any]]:
    """Identity for OAuth accounts is keyed on (provider, subject) --
    the provider's own stable user id -- not on email/username, since
    those can change; see auth.oauth_login for how a username is picked
    on first login."""
    for row in _list(users_table):
        if row.get("oauth_provider") == provider and row.get("oauth_subject") == subject:
            return row
    return None
