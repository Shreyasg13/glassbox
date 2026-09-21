"""Daily refresh of the per-symbol OHLCV + indicator parquet files.

Run via: python -m app.scripts.update_daily_data
Intended to run once per weekday, after US market close, as a cron job
(see docs/DEPLOY_GCP.md for the deployed schedule).

Schema note: the existing data_parquet/{symbol}.parquet files were NOT
produced by backend-source/live_trading/LIVE_DATA_CONNECTOR.py -- that
script computes a different column set (SMA_20/50/200, MACD, EMA, ATR,
BB_*) and writes to a different path (data_parquet/prices/daily/, nested)
than what app/data_source.py actually reads (flat data_parquet/{symbol}.parquet
with RSI, MA_10/20/30/50/100/200, Volatility, Volume_MA). This script
targets the real schema, verified by reading the live files directly.

Volatility and Volume_MA have no recoverable "true" original formula (no
source script producing this exact column set exists in backend-source/).
Chosen here: Volatility = 20-day rolling std of daily pct-change returns,
Volume_MA = 20-day rolling mean of Volume. data_source.py reads these via
.get(key, fallback), so a reasonable reconstruction is sufficient -- exact
historical replication of an undocumented formula is not achievable.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from app.data_source import STOCK_INFO, TRADING_STORAGE_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("update_daily_data")

MA_WINDOWS = (10, 20, 30, 50, 100, 200)
RSI_PERIOD = 14
VOL_WINDOW = 20
VOLUME_MA_WINDOW = 20


def _compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder's RSI via exponential moving average of gains/losses."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _recompute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["RSI"] = _compute_rsi(df["Close"])
    for window in MA_WINDOWS:
        df[f"MA_{window}"] = df["Close"].rolling(window=window, min_periods=1).mean()
    df["Volatility"] = df["Close"].pct_change().rolling(window=VOL_WINDOW, min_periods=1).std()
    df["Volume_MA"] = df["Volume"].rolling(window=VOLUME_MA_WINDOW, min_periods=1).mean()
    return df


OVERLAP_DAYS = 7  # re-fetch this far back from the last stored bar, so late corrections to recent bars are picked up
MAX_GAP_DAYS = 5  # more calendar days than this between consecutive bars is not a weekend or a holiday


def find_gaps(index: pd.Index, max_days: int = MAX_GAP_DAYS) -> list[tuple[str, str, int]]:
    """Holes in a price history: (last bar before, first bar after, calendar days between)."""
    dates = [pd.Timestamp(x).date() for x in index]
    return [(a.isoformat(), b.isoformat(), (b - a).days) for a, b in zip(dates, dates[1:]) if (b - a).days > max_days]


def update_symbol(symbol: str, data_dir: Path) -> tuple[bool, str]:
    parquet_path = data_dir / f"{symbol}.parquet"
    if not parquet_path.exists():
        return False, f"no existing file at {parquet_path}, skipping (not creating from scratch)"

    existing = pd.read_parquet(parquet_path)
    original_rows = len(existing)
    original_earliest = existing.index.min()

    ticker = yf.Ticker(symbol)
    # Fetch from just before the last STORED bar, not "the last 10 days". A fixed window silently leaves a
    # hole whenever the file is older than the window: the first run on the VM appended only the last 10
    # days to a file that ended 8 months earlier, and that gap was booked as one enormous "day".
    # A hole may also sit in the MIDDLE of the file (the bad first run left one, then later runs appended recent
    # days after it), so the fetch must reach back to before the EARLIEST hole, not just the last stored bar.
    overlap = pd.Timedelta(days=OVERLAP_DAYS)
    start_date = (pd.Timestamp(existing.index.max()) - overlap).date()
    holes = find_gaps(existing.index)
    if holes:
        start_date = min(start_date, (pd.Timestamp(holes[0][0]) - overlap).date())
        log.warning("[%s] stored history has %d gap(s), first %s->%s (%dd): backfilling from %s", symbol, len(holes), holes[0][0], holes[0][1], holes[0][2], start_date)
    start = start_date.isoformat()
    fresh = ticker.history(start=start)
    if fresh.empty:
        return False, "yfinance returned no data (network/rate-limit/symbol issue)"

    # Keep raw OHLCV + corporate-action columns from both sources; recomputed
    # indicator columns get dropped and rebuilt below so there's no risk of
    # stale/duplicate indicator values from either side.
    indicator_cols = ["RSI", "Volatility", "Volume_MA"] + [f"MA_{w}" for w in MA_WINDOWS]
    existing_raw = existing.drop(columns=[c for c in indicator_cols if c in existing.columns])
    fresh_raw = fresh.drop(columns=[c for c in indicator_cols if c in fresh.columns])

    merged_raw = pd.concat([existing_raw, fresh_raw])
    merged_raw = merged_raw[~merged_raw.index.duplicated(keep="last")].sort_index()

    if len(merged_raw) < original_rows:
        return False, f"REFUSING TO WRITE: merged rows ({len(merged_raw)}) < original ({original_rows})"
    if merged_raw.index.min() != original_earliest:
        return False, (
            f"REFUSING TO WRITE: earliest date shifted from {original_earliest} "
            f"to {merged_raw.index.min()}"
        )

    merged = _recompute_indicators(merged_raw)
    gaps = find_gaps(merged.index)
    if gaps:
        log.warning("[%s] price history still has %d gap(s): %s", symbol, len(gaps), "; ".join(f"{a}->{b} ({n}d)" for a, b, n in gaps[:5]))

    tmp_path = parquet_path.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp_path, engine="pyarrow")
    os.replace(tmp_path, parquet_path)

    latest = merged.iloc[-1]
    summary = (
        f"rows {original_rows}->{len(merged)}, latest={merged.index[-1].date()} "
        f"close={latest['Close']:.2f} rsi={latest['RSI']:.1f}"
    )
    return True, summary


def main() -> int:
    data_dir = TRADING_STORAGE_PATH / "data_parquet"
    log.info("TRADING_STORAGE_PATH=%s", TRADING_STORAGE_PATH)
    if not data_dir.exists():
        log.error("data_parquet dir not found at %s -- nothing to update", data_dir)
        return 1

    ok, failed = [], []
    for symbol in STOCK_INFO:
        try:
            success, message = update_symbol(symbol, data_dir)
        except Exception as exc:  # one bad symbol must not abort the rest
            success, message = False, f"{type(exc).__name__}: {exc}"
        if success:
            ok.append(symbol)
            log.info("[%s] OK - %s", symbol, message)
        else:
            failed.append(symbol)
            log.warning("[%s] FAILED - %s", symbol, message)

    log.info("Done. %d/%d symbols updated. Failed: %s", len(ok), len(STOCK_INFO), failed or "none")
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
