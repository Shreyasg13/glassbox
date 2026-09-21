"""Market prices: the database is the source of truth, parquet is a rebuildable cache.

    yfinance --(delta only)--> validate --> price_bars (DB) --> materialize --> data_parquet/{SYM}.parquet --> everything else

Why this shape
  * DURABLE. Prices used to exist only as files on one VM disk; if it died the history had to be refetched
    and every account replay would shift slightly (dividend-adjustment basis). Now the raw bars are in the
    database with the accounts and decisions, and any VM can rebuild its parquet cache from them.
  * DELTA. A run writes only bars that are new or corrected (upsert by (symbol, date)); nothing is
    re-imported. The fetch itself starts from the last stored bar, or before the earliest hole.
  * HONEST BARS. A bar is only accepted once its trading day is FINAL (after the close, in New York time):
    Yahoo returns a partial "today" bar during the session, and storing it would feed a half-day price to
    the signals, the committee and the paper accounts. Bars that fail basic sanity (non-positive price,
    high below low, a >60% one-day move that looks like an unadjusted split) are rejected and reported
    instead of stored.
  * CONSUMERS UNCHANGED. Indicators (RSI, moving averages, volatility) are derived from the raw bars by the
    same formulas as before, so the parquet files -- and every signal and account computed from them -- are
    bit-for-bit what they were (verify_roundtrip proves it before anything is switched over).
"""
from __future__ import annotations

import logging
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import db

log = logging.getLogger("glassbox.price_store")

ET = ZoneInfo("America/New_York")
FINAL_AFTER_ET = time(16, 15)  # the close is 16:00; the official closing prices settle a few minutes later
MAX_ONE_DAY_MOVE = 0.60  # beyond this a "daily return" is almost surely an unadjusted split or a bad tick
MAX_GAP_DAYS = 5  # more calendar days than this between consecutive bars is a hole, not a weekend or holiday
OVERLAP_DAYS = 7  # re-fetch this far back from the last stored bar so late corrections are picked up

RAW_COLS = ["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]
_DB_COL = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Dividends": "dividends", "Stock Splits": "splits"}

MA_WINDOWS = (10, 20, 30, 50, 100, 200)
RSI_PERIOD = 14
VOL_WINDOW = 20
VOLUME_MA_WINDOW = 20


# ----------------------------------------------------------------- indicators --


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder's RSI via exponential moving average of gains/losses."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def recompute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["RSI"] = compute_rsi(df["Close"])
    for window in MA_WINDOWS:
        df[f"MA_{window}"] = df["Close"].rolling(window=window, min_periods=1).mean()
    df["Volatility"] = df["Close"].pct_change().rolling(window=VOL_WINDOW, min_periods=1).std()
    df["Volume_MA"] = df["Volume"].rolling(window=VOLUME_MA_WINDOW, min_periods=1).mean()
    return df


# ------------------------------------------------------------------ the calendar --


def final_cutoff(now: Optional[datetime] = None) -> str:
    """The latest calendar date whose bar can be final: today (New York) once it is past 16:15, else yesterday."""
    n = (now or datetime.now(timezone.utc)).astimezone(ET)
    return (n.date() if n.time() >= FINAL_AFTER_ET else n.date() - timedelta(days=1)).isoformat()


def last_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def find_gaps_dates(dates: List[str], max_days: int = MAX_GAP_DAYS) -> List[Tuple[str, str, int]]:
    out = []
    for a, b in zip(dates, dates[1:]):
        n = (date.fromisoformat(b) - date.fromisoformat(a)).days
        if n > max_days:
            out.append((a, b, n))
    return out


# --------------------------------------------------------- frame <-> database rows --


def _finite(*xs: Any) -> bool:
    return all(x is not None and isinstance(x, (int, float, np.floating, np.integer)) and math.isfinite(float(x)) for x in xs)


def frame_to_rows(symbol: str, df: pd.DataFrame, *, prev_close: Optional[float] = None, now: Optional[datetime] = None, trust: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], int]:
    """Raw bars from a fetched frame as database rows: (rows, rejected, not_final).

    `trust=True` is for importing history we already hold (no final-bar gate, no sanity filter)."""
    cutoff = None if trust else final_cutoff(now)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    rows: List[Dict[str, Any]] = []
    rejected: List[Dict[str, str]] = []
    not_final = 0
    prev = prev_close
    for ts, r in df.sort_index().iterrows():
        d = pd.Timestamp(ts).date().isoformat()
        o, h, l, c = (float(r.get(k, np.nan)) for k in ("Open", "High", "Low", "Close"))
        if cutoff is not None and d > cutoff:
            not_final += 1  # today's session is still open: this bar is provisional
            continue
        if not trust:
            why = None
            if not _finite(c) or c <= 0:
                why = "non-positive or missing close"
            elif _finite(h, l) and h < l - 1e-9:
                why = "high below low"
            elif prev and abs(c / prev - 1) > MAX_ONE_DAY_MOVE:
                why = f"{c / prev - 1:+.0%} in one day (unadjusted split or bad tick?)"
            if why:
                rejected.append({"symbol": symbol, "date": d, "why": why})
                continue
        rows.append(
            {
                "symbol": symbol, "d": d, "open": _num(o), "high": _num(h), "low": _num(l), "close": float(c),
                "volume": _num(r.get("Volume")), "dividends": _num(r.get("Dividends"), 0.0), "splits": _num(r.get("Stock Splits"), 0.0), "updated_at": stamp,
            }
        )
        prev = c
    return rows, rejected, not_final


def _num(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def rows_to_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """The raw OHLCV frame the parquet files have always held: New York midnight index named 'Date', Volume as int64."""
    idx = pd.DatetimeIndex(pd.to_datetime([r["d"] for r in rows])).tz_localize(ET)
    idx.name = "Date"
    data = {col: [r[_DB_COL[col]] for r in rows] for col in RAW_COLS}
    df = pd.DataFrame(data, index=idx)
    df["Volume"] = df["Volume"].fillna(0).round().astype("int64")
    for c in ("Dividends", "Stock Splits"):
        df[c] = df[c].fillna(0.0)
    return df


def delta_rows(symbol: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Only the bars that are new or whose values differ from what is stored -- the write is the delta, nothing else.
    (A poll every few minutes must not rewrite the same ten bars each time.)"""
    if not rows:
        return []
    stored = {r["d"]: r for r in db.load_price_bars(symbol, since=min(r["d"] for r in rows))}
    out = []
    for r in rows:
        old = stored.get(r["d"])
        if old is None or any(not _same(old[k], r[k]) for k in ("open", "high", "low", "close", "volume", "dividends", "splits")):
            out.append(r)
    return out


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))


# ------------------------------------------------------------------- import / cache --


def stored_dates(symbol: str) -> List[str]:
    return [r["d"] for r in db.load_price_bars(symbol)]


def import_parquet(symbol: str, data_dir: Path) -> int:
    """Seed the database from an existing parquet file (history we already trust). Idempotent."""
    path = data_dir / f"{symbol}.parquet"
    if not path.exists():
        return 0
    rows, _rej, _nf = frame_to_rows(symbol, pd.read_parquet(path), trust=True)
    return db.upsert_price_bars(rows)


def seed_if_empty(symbol: str, data_dir: Path) -> int:
    return import_parquet(symbol, data_dir) if symbol not in db.price_bars_summary() else 0


def materialize_frame(symbol: str) -> Optional[pd.DataFrame]:
    rows = db.load_price_bars(symbol)
    return recompute_indicators(rows_to_frame(rows)) if rows else None


def materialize(symbol: str, data_dir: Path) -> Optional[Path]:
    """Rebuild data_parquet/{symbol}.parquet from the database (atomic replace)."""
    df = materialize_frame(symbol)
    if df is None:
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{symbol}.parquet"
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, engine="pyarrow")
    os.replace(tmp, path)
    return path


def materialize_all(data_dir: Path, symbols: Optional[List[str]] = None) -> List[str]:
    return [s for s in (symbols or sorted(db.price_bars_summary())) if materialize(s, data_dir)]


def verify_roundtrip(symbol: str, data_dir: Path) -> Dict[str, Any]:
    """Does rebuilding from the database reproduce the existing parquet file exactly? (Checked before switching over.)"""
    existing = pd.read_parquet(data_dir / f"{symbol}.parquet")
    rebuilt = materialize_frame(symbol)
    if rebuilt is None:
        return {"symbol": symbol, "ok": False, "why": "nothing in the database"}
    if list(existing.columns) != list(rebuilt.columns):
        return {"symbol": symbol, "ok": False, "why": f"columns differ: {list(existing.columns)} vs {list(rebuilt.columns)}"}
    if len(existing) != len(rebuilt) or not (existing.index == rebuilt.index).all():
        return {"symbol": symbol, "ok": False, "why": f"rows/index differ: {len(existing)} vs {len(rebuilt)}"}
    diff = float(np.nanmax(np.abs(existing.to_numpy(dtype=float) - rebuilt.to_numpy(dtype=float)))) if len(existing) else 0.0
    return {"symbol": symbol, "ok": diff <= 1e-9, "rows": len(rebuilt), "max_abs_diff": diff, "dtypes_equal": bool((existing.dtypes == rebuilt.dtypes).all())}


def data_version() -> str:
    """A cheap fingerprint of what is stored (latest date + number of bars): caches key on this, not on file times."""
    s = db.price_bars_summary()
    return f"{max((v['last'] for v in s.values()), default='none')}|{sum(v['count'] for v in s.values())}"
