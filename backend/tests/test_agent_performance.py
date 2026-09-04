"""Correctness of db.get_agent_performance()'s aggregation -- this
replaced a hardcoded 3-agent mock (data_source.AGENT_PERFORMANCE) with
real per-agent stats computed from the llm_calls log. db._list is
monkeypatched per-table (same approach as test_auth.py's db stubbing --
app/db.py binds its engine at import time and can't be redirected
per-test), so these tests exercise the actual aggregation logic against
controlled fixture data rather than a real database.
"""
from __future__ import annotations

from app import db


def _stub_lists(monkeypatch, agents, calls):
    def fake_list(table):
        if table is db.agents_table:
            return agents
        if table is db.llm_calls_table:
            return calls
        raise AssertionError(f"unexpected table in get_agent_performance: {table}")

    monkeypatch.setattr(db, "_list", fake_list)


def test_empty_llm_calls_returns_empty_list(monkeypatch):
    _stub_lists(monkeypatch, agents=[], calls=[])
    assert db.get_agent_performance() == []


def test_aggregates_call_count_and_success_rate(monkeypatch):
    agents = [{"id": "a1", "name": "Quant Strategist"}]
    calls = [
        {"agent_id": "a1", "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"},
        {"agent_id": "a1", "status": "ok", "duration_ms": 200, "started_at": "2026-01-02T00:00:00Z"},
        {"agent_id": "a1", "status": "error", "duration_ms": 50, "started_at": "2026-01-03T00:00:00Z"},
    ]
    _stub_lists(monkeypatch, agents, calls)

    [result] = db.get_agent_performance()
    assert result["name"] == "Quant Strategist"
    assert result["call_count"] == 3
    assert result["success_rate"] == round(100 * 2 / 3, 1)
    assert result["avg_duration_ms"] == round((100 + 200 + 50) / 3, 1)
    assert result["last_active_at"] == "2026-01-03T00:00:00Z"


def test_calls_with_no_agent_id_are_excluded(monkeypatch):
    """agent_id is Optional on LLMCallLog -- a call with no agent
    attribution (e.g. a report-narrative LLM call, not an agent test-run)
    must not silently show up under a fake "None" agent."""
    calls = [
        {"agent_id": None, "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"},
        {"agent_id": "a1", "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"},
    ]
    _stub_lists(monkeypatch, agents=[{"id": "a1", "name": "Quant Strategist"}], calls=calls)

    results = db.get_agent_performance()
    assert len(results) == 1
    assert results[0]["call_count"] == 1


def test_unknown_agent_id_falls_back_to_id_as_name(monkeypatch):
    """An agent that was since deleted (or a call logged before the
    agent config existed) shouldn't crash the aggregation -- fall back
    to the raw id rather than KeyError."""
    calls = [{"agent_id": "deleted-agent", "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"}]
    _stub_lists(monkeypatch, agents=[], calls=calls)

    [result] = db.get_agent_performance()
    assert result["name"] == "deleted-agent"


def test_missing_duration_excluded_from_average_not_treated_as_zero(monkeypatch):
    calls = [
        {"agent_id": "a1", "status": "ok", "duration_ms": None, "started_at": "2026-01-01T00:00:00Z"},
        {"agent_id": "a1", "status": "ok", "duration_ms": 200, "started_at": "2026-01-02T00:00:00Z"},
    ]
    _stub_lists(monkeypatch, agents=[{"id": "a1", "name": "Quant Strategist"}], calls=calls)

    [result] = db.get_agent_performance()
    assert result["avg_duration_ms"] == 200.0


def test_results_sorted_by_call_count_descending(monkeypatch):
    agents = [{"id": "a1", "name": "Agent One"}, {"id": "a2", "name": "Agent Two"}]
    calls = (
        [{"agent_id": "a1", "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"}] * 2
        + [{"agent_id": "a2", "status": "ok", "duration_ms": 100, "started_at": "2026-01-01T00:00:00Z"}] * 5
    )
    _stub_lists(monkeypatch, agents, calls)

    results = db.get_agent_performance()
    assert [r["name"] for r in results] == ["Agent Two", "Agent One"]
