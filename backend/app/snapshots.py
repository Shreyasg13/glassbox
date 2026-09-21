"""Daily point-in-time snapshots: what the system believed at each close, kept as it was.

Prices are re-derivable from the price table, but the system's BELIEFS are not: the engine signal, the risk
score, the committee's call and the market cohesion on a given day are computed from data as it stood that day
(later corrections and later committee runs would change a recomputation). One row per trading day is written
after the daily pipeline finishes and read back as labelled matrices, so "what did we think of NVDA over the
last 90 days?" or "how did average correlation move into the drawdown?" is a lookup, not a recomputation.

A snapshot is small (15 symbols, a few dozen numbers each) and rewriting the same date is idempotent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from . import associations, db, free_data, panel as P, price_store, risk

log = logging.getLogger("glassbox.snapshots")

SNAPSHOT_FIELDS = {
    "close": ("close", None),
    "signal": ("signal", P.SIGNAL_CODE),
    "confidence": ("confidence", None),
    "rsi": ("rsi", None),
    "risk_score": ("risk_score", None),
    "risk_level": ("risk_level", P.RISK_CODE),
    "drawdown": ("drawdown", None),
    "committee": ("committee", P.SIGNAL_CODE),
    "consensus": ("consensus", None),
}


def build(book: Any, d: str, runs: Optional[List[Dict[str, Any]]] = None, macro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The snapshot document for bar date `d`, from data up to and including `d` only."""
    day_runs = {r["symbol"]: r for r in (runs or []) if r.get("date") == d and r.get("symbol")}
    syms: Dict[str, Any] = {}
    for s in book.symbols:
        px = book.close.get(s, {}).get(d)
        if px is None:
            continue  # no bar that day for this symbol
        sig = book.signal.get(s, {}).get(d)
        rk = risk.risk_at(book, s, d)
        row: Dict[str, Any] = {"close": px}
        if sig:
            row.update({"signal": sig[0], "confidence": round(sig[1], 2), "rsi": round(sig[2], 2)})
        if rk:
            row.update({"risk_score": rk["score"], "risk_level": rk["level"], "drawdown": rk["drawdown"]})
        r = day_runs.get(s)
        if r:
            action = r.get("action") or (r.get("decision") if r.get("quorum_ok") else None)
            row.update(
                {
                    "committee": action,
                    "committee_vote": r.get("decision"),
                    "committee_gate": r.get("gate"),
                    "consensus": (r.get("ceo") or {}).get("consensus"),
                    "answered": r.get("answered"),
                }
            )
        syms[s] = row
    try:
        coh = associations.cohesion(book, d)
        corr = associations.correlations(book, d)
        groups = associations.clusters(corr)
    except Exception as exc:  # noqa: BLE001 -- a snapshot without associations beats no snapshot
        log.warning("associations unavailable for snapshot %s (%s)", d, type(exc).__name__)
        coh, groups = None, []
    return {
        "date": d,
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "data_version": price_store.data_version(),
        "symbols": syms,
        "cohesion": coh,
        "clusters": groups,
        "macro": macro,
    }


def take(book: Any, d: Optional[str] = None) -> Dict[str, Any]:
    """Write (or rewrite) the snapshot for `d` (default: the latest bar in the book)."""
    d = d or book.latest_date
    if not d:
        raise ValueError("no price data")
    try:
        runs = db.list_all_committee_runs()
    except Exception as exc:  # noqa: BLE001
        log.warning("committee runs unavailable for snapshot (%s)", type(exc).__name__)
        runs = []
    try:
        macro = free_data.macro_as_of(d)
    except Exception:  # noqa: BLE001
        macro = None
    doc = build(book, d, runs, macro)
    db.save_snapshot(d, doc)
    return doc


def matrix(field: str, days: int = 120) -> Dict[str, Any]:
    """One field across the stored snapshots as a labelled matrix: {dates, symbols, values[T][S], field}.
    Text fields come back as their numeric codes (SELL -1, HOLD 0, BUY +1; LOW 0, MEDIUM 1, HIGH 2); missing is null."""
    if field not in SNAPSHOT_FIELDS:
        raise KeyError(field)
    key, code = SNAPSHOT_FIELDS[field]
    snaps = db.list_snapshots(days)
    symbols = sorted({s for snap in snaps for s in snap.get("symbols", {})})
    values: List[List[Optional[float]]] = []
    for snap in snaps:
        row = []
        for s in symbols:
            v = snap.get("symbols", {}).get(s, {}).get(key)
            if code is not None:
                v = code.get(v) if isinstance(v, str) else None
            row.append(None if v is None else float(v))
        values.append(row)
    return {"field": field, "dates": [snap["date"] for snap in snaps], "symbols": symbols, "values": values, "codes": code}


def series(field: str, symbol: str, days: int = 120) -> Dict[str, Any]:
    """One symbol's field over the stored snapshots (a column of `matrix`)."""
    m = matrix(field, days)
    if symbol not in m["symbols"]:
        return {"field": field, "symbol": symbol, "dates": [], "values": []}
    j = m["symbols"].index(symbol)
    keep = [(d, row[j]) for d, row in zip(m["dates"], m["values"]) if row[j] is not None]
    return {"field": field, "symbol": symbol, "dates": [d for d, _ in keep], "values": [v for _, v in keep]}


def cohesion_history(days: int = 250) -> Dict[str, Any]:
    snaps = db.list_snapshots(days)
    rows = [(s["date"], (s.get("cohesion") or {}).get("value"), (s.get("cohesion") or {}).get("label")) for s in snaps]
    return {"dates": [r[0] for r in rows], "value": [r[1] for r in rows], "label": [r[2] for r in rows]}


def missing_dates(book: Any, days: int = 60) -> List[str]:
    """Trading days in the recent calendar that have no snapshot (the pipeline was down that day)."""
    have = {s["date"] for s in db.list_snapshots(400)}
    return [d for d in book.dates[-days:] if d not in have]


def as_array(m: Dict[str, Any]) -> np.ndarray:
    """A `matrix()` result as a float array with NaN for missing."""
    return np.array([[np.nan if v is None else v for v in row] for row in m["values"]], dtype=float).reshape(len(m["dates"]), len(m["symbols"]))
