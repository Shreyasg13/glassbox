"""routers/me.py correctness -- called as plain async functions
(FastAPI route handlers are regular functions under the decorator, so
this bypasses the DI/HTTP layer entirely) with db.* monkeypatched, same
approach test_auth.py already uses for app/db.py's import-time engine
binding. No TestClient anywhere in this test suite (checked before
adding this file) -- consistent with that existing convention rather
than introducing a second testing style for one router.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth
from app.models import AgentSubscriptions, OrchestrationRunRequest
from app.routers import me


def _admin_token():
    return auth.TokenPayload(sub="admin", role="admin")


def _viewer_token(username="shreyash"):
    return auth.TokenPayload(sub=username, role="viewer")


@pytest.fixture(autouse=True)
def _fake_db(monkeypatch):
    users: dict[str, dict] = {"shreyash": {"id": "u1", "username": "shreyash", "username_lower": "shreyash"}}
    agents = [
        {"id": "a1", "name": "Quant", "role": "Technical analysis", "type": "deterministic", "enabled": True},
        {"id": "a2", "name": "Risk", "role": "Risk management", "type": "deterministic", "enabled": True},
    ]
    audit_log: list[dict] = []

    def fake_get_user_by_username(username):
        return users.get(username.lower())

    def fake_update_user(user_id, patch):
        for row in users.values():
            if row["id"] == user_id:
                row.update(patch)
                return row
        return None

    def fake_list_agents():
        return agents

    def fake_log_audit(*args, **kwargs):
        audit_log.append((args, kwargs))

    monkeypatch.setattr(me.db, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(me.db, "update_user", fake_update_user)
    monkeypatch.setattr(me.db, "list_agents", fake_list_agents)
    monkeypatch.setattr(me.db, "log_audit", fake_log_audit)
    return {"users": users, "agents": agents, "audit_log": audit_log}


async def test_dev_account_cannot_set_subscriptions():
    with pytest.raises(HTTPException) as exc_info:
        await me.set_my_subscriptions(AgentSubscriptions(agent_ids=["a1"]), user=_admin_token())
    assert exc_info.value.status_code == 400


async def test_dev_account_subscriptions_read_as_empty():
    result = await me.get_my_subscriptions(user=_admin_token())
    assert result.agent_ids == []


async def test_real_user_can_set_valid_subscriptions(_fake_db):
    result = await me.set_my_subscriptions(AgentSubscriptions(agent_ids=["a1"]), user=_viewer_token())
    assert result.agent_ids == ["a1"]
    assert _fake_db["users"]["shreyash"]["subscribed_agent_ids"] == ["a1"]


async def test_unknown_agent_id_rejected(_fake_db):
    with pytest.raises(HTTPException) as exc_info:
        await me.set_my_subscriptions(AgentSubscriptions(agent_ids=["not-a-real-agent"]), user=_viewer_token())
    assert exc_info.value.status_code == 400


async def test_subscriptions_round_trip(_fake_db):
    await me.set_my_subscriptions(AgentSubscriptions(agent_ids=["a1", "a2"]), user=_viewer_token())
    result = await me.get_my_subscriptions(user=_viewer_token())
    assert result.agent_ids == ["a1", "a2"]


async def test_list_available_agents_returns_safe_fields(_fake_db):
    result = await me.list_available_agents(user=_viewer_token())
    assert len(result) == 2
    assert {a["id"] for a in result} == {"a1", "a2"}


async def test_get_my_job_rejects_non_owner(monkeypatch):
    monkeypatch.setattr(me.db, "get_job", lambda job_id: {"job_id": job_id, "owner": "someone-else", "status": "done"})
    with pytest.raises(HTTPException) as exc_info:
        await me.get_my_job("job-1", user=_viewer_token())
    assert exc_info.value.status_code == 403


async def test_get_my_job_returns_job_for_owner(monkeypatch):
    monkeypatch.setattr(
        me.db,
        "get_job",
        lambda job_id: {
            "job_id": job_id,
            "kind": "my_agents_run",
            "status": "done",
            "created_at": "2026-01-01T00:00:00Z",
            "owner": "shreyash",
        },
    )
    # Calling the handler directly (not through FastAPI's ASGI layer)
    # bypasses response_model serialization -- it returns the raw dict
    # db.get_job gave it, not a JobStatus instance.
    result = await me.get_my_job("job-1", user=_viewer_token())
    assert result["job_id"] == "job-1"


async def test_get_my_job_404s_for_unknown_job(monkeypatch):
    monkeypatch.setattr(me.db, "get_job", lambda job_id: None)
    with pytest.raises(HTTPException) as exc_info:
        await me.get_my_job("nope", user=_viewer_token())
    assert exc_info.value.status_code == 404


async def test_run_report_404s_when_orchestration_not_seeded(monkeypatch, _fake_db):
    monkeypatch.setattr(me.db, "list_orchestrations", lambda: [])
    with pytest.raises(HTTPException) as exc_info:
        await me.run_my_report(OrchestrationRunRequest(input=None), user=_viewer_token())
    assert exc_info.value.status_code == 404


def _stub_orchestration_and_capture_task(monkeypatch, captured):
    """run_my_report fires the actual work via asyncio.create_task
    (fire-and-forget by design -- the endpoint returns immediately with
    a job id), so awaiting run_my_report() alone doesn't guarantee the
    scheduled task has run yet by the time a test asserts on it. Capture
    the coroutine instead of letting create_task schedule it, so the
    test can await it deterministically instead of racing the event
    loop."""
    monkeypatch.setattr(me.db, "log_audit", lambda *a, **k: None)

    async def fake_run_orchestration(orch, input, *, job_id=None, allow_failover=True):
        captured["agent_ids"] = orch.agent_ids
        captured["allow_failover"] = allow_failover
        return {"mode": orch.mode, "agents": []}

    monkeypatch.setattr(me.orchestration, "run_orchestration", fake_run_orchestration)

    created = []
    monkeypatch.setattr(me.asyncio, "create_task", lambda coro: created.append(coro))
    return created


async def test_run_report_filters_to_subscribed_agents(monkeypatch, _fake_db):
    """The core promise of this feature: only the caller's subscribed
    agents actually run."""
    _fake_db["users"]["shreyash"]["subscribed_agent_ids"] = ["a1"]
    monkeypatch.setattr(
        me.db,
        "list_orchestrations",
        lambda: [
            {
                "id": "orch1",
                "name": me.ORCHESTRATION_NAME,
                "mode": "committee_vote",
                "agent_ids": ["a1", "a2"],
                "coordinator": "vn_engine",
            }
        ],
    )
    captured: dict = {}
    created = _stub_orchestration_and_capture_task(monkeypatch, captured)

    await me.run_my_report(OrchestrationRunRequest(input=None), user=_viewer_token())
    await created[0]
    assert captured["agent_ids"] == ["a1"]


def _fake_signal(symbol="AAPL"):
    return {
        "symbol": symbol,
        "name": "Apple Inc.",
        "sector": "Technology",
        "current_price": 190.12,
        "signal": "BUY",
        "confidence": 72.0,
        "rsi": 28.4,
        "ma_cross": "BULLISH",
        "volume_ratio": 1.3,
        "suggested_weight": 10.0,
        "fast_ma": 20,
        "slow_ma": 50,
        "test_sharpe": 1.1,
        "win_rate": 55.0,
        "data_date": "2026-09-05",
    }


@pytest.fixture(autouse=True)
def _fake_live_signals(monkeypatch):
    monkeypatch.setattr(me.ds, "get_live_signals", lambda: {"signals": [_fake_signal()]})
    monkeypatch.setattr(me.ds, "STOCK_INFO", {"AAPL": {}})


async def test_dev_account_entitlements_show_unlimited_style_full_quota():
    result = await me.get_my_entitlements(user=_admin_token())
    assert result.limit == me.FREE_VERIFIED_SIGNAL_LIMIT
    assert result.remaining == me.FREE_VERIFIED_SIGNAL_LIMIT


async def test_real_user_entitlements_start_at_full_quota(_fake_db):
    result = await me.get_my_entitlements(user=_viewer_token())
    assert result.used == 0
    assert result.remaining == me.FREE_VERIFIED_SIGNAL_LIMIT


async def test_verify_ticker_decrements_real_users_quota(_fake_db):
    result = await me.verify_ticker("aapl", user=_viewer_token())
    assert result.signal.symbol == "AAPL"
    assert result.entitlements.used == 1
    assert result.entitlements.remaining == me.FREE_VERIFIED_SIGNAL_LIMIT - 1
    assert _fake_db["users"]["shreyash"]["verified_signal_count"] == 1


async def test_verify_ticker_blocks_at_quota(_fake_db):
    _fake_db["users"]["shreyash"]["verified_signal_count"] = me.FREE_VERIFIED_SIGNAL_LIMIT
    with pytest.raises(HTTPException) as exc_info:
        await me.verify_ticker("AAPL", user=_viewer_token())
    assert exc_info.value.status_code == 402


async def test_verify_ticker_never_decrements_dev_accounts(_fake_db):
    result = await me.verify_ticker("AAPL", user=_admin_token())
    assert result.entitlements.remaining == me.FREE_VERIFIED_SIGNAL_LIMIT
    assert "verified_signal_count" not in _fake_db["users"]["shreyash"]


async def test_verify_ticker_404s_for_unknown_symbol(_fake_db):
    with pytest.raises(HTTPException) as exc_info:
        await me.verify_ticker("NOTASYMBOL", user=_viewer_token())
    assert exc_info.value.status_code == 404


async def test_run_report_falls_back_to_full_list_when_no_subscription(monkeypatch, _fake_db):
    """No subscription set (every dev account, and any real account
    that hasn't visited the subscriptions page) means "everyone runs",
    not "nobody runs" -- must not silently degrade to an empty
    committee just because a preference was never configured."""
    monkeypatch.setattr(
        me.db,
        "list_orchestrations",
        lambda: [
            {
                "id": "orch1",
                "name": me.ORCHESTRATION_NAME,
                "mode": "committee_vote",
                "agent_ids": ["a1", "a2"],
                "coordinator": "vn_engine",
            }
        ],
    )
    captured: dict = {}
    created = _stub_orchestration_and_capture_task(monkeypatch, captured)

    await me.run_my_report(OrchestrationRunRequest(input=None), user=_viewer_token())
    await created[0]
    assert captured["agent_ids"] == ["a1", "a2"]
