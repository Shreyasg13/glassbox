"""Verification runner — the only impure part of the gate (S3 T4).

Loads data from the database, calls the pure gate functions, stores results.
Re-running for the same run first deletes that run's previous results in the
same transaction (results are derived data, not the ledger).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

from . import gate
from .. import claims, db, paper, paper_cycle, risk, snapshot_store
from ..migrated_tables import claims_table, verification_results_table, committee_narratives_table, source_snapshots_table

log = logging.getLogger("glassbox.verification")


def _iso(dt_or_str: Optional[str | datetime] = None) -> str:
    """Normalize to the exact ISO format used everywhere."""
    if dt_or_str is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(dt_or_str, datetime):
        dt = dt_or_str
    else:
        dt = datetime.fromisoformat(dt_or_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


async def run_gate(run_id: str, run_time: str, book: Optional[paper.PriceBook] = None) -> Dict[str, Any]:
    """Run the verification gate for a committee run and store results.

    Args:
        run_id: The committee run ID (e.g., "2024-04-23:AAPL")
        run_time: The ISO timestamp when the run started
        book: Optional PriceBook (loaded if not provided)

    Returns:
        The summary dict from gate.summarize()
    """
    # Load the PriceBook if not provided
    if book is None:
        book = await paper_cycle.load_book_async()

    # Extract the symbol and date from run_id
    try:
        d, sym = run_id.split(":", 1)
    except ValueError:
        log.error("run_gate: invalid run_id format %r", run_id)
        return {"total": 0, "passed": 0, "failed": 0, "warned": 0, "ok": True, "badge": "0/0 numbers verified against source"}

    # Load claims for this run
    with db.engine.connect() as conn:
        claim_rows = conn.execute(
            select(claims_table).where(claims_table.c.run_id == run_id).order_by(claims_table.c.created_at)
        ).fetchall()

    if not claim_rows:
        log.info("run_gate: no claims found for %s", run_id)
        return {"total": 0, "passed": 0, "failed": 0, "warned": 0, "ok": True, "badge": "0/0 numbers verified against source"}

    claims_list = [
        {
            "id": r.id,
            "run_id": r.run_id,
            "ticker": r.ticker,
            "metric": r.metric,
            "value": r.value,
            "unit": r.unit,
            "period": r.period,
            "source": r.source,
            "source_snapshot_id": r.source_snapshot_id,
            "source_path": r.source_path,
            "text_span": r.text_span,
            "created_at": r.created_at,
        }
        for r in claim_rows
    ]

    # Build snapshots_by_claim_id: fetch snapshot metadata and payload for each claim's source_snapshot_id
    snapshots_by_claim_id: Dict[str, tuple] = {}
    for claim in claims_list:
        snap_id = claim.get("source_snapshot_id")
        if snap_id:
            with db.engine.connect() as conn:
                row = conn.execute(
                    select(
                        source_snapshots_table.c.id,
                        source_snapshots_table.c.source,
                        source_snapshots_table.c.ticker,
                        source_snapshots_table.c.as_of,
                        source_snapshots_table.c.fetched_at,
                        source_snapshots_table.c.payload_json,
                        source_snapshots_table.c.payload_hash,
                    ).where(source_snapshots_table.c.id == snap_id)
                ).fetchone()
            if row:
                import json
                payload = json.loads(row.payload_json)
                snapshot_meta = {
                    "id": row.id,
                    "source": row.source,
                    "ticker": row.ticker,
                    "as_of": row.as_of,
                    "fetched_at": row.fetched_at,
                    "payload_hash": row.payload_hash,
                }
                snapshots_by_claim_id[claim["id"]] = (snapshot_meta, payload)

    # Get price book closes for the symbol
    prices = {date_str: book.close[sym][date_str] for date_str in book._sorted_dates.get(sym, []) if date_str in book.close.get(sym, {})}

    # Recompute risk independently (second computation, not a move)
    recomputed_risk = risk.risk_at(book, sym, d)

    # Load narrative row for this run
    narrative_row = None
    with db.engine.connect() as conn:
        nar_row = conn.execute(
            select(committee_narratives_table).where(committee_narratives_table.c.run_id == run_id)
        ).fetchone()
    if nar_row:
        narrative_row = {
            "run_id": nar_row.run_id,
            "narrative": nar_row.narrative,
            "status": nar_row.status,
            "attempts": nar_row.attempts,
            "provider_requested": nar_row.provider_requested,
            "model_requested": nar_row.model_requested,
            "provider_answered": nar_row.provider_answered,
            "model_answered": nar_row.model_answered,
            "error": nar_row.error,
            "created_at": nar_row.created_at,
        }

    # Build inputs for verify_run
    inputs = {
        "claims": claims_list,
        "snapshots_by_claim_id": snapshots_by_claim_id,
        "run_time": run_time,
        "run_date": d,
        "prices": prices,
        "recomputed_risk": recomputed_risk,
        "narrative_row": narrative_row,
        "windows": None,  # use defaults from config
    }

    # Run all checks
    results = gate.verify_run(inputs)
    summary = gate.summarize(results)

    # Store results in the database (replace any existing for this run_id)
    now_iso = _iso()
    rows_to_insert = []
    for r in results:
        rows_to_insert.append({
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "claim_id": r.claim_id,
            "check_type": r.check_type,
            "status": r.status,
            "expected": r.expected,
            "observed": r.observed,
            "reason": r.reason,
            "created_at": now_iso,
        })

    with db.engine.begin() as conn:
        # Delete existing results for this run
        conn.execute(delete(verification_results_table).where(verification_results_table.c.run_id == run_id))
        # Insert new results
        if rows_to_insert:
            conn.execute(verification_results_table.insert(), rows_to_insert)

    log.info("run_gate: stored %d verification results for %s (summary: %s)", len(results), run_id, summary)
    return summary