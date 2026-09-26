"""Daily price sync: fetch ONLY what is new, store it in the database, refresh the parquet cache.

Run via: python -m app.scripts.update_daily_data
Normally started by the daily pipeline (app/pipeline.py) as soon as the US close is final; safe to run any time
and as often as you like -- it is idempotent, and it never stores a bar for a session that is still open.

Flow per symbol (see app/price_store.py for why):
  1. First run only: import the existing parquet file into the database (history we already trust).
  2. Fetch from 7 days before the last stored bar, or before the EARLIEST hole in the history, whichever is earlier
     (so an outage of any length heals itself; the first version fetched "the last 10 days" and left an
     8-month hole that was then booked as one enormous daily return).
  3. Keep only FINAL bars (after 16:15 New York time) that pass sanity checks; report the rest.
  4. Upsert into price_bars (new or corrected bars only), then rebuild the parquet file from the database.
  5. Write a `prices` snapshot per symbol per sync with the new bars as payload (S3 T10).

Schema note: the parquet files hold raw OHLCV plus RSI, MA_10/20/30/50/100/200, Volatility and Volume_MA -- the columns
app/data_source.py reads. Volatility and Volume_MA have no recoverable original formula; they are the 20-day rolling
std of daily returns and the 20-day rolling mean of Volume, which is all data_source.py needs (it reads them via
.get(key, fallback)).
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from app import db, price_store
from app import snapshot_store
from app.data_source import STOCK_INFO, TRADING_STORAGE_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("update_daily_data")

# kept for compatibility (tests and older callers import these names from here)
MA_WINDOWS = price_store.MA_WINDOWS
_compute_rsi = price_store.compute_rsi
_recompute_indicators = price_store.recompute_indicators
OVERLAP_DAYS = price_store.OVERLAP_DAYS
MAX_GAP_DAYS = price_store.MAX_GAP_DAYS


def find_gaps(index: pd.Index, max_days: int = MAX_GAP_DAYS) -> list[tuple[str, str, int]]:
    """Holes in a price history: (last bar before, first bar after, calendar days between)."""
    return price_store.find_gaps_dates([pd.Timestamp(x).date().isoformat() for x in index], max_days)


def update_symbol(symbol: str, data_dir: Path, now: Optional[datetime] = None) -> tuple[bool, str, Dict[str, Any]]:
    """Returns (ok, message, info) with info = {new, rejected, not_final, latest}.
    Records a price snapshot internally if new/corrected bars were upserted.
    """
    info: Dict[str, Any] = {"new": 0, "changed": 0, "rejected": [], "not_final": 0, "latest": None}
    seeded = price_store.seed_if_empty(symbol, data_dir)
    before = db.price_bars_summary().get(symbol)
    if not before:
        return False, f"no stored history and no parquet file at {data_dir / (symbol + '.parquet')} to seed from (not creating from scratch)", info
    dates = price_store.stored_dates(symbol)
    overlap = timedelta(days=price_store.OVERLAP_DAYS)
    start = date.fromisoformat(dates[-1]) - overlap
    holes = price_store.find_gaps_dates(dates)
    if holes:
        start = min(start, date.fromisoformat(holes[0][0]) - overlap)
        log.warning("[%s] stored history has %d gap(s), first %s->%s (%dd): backfilling from %s", symbol, len(holes), holes[0][0], holes[0][1], holes[0][2], start)

    fresh = yf.Ticker(symbol).history(start=start.isoformat())
    if fresh.empty:
        return False, "yfinance returned no data (network/rate-limit/symbol issue)", info
    prev = next((r["close"] for r in reversed(db.load_price_bars(symbol)) if r["d"] < pd.Timestamp(fresh.index.min()).date().isoformat()), None)
    rows, rejected, not_final = price_store.frame_to_rows(symbol, fresh, prev_close=prev, now=now)
    for r in rejected:
        log.warning("[%s] REJECTED bar %s: %s", symbol, r["date"], r["why"])
    changed = price_store.delta_rows(symbol, rows)  # write only what is new or corrected
    db.upsert_price_bars(changed)
    after = db.price_bars_summary()[symbol]
    if changed or seeded or not (data_dir / f"{symbol}.parquet").exists():
        price_store.materialize(symbol, data_dir)  # the cache only moves when the data did (its mtime keys the app's caches)
    remaining = price_store.find_gaps_dates(price_store.stored_dates(symbol))
    if remaining:
        log.warning("[%s] price history still has %d gap(s): %s", symbol, len(remaining), "; ".join(f"{a}->{b} ({n}d)" for a, b, n in remaining[:5]))
    info.update({"new": after["count"] - before["count"], "changed": len(changed), "rejected": rejected, "not_final": not_final, "latest": after["last"]})
    msg = f"rows {before['count']}->{after['count']}, latest={after['last']}" + (f", imported {seeded} bars from parquet" if seeded else "") + (f", {len(rejected)} rejected" if rejected else "") + (f", {not_final} provisional bar(s) ignored" if not_final else "")

    # Write price snapshot for this symbol with the new/corrected bars
    if changed:
        try:
            fetched_at = (now or datetime.now(timezone.utc)).isoformat()
            as_of = max(r["d"] for r in changed)
            snapshot_store.put("prices", symbol, as_of, changed, fetched_at=fetched_at)
        except Exception as exc:  # noqa: BLE001 -- snapshot write must never break the sync
            log.warning("snapshot_store.put failed for prices/%s: %s", symbol, exc)

    return True, msg, info


def run(now: Optional[datetime] = None, symbols: Optional[list[str]] = None) -> Dict[str, Any]:
    data_dir = TRADING_STORAGE_PATH / "data_parquet"
    ok, failed, new_bars, rejected, latest, latest_by_symbol = [], [], 0, [], None, {}
    for symbol in symbols or STOCK_INFO:
        try:
            success, message, info = update_symbol(symbol, data_dir, now)
        except Exception as exc:  # one bad symbol must not abort the rest
            success, message, info = False, f"{type(exc).__name__}: {exc}", {}
        if success:
            ok.append(symbol)
            new_bars += info["new"]
            rejected += info["rejected"]
            latest = max(filter(None, [latest, info["latest"]]), default=None)
            latest_by_symbol[symbol] = info["latest"]
            log.info("[%s] OK - %s", symbol, message)
        else:
            failed.append(symbol)
            log.warning("[%s] FAILED - %s", symbol, message)
    log.info("Done. %d/%d symbols updated, %d new bar(s). Failed: %s", len(ok), len(ok) + len(failed), new_bars, failed or "none")
    return {"ok": ok, "failed": failed, "new_bars": new_bars, "rejected": rejected, "latest": latest, "latest_by_symbol": latest_by_symbol}


def main() -> int:
    log.info("TRADING_STORAGE_PATH=%s", TRADING_STORAGE_PATH)
    if not (TRADING_STORAGE_PATH / "data_parquet").exists():
        log.error("data_parquet dir not found at %s -- nothing to update", TRADING_STORAGE_PATH / "data_parquet")
        return 1
    return 0 if not run()["failed"] else 2


if __name__ == "__main__":
    sys.exit(main())
