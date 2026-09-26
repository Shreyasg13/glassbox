"""Append-only hash-chained call ledger (S3 T11).

This module exposes ONLY:
  - append(...): store a new call, assigning seq and prev_hash inside ONE write transaction.
  - read(...): paginated read by seq range.
  - head(): the latest row.
  - verify(): recompute the chain from seq 1 and report the first bad link.

No update, no delete, no generic "execute". The database triggers (migration 0003) enforce
append-only at the storage layer; this module enforces it at the API layer.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from . import db
from .migrated_tables import ledger_calls_table as _T

log = logging.getLogger("glassbox.ledger")

GENESIS = "GENESIS"
_MAX_RETRIES = 5


def _canonical_json(obj: Any) -> str:
    """Canonical JSON for hashing: sorted keys, no whitespace, ensure_ascii=False."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _iso_now() -> str:
    """Current UTC time as ISO string with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compute_hash(prev_hash: str, row_without_hash: Dict[str, Any]) -> str:
    """Compute the SHA256 hash of prev_hash + canonical JSON of row (without 'hash' key)."""
    data = (prev_hash + _canonical_json(row_without_hash)).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a SQLAlchemy row to a dict with parsed JSON fields."""
    return {
        "seq": row.seq,
        "call_id": row.call_id,
        "ticker": row.ticker,
        "call_type": row.call_type,
        "payload": json.loads(row.payload_json),
        "input_snapshot_ids": json.loads(row.input_snapshot_ids),
        "committee_config_id": row.committee_config_id,
        "recorded_at": row.recorded_at,
        "prev_hash": row.prev_hash,
        "hash": row.hash,
    }


def _head_row(conn) -> Optional[Dict[str, Any]]:
    """Get the latest row (highest seq). Returns None if empty."""
    row = conn.execute(select(_T).order_by(_T.c.seq.desc()).limit(1)).fetchone()
    return _row_to_dict(row) if row else None


def append(
    call_id: str,
    ticker: str,
    call_type: str,
    payload: Any,
    input_snapshot_ids: List[str] = None,
    committee_config_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Store a new ledger entry.

    The seq and prev_hash are assigned inside a SINGLE write transaction.
    SQLite: BEGIN IMMEDIATE takes the write lock before reading the head.
    Postgres: LOCK TABLE ledger_calls IN EXCLUSIVE MODE inside the transaction.
    On primary key conflict (IntegrityError), retry up to 5 times with a short sleep.
    """
    if input_snapshot_ids is None:
        input_snapshot_ids = []

    recorded_at = _iso_now()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with db.engine.begin() as conn:
                # Acquire write lock before reading head
                if db.engine.dialect.name == "sqlite":
                    conn.execute(text("BEGIN IMMEDIATE"))
                else:
                    conn.execute(text("LOCK TABLE ledger_calls IN EXCLUSIVE MODE"))

                head = _head_row(conn)
                seq = (head["seq"] + 1) if head else 1
                prev_hash = head["hash"] if head else GENESIS

                row_without_hash = {
                    "seq": seq,
                    "call_id": call_id,
                    "ticker": ticker,
                    "call_type": call_type,
                    "payload": payload,
                    "input_snapshot_ids": input_snapshot_ids,
                    "committee_config_id": committee_config_id,
                    "recorded_at": recorded_at,
                    "prev_hash": prev_hash,
                }
                row_hash = _compute_hash(prev_hash, row_without_hash)

                insert_row = {
                    "seq": seq,
                    "call_id": call_id,
                    "ticker": ticker,
                    "call_type": call_type,
                    "payload_json": _canonical_json(payload),
                    "input_snapshot_ids": _canonical_json(input_snapshot_ids),
                    "committee_config_id": committee_config_id,
                    "recorded_at": recorded_at,
                    "prev_hash": prev_hash,
                    "hash": row_hash,
                }

                conn.execute(_T.insert().values(**insert_row))
                log.info("ledger append seq=%d call_id=%s", seq, call_id)
                return row_without_hash | {"hash": row_hash}

        except IntegrityError:
            if attempt == _MAX_RETRIES:
                log.error("ledger append failed after %d retries (seq conflict)", _MAX_RETRIES)
                raise
            time.sleep(0.01 * attempt)  # brief backoff

    # Should never reach here
    raise RuntimeError("ledger append: unexpected loop exit")


def read(from_seq: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """Read a page of ledger entries, ordered by seq ascending."""
    limit = max(1, min(limit, 1000))
    with db.engine.connect() as conn:
        rows = conn.execute(
            select(_T)
            .where(_T.c.seq >= from_seq)
            .order_by(_T.c.seq.asc())
            .limit(limit)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def head() -> Optional[Dict[str, Any]]:
    """Return the latest ledger entry, or None if empty."""
    with db.engine.connect() as conn:
        row = _head_row(conn)
    return row


def verify() -> Dict[str, Any]:
    """Verify the hash chain from seq 1.

    Returns:
        {
            "ok": bool,
            "rows": int,
            "first_bad_seq": Optional[int],
            "reason": str
        }

    Checks:
      - seq is contiguous (no gaps)
      - each row's prev_hash matches the previous row's hash (or GENESIS for seq 1)
      - each row's hash matches the recomputed hash from its fields
    """
    with db.engine.connect() as conn:
        rows = conn.execute(select(_T).order_by(_T.c.seq.asc())).fetchall()

    if not rows:
        return {"ok": True, "rows": 0, "first_bad_seq": None, "reason": "empty ledger"}

    prev_hash = GENESIS
    expected_seq = 1

    for row in rows:
        # Check for seq gap
        if row.seq != expected_seq:
            return {
                "ok": False,
                "rows": len(rows),
                "first_bad_seq": expected_seq,
                "reason": f"seq gap: expected {expected_seq}, found {row.seq}",
            }

        row_dict = _row_to_dict(row)

        # Check prev_hash link
        if row.prev_hash != prev_hash:
            return {
                "ok": False,
                "rows": len(rows),
                "first_bad_seq": row.seq,
                "reason": f"prev_hash mismatch at seq {row.seq}: expected {prev_hash[:16]}..., got {row.prev_hash[:16]}...",
            }

        # Recompute hash from row_without_hash
        row_without_hash = {k: v for k, v in row_dict.items() if k != "hash"}
        computed_hash = _compute_hash(prev_hash, row_without_hash)
        if computed_hash != row.hash:
            return {
                "ok": False,
                "rows": len(rows),
                "first_bad_seq": row.seq,
                "reason": f"hash mismatch at seq {row.seq}",
            }

        prev_hash = row.hash
        expected_seq += 1

    return {"ok": True, "rows": len(rows), "first_bad_seq": None, "reason": "ok"}