"""Point-in-time snapshot store for external data fetches (S3 T10).

Records every fetch from SEC, Treasury, BLS, insider, and prices sources with the
time it was fetched and the as-of date the data describes. Read path guarantees
no data fetched after a given run_time is ever returned.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from . import db
from .migrated_tables import source_snapshots_table

log = logging.getLogger("glassbox.snapshot_store")

VALID_SOURCES = {"sec_facts", "sec_filings", "sec_insiders", "treasury", "bls", "prices"}


def _canonical_json(payload: Any) -> str:
    """Canonical JSON for hashing: sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Any) -> str:
    """SHA256 hex of canonical JSON."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _iso(dt_or_str: Optional[str | datetime] = None) -> str:
    """Normalize a datetime or ISO string to a single exact format: YYYY-MM-DDTHH:MM:SS.ffffff+00:00.

    All timestamps stored and compared in the snapshot store must use this format
    so that TEXT comparison (fetched_at <= run_time) works correctly on SQLite and Postgres.
    """
    if dt_or_str is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(dt_or_str, datetime):
        dt = dt_or_str
    else:
        # Parse ISO string, assume UTC if no timezone
        dt = datetime.fromisoformat(dt_or_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    # Always include microseconds (6 digits) and explicit +00:00 offset
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def put(
    source: str,
    ticker: str,
    as_of: str,
    payload: Any,
    fetched_at: Optional[str] = None,
) -> str:
    """Store a snapshot. Returns the snapshot id (existing id on duplicate hash).

    Idempotent: a refetch of identical payload (same source, ticker, payload_hash)
    returns the existing row's id without inserting a new row.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"unknown source {source!r}; must be one of {sorted(VALID_SOURCES)}")

    ticker = (ticker or "").upper()
    fetched_at = _iso(fetched_at)
    canon = _canonical_json(payload)
    phash = _payload_hash(payload)
    snap_id = str(uuid.uuid4())

    row = {
        "id": snap_id,
        "source": source,
        "ticker": ticker,
        "as_of": as_of,
        "fetched_at": fetched_at,
        "payload_json": canon,
        "payload_hash": phash,
    }

    with db.engine.begin() as conn:
        try:
            conn.execute(db._upsert_stmt(source_snapshots_table, [row]).on_conflict_do_nothing(index_elements=["source", "ticker", "payload_hash"]))
        except Exception as exc:  # noqa: BLE001 -- snapshot write must never break the refresh
            log.warning("snapshot_store.put failed for %s/%s: %s", source, ticker, exc)
            raise

        # On conflict (duplicate hash), fetch the existing id
        existing = conn.execute(
            select(source_snapshots_table.c.id).where(
                source_snapshots_table.c.source == source,
                source_snapshots_table.c.ticker == ticker,
                source_snapshots_table.c.payload_hash == phash,
            )
        ).fetchone()
        if existing:
            return existing.id

    return snap_id


def get(source: str, ticker: str, run_time: str) -> Optional[Dict[str, Any]]:
    """Newest snapshot with fetched_at <= run_time for the given source/ticker.

    run_time is REQUIRED (no default). This is the point-in-time guarantee:
    the committee passes its run start timestamp, so it can never see data
    that was fetched after the run began.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"unknown source {source!r}; must be one of {sorted(VALID_SOURCES)}")

    ticker = (ticker or "").upper()
    run_time = _iso(run_time)

    with db.engine.connect() as conn:
        row = conn.execute(
            select(source_snapshots_table)
            .where(
                source_snapshots_table.c.source == source,
                source_snapshots_table.c.ticker == ticker,
                source_snapshots_table.c.fetched_at <= run_time,
            )
            .order_by(source_snapshots_table.c.fetched_at.desc())
            .limit(1)
        ).fetchone()

    if row is None:
        return None

    return json.loads(row.payload_json)


def list(source: Optional[str] = None, ticker: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Metadata only (no payload) for the admin inspector."""
    q = select(
        source_snapshots_table.c.id,
        source_snapshots_table.c.source,
        source_snapshots_table.c.ticker,
        source_snapshots_table.c.as_of,
        source_snapshots_table.c.fetched_at,
        source_snapshots_table.c.payload_hash,
    ).order_by(source_snapshots_table.c.fetched_at.desc()).limit(limit)

    if source is not None:
        q = q.where(source_snapshots_table.c.source == source)
    if ticker is not None:
        q = q.where(source_snapshots_table.c.ticker == ticker.upper())

    with db.engine.connect() as conn:
        rows = conn.execute(q).fetchall()

    return [
        {
            "id": r.id,
            "source": r.source,
            "ticker": r.ticker,
            "as_of": r.as_of,
            "fetched_at": r.fetched_at,
            "payload_hash": r.payload_hash,
        }
        for r in rows
    ]


def get_by_id(snap_id: str) -> Optional[Dict[str, Any]]:
    """Full row including payload, for the admin detail view."""
    with db.engine.connect() as conn:
        row = conn.execute(
            select(source_snapshots_table).where(source_snapshots_table.c.id == snap_id)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row.id,
        "source": row.source,
        "ticker": row.ticker,
        "as_of": row.as_of,
        "fetched_at": row.fetched_at,
        "payload": json.loads(row.payload_json),
        "payload_hash": row.payload_hash,
    }


def get_with_id(source: str, ticker: str, run_time: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Newest snapshot with fetched_at <= run_time for the given source/ticker, returning (id, payload).

    Same point-in-time guarantee as get(): never returns data fetched after run_time.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"unknown source {source!r}; must be one of {sorted(VALID_SOURCES)}")

    ticker = (ticker or "").upper()
    run_time = _iso(run_time)

    with db.engine.connect() as conn:
        row = conn.execute(
            select(source_snapshots_table.c.id, source_snapshots_table.c.payload_json).where(
                source_snapshots_table.c.source == source,
                source_snapshots_table.c.ticker == ticker,
                source_snapshots_table.c.fetched_at <= run_time,
            )
            .order_by(source_snapshots_table.c.fetched_at.desc())
            .limit(1)
        ).fetchone()

    if row is None:
        return None

    return (row.id, json.loads(row.payload_json))