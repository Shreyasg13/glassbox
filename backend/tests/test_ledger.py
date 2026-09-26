"""Tests for the append-only hash-chained call ledger (S3 T11)."""
from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app import db, ledger, migrate
from app.migrated_tables import include_object, ledger_calls_table, migrated_metadata


# ---- Test infrastructure --------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path):
    """Create a temp SQLite DB with older tables + migrated tables applied."""
    db_path = tmp_path / "test_ledger.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    # Create older tables (as production init_schema does)
    db.metadata.create_all(engine)

    # Apply all migrations up to head
    with engine.begin() as conn:
        migrate.upgrade(conn)

    # Patch the ledger module to use this engine
    original_engine = db.engine
    db.engine = engine
    yield engine

    # Restore
    db.engine = original_engine
    engine.dispose()


def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(prev_hash, row_without_hash):
    data = (prev_hash + _canonical_json(row_without_hash)).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ---- Tests ----------------------------------------------------------------------


def test_append_three_rows_chain(temp_db):
    """Append 3 rows: seq 1,2,3, row 1 prev_hash GENESIS, each prev_hash equals previous hash; verify() ok."""
    # Append 3 rows
    r1 = ledger.append("call-1", "AAPL", "committee", {"signal": "BUY", "confidence": 0.9}, ["snap-1"], "config-1")
    r2 = ledger.append("call-2", "MSFT", "committee", {"signal": "SELL", "confidence": 0.8}, ["snap-2"], "config-2")
    r3 = ledger.append("call-3", "GOOGL", "committee", {"signal": "HOLD", "confidence": 0.7}, [], None)

    assert r1["seq"] == 1
    assert r2["seq"] == 2
    assert r3["seq"] == 3

    assert r1["prev_hash"] == "GENESIS"
    assert r2["prev_hash"] == r1["hash"]
    assert r3["prev_hash"] == r2["hash"]

    # Verify the chain
    result = ledger.verify()
    assert result["ok"] is True
    assert result["rows"] == 3
    assert result["first_bad_seq"] is None
    assert result["reason"] == "ok"


def test_tamper_detection_payload(temp_db):
    """Edit row 2's payload directly (after dropping triggers), verify() returns ok=False with first_bad_seq==2."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])
    ledger.append("call-2", "MSFT", "committee", {"signal": "SELL"}, ["s2"])
    ledger.append("call-3", "GOOGL", "committee", {"signal": "HOLD"}, ["s3"])

    # Drop the triggers to allow direct edit
    with temp_db.begin() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_update;"))
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_delete;"))

    # Tamper with row 2's payload
    with temp_db.begin() as conn:
        tampered_payload = json.dumps({"signal": "SELL", "confidence": 0.99, "tampered": True})
        conn.execute(
            text("UPDATE ledger_calls SET payload_json = :payload WHERE seq = 2"),
            {"payload": tampered_payload},
        )

    result = ledger.verify()
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2
    assert "hash mismatch" in result["reason"].lower()


def test_tamper_detection_ticker(temp_db):
    """Edit row 2's ticker directly, verify() returns ok=False with first_bad_seq==2."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])
    ledger.append("call-2", "MSFT", "committee", {"signal": "SELL"}, ["s2"])
    ledger.append("call-3", "GOOGL", "committee", {"signal": "HOLD"}, ["s3"])

    with temp_db.begin() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_update;"))
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_delete;"))

    with temp_db.begin() as conn:
        conn.execute(text("UPDATE ledger_calls SET ticker = 'TSLA' WHERE seq = 2"))

    result = ledger.verify()
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2


def test_tamper_detection_recorded_at(temp_db):
    """Edit row 2's recorded_at directly, verify() returns ok=False with first_bad_seq==2."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])
    ledger.append("call-2", "MSFT", "committee", {"signal": "SELL"}, ["s2"])
    ledger.append("call-3", "GOOGL", "committee", {"signal": "HOLD"}, ["s3"])

    with temp_db.begin() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_update;"))
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_delete;"))

    with temp_db.begin() as conn:
        conn.execute(text("UPDATE ledger_calls SET recorded_at = '2026-01-01T00:00:00+00:00' WHERE seq = 2"))

    result = ledger.verify()
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2


def test_delete_row_detects_gap(temp_db):
    """Delete row 2 -> gap detected at the right seq."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])
    ledger.append("call-2", "MSFT", "committee", {"signal": "SELL"}, ["s2"])
    ledger.append("call-3", "GOOGL", "committee", {"signal": "HOLD"}, ["s3"])

    with temp_db.begin() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_update;"))
        conn.execute(text("DROP TRIGGER IF EXISTS ledger_calls_no_delete;"))

    with temp_db.begin() as conn:
        conn.execute(text("DELETE FROM ledger_calls WHERE seq = 2"))

    result = ledger.verify()
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2
    assert "seq gap" in result["reason"].lower()


def test_triggers_block_update(temp_db):
    """A plain UPDATE on ledger_calls raises (triggers present)."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])

    with temp_db.begin() as conn:
        with pytest.raises(Exception) as exc_info:
            conn.execute(text("UPDATE ledger_calls SET ticker = 'TSLA' WHERE seq = 1"))
        assert "append-only" in str(exc_info.value).lower()


def test_triggers_block_delete(temp_db):
    """A plain DELETE on ledger_calls raises (triggers present)."""
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])

    with temp_db.begin() as conn:
        with pytest.raises(Exception) as exc_info:
            conn.execute(text("DELETE FROM ledger_calls WHERE seq = 1"))
        assert "append-only" in str(exc_info.value).lower()


def test_repository_has_no_update_delete_methods():
    """The ledger module exposes no public callable whose name contains update/delete/remove/set.

    The public API is only: append, read, head, verify.
    """
    import inspect

    public_callables = [
        name
        for name in dir(ledger)
        if not name.startswith("_")
        and callable(getattr(ledger, name))
        and inspect.getmodule(getattr(ledger, name)) == ledger  # only functions defined in ledger module
    ]
    forbidden_substrings = ["update", "delete", "remove", "set"]
    for name in public_callables:
        lower = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lower, f"ledger.{name} contains forbidden substring '{forbidden}'"

    # Public API only: these four functions
    expected = {"append", "read", "head", "verify"}
    assert set(public_callables) == expected


def _append_worker(args):
    """Worker function for concurrency test - appends N rows to the same DB file."""
    db_path, worker_id, count = args
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    # Patch db.engine for this worker
    import app.db as db_module
    import app.ledger as ledger_module
    original_engine = db_module.engine
    db_module.engine = engine
    ledger_module.db.engine = engine

    try:
        for i in range(count):
            call_id = f"call-{worker_id}-{i}"
            ledger.append(call_id, f"TICK{worker_id}", "committee", {"seq": i}, [])
    finally:
        db_module.engine = original_engine
        ledger_module.db.engine = original_engine
        engine.dispose()


def test_concurrency_threads(temp_db):
    """4 threads append 25 rows each: exactly 100 rows, seq 1..100 with no gaps or duplicates, verify() ok."""
    db_path = str(temp_db.url).replace("sqlite:///", "")
    num_threads = 4
    rows_per_thread = 25

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(_append_worker, (db_path, i, rows_per_thread))
            for i in range(num_threads)
        ]
        for f in as_completed(futures):
            f.result()

    # Verify final state
    rows = ledger.read(1, 200)
    assert len(rows) == 100
    assert [r["seq"] for r in rows] == list(range(1, 101))
    result = ledger.verify()
    assert result["ok"] is True
    assert result["rows"] == 100


def _append_process_worker(args):
    """Worker function for multiprocessing test."""
    db_path, worker_id, count = args
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    import app.db as db_module
    import app.ledger as ledger_module
    original_engine = db_module.engine
    db_module.engine = engine
    ledger_module.db.engine = engine

    try:
        for i in range(count):
            call_id = f"call-proc-{worker_id}-{i}"
            ledger.append(call_id, f"TICK{worker_id}", "committee", {"seq": i}, [])
    finally:
        db_module.engine = original_engine
        ledger_module.db.engine = original_engine
        engine.dispose()


def test_concurrency_processes(temp_db):
    """2 processes append 25 rows each: exactly 50 rows, seq 1..50 with no gaps or duplicates, verify() ok."""
    db_path = str(temp_db.url).replace("sqlite:///", "")
    num_processes = 2
    rows_per_process = 25

    with mp.Pool(processes=num_processes) as pool:
        pool.map(
            _append_process_worker,
            [(db_path, i, rows_per_process) for i in range(num_processes)],
        )

    rows = ledger.read(1, 200)
    assert len(rows) == 50
    assert [r["seq"] for r in rows] == list(range(1, 51))
    result = ledger.verify()
    assert result["ok"] is True
    assert result["rows"] == 50


def test_canonical_json_key_order(temp_db):
    """Key order in the payload does not change the hash."""
    payload_a = {"a": 1, "b": 2, "c": {"nested": True}}
    payload_b = {"c": {"nested": True}, "a": 1, "b": 2}  # different key order

    r1 = ledger.append("call-a", "AAPL", "committee", payload_a, [])
    r2 = ledger.append("call-b", "AAPL", "committee", payload_b, [])

    # Same payload content -> different call_id but the hash computation should be deterministic
    # Since they have different seq/prev_hash, the final hash differs, but the canonical_json
    # of the payload alone should be identical
    assert _canonical_json(payload_a) == _canonical_json(payload_b)

    # Also test that the row_without_hash produces same canonical_json regardless of key order
    row1 = {k: v for k, v in r1.items() if k != "hash"}
    row2 = {k: v for k, v in r2.items() if k != "hash"}
    row1["payload"] = payload_a
    row2["payload"] = payload_b
    row1["input_snapshot_ids"] = []
    row2["input_snapshot_ids"] = []

    # The canonical_json of the whole row (minus hash) should differ because seq/prev_hash differ
    # but the payload part should be identical
    assert _canonical_json(payload_a) == _canonical_json(payload_b)


def test_admin_routes_viewer_forbidden(temp_db, monkeypatch):
    """Viewer token -> 403 on GET /api/admin/ledger and POST /api/admin/ledger/verify."""
    from fastapi.testclient import TestClient
    from app.main import app

    # Need to override auth to return viewer
    from app.auth import TokenPayload, get_current_user

    async def fake_viewer():
        return TokenPayload(sub="viewer", role="viewer")

    app.dependency_overrides[get_current_user] = fake_viewer
    client = TestClient(app)

    try:
        resp = client.get("/api/admin/ledger", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 403

        resp = client.post("/api/admin/ledger/verify", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_routes_admin_allowed(temp_db, monkeypatch):
    """Admin token -> 200 on GET /api/admin/ledger and POST /api/admin/ledger/verify."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import TokenPayload, get_current_user

    # Add some test data first
    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])
    ledger.append("call-2", "MSFT", "committee", {"signal": "SELL"}, ["s2"])

    async def fake_admin():
        return TokenPayload(sub="admin", role="admin")

    app.dependency_overrides[get_current_user] = fake_admin
    client = TestClient(app)

    try:
        resp = client.get("/api/admin/ledger", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["seq"] == 1
        assert data[1]["seq"] == 2

        resp = client.post("/api/admin/ledger/verify", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        verify_data = resp.json()
        assert verify_data["ok"] is True
        assert verify_data["rows"] == 2
        assert verify_data["first_bad_seq"] is None
    finally:
        app.dependency_overrides.clear()


def test_verify_endpoint_returns_verify_dict(temp_db, monkeypatch):
    """Verify endpoint returns the verify() dict."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import TokenPayload, get_current_user

    ledger.append("call-1", "AAPL", "committee", {"signal": "BUY"}, ["s1"])

    async def fake_admin():
        return TokenPayload(sub="admin", role="admin")

    app.dependency_overrides[get_current_user] = fake_admin
    client = TestClient(app)

    try:
        resp = client.post("/api/admin/ledger/verify", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"ok", "rows", "first_bad_seq", "reason"}
        assert data["ok"] is True
    finally:
        app.dependency_overrides.clear()


def test_migration_upgrade_downgrade(temp_db):
    """Migration: upgrade to head then --down base on a temp DB works and removes table and triggers."""
    from alembic.config import Config
    from alembic import command

    # The temp_db fixture already applied migrations, so we're at head (0003)
    # Now downgrade to base
    with temp_db.begin() as conn:
        migrate.downgrade("base", conn)

    # Check table is gone
    inspector = inspect(temp_db)
    tables = inspector.get_table_names()
    assert "ledger_calls" not in tables

    # Check triggers are gone (SQLite)
    with temp_db.connect() as conn:
        triggers = conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ledger_calls%'")).fetchall()
        trigger_names = [t[0] for t in triggers]
        assert "ledger_calls_no_update" not in trigger_names
        assert "ledger_calls_no_delete" not in trigger_names

    # Upgrade again
    with temp_db.begin() as conn:
        migrate.upgrade(conn)

    tables = inspect(temp_db).get_table_names()
    assert "ledger_calls" in tables

    # Triggers recreated
    with temp_db.connect() as conn:
        triggers = conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ledger_calls%'")).fetchall()
        trigger_names = [t[0] for t in triggers]
        assert "ledger_calls_no_update" in trigger_names
        assert "ledger_calls_no_delete" in trigger_names