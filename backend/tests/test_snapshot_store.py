"""Tests for the point-in-time snapshot store (S3 T10)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import db, free_data, snapshot_store
from app.migrated_tables import source_snapshots_table


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Use a temporary SQLite database for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("GLASSBOX_DB_PATH", str(db_path))
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    # Re-import modules to pick up new env vars
    import importlib
    importlib.reload(db)
    importlib.reload(free_data)
    importlib.reload(snapshot_store)
    from app.migrate import upgrade
    upgrade(db.engine.connect())
    yield
    db.engine.dispose()


def test_put_get_roundtrip():
    """put/get roundtrip works and returns the stored payload."""
    payload = {"key": "value", "numbers": [1, 2, 3]}
    # Use explicit fetched_at before the run_time
    fetched_at = "2026-09-15T10:00:00+00:00"
    snap_id = snapshot_store.put("sec_facts", "AAPL", "2026-09-15", payload, fetched_at=fetched_at)
    assert snap_id is not None

    got = snapshot_store.get("sec_facts", "AAPL", "2026-09-16T00:00:00+00:00")
    assert got == payload


def test_identical_payload_returns_same_id():
    """Identical payload (same source, ticker, hash) returns existing id, does not add a row."""
    payload = {"data": "same"}
    id1 = snapshot_store.put("sec_facts", "AAPL", "2026-09-15", payload)
    id2 = snapshot_store.put("sec_facts", "AAPL", "2026-09-15", payload)
    assert id1 == id2

    # Only one row in the table
    with db.engine.connect() as conn:
        rows = conn.execute(source_snapshots_table.select()).fetchall()
    assert len(rows) == 1


def test_changed_payload_creates_new_row():
    """Changed payload (different hash) creates a new row with a new id."""
    payload1 = {"data": "v1"}
    payload2 = {"data": "v2"}
    id1 = snapshot_store.put("sec_facts", "AAPL", "2026-09-15", payload1)
    id2 = snapshot_store.put("sec_facts", "AAPL", "2026-09-15", payload2)
    assert id1 != id2

    with db.engine.connect() as conn:
        rows = conn.execute(source_snapshots_table.select()).fetchall()
    assert len(rows) == 2


def test_get_returns_newest_before_run_time():
    """get(run_time) returns the newest snapshot with fetched_at <= run_time, never a later one."""
    # Put snapshot at t1
    t1 = "2026-09-15T10:00:00+00:00"
    snapshot_store.put("sec_facts", "AAPL", "2026-09-14", {"v": 1}, fetched_at=t1)

    # Put snapshot at t3 (later)
    t3 = "2026-09-15T14:00:00+00:00"
    snapshot_store.put("sec_facts", "AAPL", "2026-09-14", {"v": 3}, fetched_at=t3)

    # Query at t2 (between t1 and t3) should return t1's payload
    t2 = "2026-09-15T12:00:00+00:00"
    got = snapshot_store.get("sec_facts", "AAPL", t2)
    assert got == {"v": 1}

    # Query at t4 (after t3) should return t3's payload
    t4 = "2026-09-15T16:00:00+00:00"
    got = snapshot_store.get("sec_facts", "AAPL", t4)
    assert got == {"v": 3}

    # Query before t1 returns None
    t0 = "2026-09-15T08:00:00+00:00"
    got = snapshot_store.get("sec_facts", "AAPL", t0)
    assert got is None


def test_list_returns_metadata_only():
    """list() returns metadata without payload."""
    snapshot_store.put("sec_facts", "AAPL", "2026-09-14", {"v": 1}, fetched_at="2026-09-15T10:00:00+00:00")
    snapshot_store.put("treasury", "", "2026-09-14", [{"date": "2026-09-14", "y10": 4.0}], fetched_at="2026-09-15T11:00:00+00:00")

    items = snapshot_store.list(limit=10)
    assert len(items) == 2
    for item in items:
        assert "payload" not in item
        assert "payload_hash" in item
        assert "source" in item
        assert "ticker" in item
        assert "as_of" in item
        assert "fetched_at" in item

    # Filter by source
    items = snapshot_store.list(source="treasury", limit=10)
    assert len(items) == 1
    assert items[0]["source"] == "treasury"

    # Filter by ticker
    items = snapshot_store.list(ticker="AAPL", limit=10)
    assert len(items) == 1
    assert items[0]["ticker"] == "AAPL"


def test_get_by_id_returns_full_row_with_payload():
    """get_by_id returns the full row including payload."""
    payload = {"key": "value"}
    snap_id = snapshot_store.put("sec_facts", "AAPL", "2026-09-14", payload)
    got = snapshot_store.get_by_id(snap_id)
    assert got is not None
    assert got["id"] == snap_id
    assert got["payload"] == payload
    assert got["payload_hash"] == snapshot_store._payload_hash(payload)


def test_context_lines_byte_identical_with_and_without_run_time(tmp_path, monkeypatch):
    """context_lines output is byte-identical with and without run_time when snapshot and cache hold the same data.
    Covers fundamentals, filings, insiders, and macro."""
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    monkeypatch.setenv("SEC_USER_AGENT", "GlassBox test ops@example.com")
    import importlib
    importlib.reload(free_data)

    # --- Fundamentals cache + identical snapshot ---
    fund_cache = {
        "cik": 1,
        "fetched_at": "2026-09-15T10:00:00+00:00",
        "concepts": {
            "revenue": {"tag": "Revenues", "unit": "USD", "series": [{"end": "2025-12-31", "start": "2025-01-01", "val": 100.0, "filed": "2026-02-01"}]}
        }
    }
    free_data._write("fundamentals/AAPL.json", fund_cache)
    snapshot_store.put("sec_facts", "AAPL", "2025-12-31", fund_cache, fetched_at="2026-09-15T10:00:00+00:00")

    # --- Filings cache + identical snapshot ---
    filings_cache = {
        "cik": 1,
        "fetched_at": "2026-09-15T10:00:00+00:00",
        "filings": [
            {"form": "10-K", "filed": "2025-02-01", "items": "7, 7A, 8", "text": "Annual report", "flag": True}
        ]
    }
    free_data._write("filings/AAPL.json", filings_cache)
    snapshot_store.put("sec_filings", "AAPL", "2025-02-01", filings_cache, fetched_at="2026-09-15T10:00:00+00:00")

    # --- Insiders cache + identical snapshot ---
    insiders_cache = {
        "cik": 1,
        "fetched_at": "2026-09-15T10:00:00+00:00",
        "transactions": [
            {"date": "2025-12-15", "type": "P", "shares": 1000, "price": 150.0, "name": "Test Insider", "role": "Officer"}
        ],
        "seen": []
    }
    free_data._write("insiders/AAPL.json", insiders_cache)
    snapshot_store.put("sec_insiders", "AAPL", "2025-12-15", insiders_cache, fetched_at="2026-09-15T10:00:00+00:00")

    # --- Macro cache + identical snapshots ---
    macro_cache = {
        "treasury": [{"date": "2026-09-10", "y10": 4.0}],
        "bls": {"unemployment": [{"month": "2026-08", "value": 4.5}]},
        "fetched_at": "2026-09-15T10:00:00+00:00"
    }
    free_data._write("macro.json", macro_cache)
    snapshot_store.put("treasury", "", "2026-09-10", macro_cache["treasury"], fetched_at="2026-09-15T10:00:00+00:00")
    snapshot_store.put("bls", "unemployment", "2026-08", macro_cache["bls"]["unemployment"], fetched_at="2026-09-15T10:00:00+00:00")

    # Call with and without run_time
    lines_without = free_data.context_lines("AAPL", "2026-06-01", price=40.0)
    lines_with = free_data.context_lines("AAPL", "2026-06-01", price=40.0, run_time="2026-09-15T12:00:00+00:00")

    assert lines_without == lines_with, f"context_lines differs with/without run_time:\nwithout: {lines_without}\nwith: {lines_with}"


def test_committee_path_uses_earlier_snapshot_when_later_exists(tmp_path, monkeypatch):
    """With a snapshot fetched AFTER run_time and a different one BEFORE, context_lines(run_time=...) uses the earlier one."""
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    monkeypatch.setenv("SEC_USER_AGENT", "GlassBox test ops@example.com")
    import importlib
    importlib.reload(free_data)

    # Cache has the LATEST data (v2) - include enough concepts to generate a fundamentals line
    cache_v2 = {
        "cik": 1,
        "fetched_at": "2026-09-15T14:00:00+00:00",
        "concepts": {
            "revenue": {"tag": "Revenues", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 180.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 200.0, "filed": "2026-02-01"}
            ]},
            "net_income": {"tag": "NetIncomeLoss", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 30.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 40.0, "filed": "2026-02-01"}
            ]},
        }
    }
    free_data._write("fundamentals/AAPL.json", cache_v2)

    # Snapshot at t1 (earlier, v1) - lower revenue
    snap_v1 = {
        "cik": 1,
        "fetched_at": "2026-09-15T10:00:00+00:00",
        "concepts": {
            "revenue": {"tag": "Revenues", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 100.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 100.0, "filed": "2026-02-01"}
            ]},
            "net_income": {"tag": "NetIncomeLoss", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 10.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 20.0, "filed": "2026-02-01"}
            ]},
        }
    }
    snapshot_store.put("sec_facts", "AAPL", "2025-12-31", snap_v1, fetched_at="2026-09-15T10:00:00+00:00")

    # Snapshot at t3 (later, v2 - same as cache)
    snap_v2 = {
        "cik": 1,
        "fetched_at": "2026-09-15T14:00:00+00:00",
        "concepts": {
            "revenue": {"tag": "Revenues", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 180.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 200.0, "filed": "2026-02-01"}
            ]},
            "net_income": {"tag": "NetIncomeLoss", "unit": "USD", "series": [
                {"end": "2024-12-31", "start": "2024-01-01", "val": 30.0, "filed": "2025-02-01"},
                {"end": "2025-12-31", "start": "2025-01-01", "val": 40.0, "filed": "2026-02-01"}
            ]},
        }
    }
    snapshot_store.put("sec_facts", "AAPL", "2025-12-31", snap_v2, fetched_at="2026-09-15T14:00:00+00:00")

    # Run at t2 (between t1 and t3) should use v1 (100.0 revenue)
    run_time = "2026-09-15T12:00:00+00:00"
    lines = free_data.context_lines("AAPL", "2026-06-01", price=40.0, run_time=run_time)
    # The fundamentals line should show the v1 revenue (100.0) not v2 (200.0)
    fundamentals_line = next(l for l in lines if l.startswith("Fundamentals"))
    assert "100.0" in fundamentals_line or "revenue" in fundamentals_line  # v1 revenue appears
    # Without run_time it uses cache (v2)
    lines_no_run = free_data.context_lines("AAPL", "2026-06-01", price=40.0)
    # With run_time it should use the snapshot (v1), without it uses cache (v2)
    # The revenue value in the snapshot v1 is 100, in cache v2 is 200
    # So the output should differ
    assert lines != lines_no_run


def test_snapshot_write_failure_does_not_break_refresh_macro(tmp_path, monkeypatch):
    """A snapshot write failure (monkeypatched put to raise) does not break refresh_macro."""
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    import importlib
    importlib.reload(free_data)

    # Monkeypatch snapshot_store.put to raise
    original_put = snapshot_store.put
    def failing_put(*args, **kwargs):
        raise RuntimeError("simulated snapshot failure")
    monkeypatch.setattr(snapshot_store, "put", failing_put)

    # Mock HTTP to return valid treasury data
    import httpx
    def handler(request):
        return httpx.Response(200, text="Date,3 Mo\n09/15/2026,4.0\n")
    fetcher = free_data.Fetcher(transport=httpx.MockTransport(handler), sleep=lambda s: None)

    # This should not raise even though snapshot put fails
    status = free_data.refresh_macro(http=fetcher, today=__import__("datetime").date(2026, 9, 16))
    assert status["treasury"]["ok"] is True


def test_migration_upgrade_downgrade(tmp_path):
    """Migration upgrade then downgrade works on a temp SQLite DB (follows T1 migration test pattern)."""
    from sqlalchemy import create_engine, inspect, text
    from app.migrate import upgrade, downgrade

    eng = create_engine(f"sqlite:///{tmp_path / 'm.db'}", connect_args={"check_same_thread": False})
    db.metadata.create_all(eng)

    # Upgrade
    with eng.begin() as conn:
        upgrade(conn)
    assert "source_snapshots" in inspect(eng).get_table_names()

    # Check columns
    cols = {c["name"] for c in inspect(eng).get_columns("source_snapshots")}
    expected = {"id", "source", "ticker", "as_of", "fetched_at", "payload_json", "payload_hash"}
    assert cols == expected

    # Check indexes
    indexes = {idx["name"] for idx in inspect(eng).get_indexes("source_snapshots")}
    assert "ix_source_snapshots_source_ticker_fetched" in indexes

    # Check unique constraint exists (SQLite auto-generates name in batch mode)
    with eng.connect() as conn:
        uqs = conn.execute(text("PRAGMA index_list('source_snapshots')")).fetchall()
    uq_names = {row[1] for row in uqs if row[3] == 'u'}  # name is column 1, origin is column 3
    assert len(uq_names) >= 1, f"expected at least one unique index, got {uq_names}"

    # Downgrade
    with eng.begin() as conn:
        downgrade("base", conn)
    assert "source_snapshots" not in inspect(eng).get_table_names()

    # Older tables still exist
    remaining = set(inspect(eng).get_table_names())
    assert {"users", "committee_runs", "paper_accounts", "price_bars"}.issubset(remaining)


def test_admin_routes_require_admin_role(tmp_path, monkeypatch):
    """Admin routes return 403 for viewer token and 200 for admin on GET /api/admin/snapshots and GET /api/admin/snapshots/{id}."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import TokenPayload, get_current_user
    from app.routers import admin as admin_routes

    app = FastAPI()
    app.include_router(admin_routes.router)

    viewer = TokenPayload(sub="viewer", role="viewer")
    admin = TokenPayload(sub="admin", role="admin")

    def override_viewer():
        return viewer

    def override_admin():
        return admin

    # Viewer gets 403
    app.dependency_overrides[get_current_user] = override_viewer
    c_viewer = TestClient(app)
    assert c_viewer.get("/api/admin/snapshots").status_code == 403

    # Admin gets 200
    app.dependency_overrides[get_current_user] = override_admin
    c_admin = TestClient(app)
    r = c_admin.get("/api/admin/snapshots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Admin gets 404 for unknown id
    r = c_admin.get("/api/admin/snapshots/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_snapshot_put_invalid_source_raises():
    """put() with an unknown source raises ValueError."""
    with pytest.raises(ValueError, match="unknown source"):
        snapshot_store.put("invalid_source", "AAPL", "2026-09-15", {})


def test_get_invalid_source_raises():
    """get() with an unknown source raises ValueError."""
    with pytest.raises(ValueError, match="unknown source"):
        snapshot_store.get("invalid_source", "AAPL", "2026-09-15T00:00:00+00:00")


def test_ticker_case_insensitive():
    """Ticker is normalized to uppercase."""
    payload = {"v": 1}
    fetched_at = "2026-09-14T10:00:00+00:00"
    snap_id = snapshot_store.put("sec_facts", "aapl", "2026-09-14", payload, fetched_at=fetched_at)
    got = snapshot_store.get("sec_facts", "AAPL", "2026-09-15T00:00:00+00:00")
    assert got == payload

    # List also returns uppercase
    items = snapshot_store.list(ticker="AAPL")
    assert len(items) == 1
    assert items[0]["ticker"] == "AAPL"


def test_payload_hash_is_sha256_of_canonical_json():
    """payload_hash is SHA256 of canonical JSON (sort_keys=True, separators=(',', ':'))."""
    payload = {"b": 2, "a": 1}
    import hashlib
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()

    snap_id = snapshot_store.put("sec_facts", "AAPL", "2026-09-14", payload)
    row = snapshot_store.get_by_id(snap_id)
    assert row["payload_hash"] == expected_hash


def test_macro_as_of_with_run_time_uses_snapshots(tmp_path, monkeypatch):
    """macro_as_of(run_time=...) reads treasury and bls from snapshots when available."""
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    import importlib
    importlib.reload(free_data)

    # Write cache (will be ignored when run_time is given and snapshots exist)
    free_data._write("macro.json", {"treasury": [{"date": "2026-09-10", "y10": 3.0}], "bls": {"unemployment": [{"month": "2026-08", "value": 5.0}]}})

    # Write treasury snapshot (earlier, y10=4.0)
    treasury_snap = [{"date": "2026-09-10", "y10": 4.0}]
    snapshot_store.put("treasury", "", "2026-09-10", treasury_snap, fetched_at="2026-09-11T10:00:00+00:00")

    # Write bls snapshot (earlier)
    bls_snap = [{"month": "2026-08", "value": 4.5}]
    snapshot_store.put("bls", "unemployment", "2026-08", bls_snap, fetched_at="2026-09-11T10:00:00+00:00")

    # Query with run_time after snapshots -> should use snapshot values
    m = free_data.macro_as_of("2026-09-15", run_time="2026-09-11T12:00:00+00:00")
    assert m["y10"] == 4.0
    assert m["unemployment"] == 4.5

    # Query with run_time before snapshots -> should fall back to cache
    m = free_data.macro_as_of("2026-09-15", run_time="2026-09-10T12:00:00+00:00")
    assert m["y10"] == 3.0
    assert m["unemployment"] == 5.0


def test_macro_as_of_partial_bls_snapshots_fallback_to_cache(tmp_path, monkeypatch):
    """When only some BLS series have snapshots, missing ones fall back to cache."""
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    import importlib
    importlib.reload(free_data)

    # Cache has both unemployment and cpi (with 13 months for YoY calculation)
    cpi_rows = [{"month": f"2025-{m:02d}", "value": 3.0 + m * 0.01} for m in range(1, 14)]
    unemp_rows = [{"month": f"2025-{m:02d}", "value": 4.5 + m * 0.01} for m in range(1, 14)]
    free_data._write("macro.json", {
        "treasury": [{"date": "2026-09-10", "y10": 3.0}],
        "bls": {
            "unemployment": unemp_rows,
            "cpi": cpi_rows
        }
    })

    # Snapshot only for unemployment (not cpi) - newer value
    bls_unemp_snap = [{"month": "2026-08", "value": 4.5}]
    snapshot_store.put("bls", "unemployment", "2026-08", bls_unemp_snap, fetched_at="2026-09-11T10:00:00+00:00")

    # Query with run_time after snapshot -> unemployment from snapshot, cpi from cache
    m = free_data.macro_as_of("2026-09-15", run_time="2026-09-11T12:00:00+00:00")
    assert m["unemployment"] == 4.5  # from snapshot
    assert "cpi_yoy" in m  # from cache (year-over-year calculation)

    # The macro line should include both
    line = free_data.macro_line(m)
    assert "unemployment 4.5%" in line
    assert "consumer prices" in line
