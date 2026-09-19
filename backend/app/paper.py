"""Paper-trading + backtest engine.

Turns the quant engine's BUY/SELL/HOLD signals into simulated portfolios so
the strategy can be measured, compared and improved. No database and no
network in here -- accounts are plain dicts and prices come from a PriceBook,
so the same code drives the historical replay ("backtest") and the daily live
cycle, and can be tested exhaustively. Persistence and scheduling live in
app/scripts/run_paper_cycle.py; the admin API is routers/paper.py.

RULES (deliberately simple, all stated so results can be audited):

* Decisions use day D's close; orders EXECUTE at day D+1's close. Signals at D
  use D's close, so filling at D's close would be a look-ahead. Fractional
  shares, long-only, no leverage, no shorting.
* Costs: COMMISSION_BPS (default 5 bps) of every traded notional.
* engine_tilt: target weight of a symbol = invested * strategic_weight * tilt,
  where tilt is the engine's own suggested-weight multiplier (BUY 1.5x, HOLD
  1.0x, SELL 0.5x -- the same numbers /api/live-signals reports). Total above
  100% is scaled down; anything left over is cash, so SELL signals raise cash
  (risk-off) and BUY signals deploy it. A position is capped at the risk
  policy's max_position unless the strategic weight itself is larger.
  Trading is event-driven, not every-wiggle: an account rebalances when its
  signal set changes, or every REBALANCE_DAYS trading days if any weight has
  drifted more than DRIFT_THRESHOLD from target.
* static_rebalanced: the same strategic weights and the SAME rebalancing rules
  but every signal treated as HOLD. Every profile gets one as its benchmark
  ("policy portfolio"), so alpha = what the signals added, net of costs,
  rather than being muddied by rebalancing-vs-buy-and-hold effects.
* static_hold: buy the weights once and never trade (SPY / equal-weight
  controls).
* random_tilt: a placebo. Each symbol is driven by a DIFFERENT symbol's real
  signal history (a seeded cyclic shift), so signal frequency and persistence
  are exactly the engine's but any relationship to the symbol's own price is
  destroyed. If the engine cannot beat this, its signals carry no information.
* Every trading day is tagged "backtest" (before the account's live_from date)
  or "live". Backtest results are IN-SAMPLE: the trained parameters
  (RSI thresholds, MA windows) were fitted on this same history, so backtest
  returns are optimistic. Live results are genuine out-of-sample paper trading.
"""
from __future__ import annotations

import bisect
import hashlib
import math
import os
from typing import Any, Dict, List, Optional, Tuple

from . import data_source as ds

COMMISSION_BPS = float(os.environ.get("PAPER_COMMISSION_BPS", "5"))
DRIFT_THRESHOLD = 0.05
REBALANCE_DAYS = 21  # trading days between drift-driven rebalances (~monthly)
MIN_TRADE_FRACTION = 0.002  # ignore rebalances smaller than 0.2% of equity
TRADING_DAYS = 252
MAX_STORED_TRADES = 1000

TILT = {"BUY": 1.5, "HOLD": 1.0, "SELL": 0.5}

# invested = share of the portfolio deployed at neutral (all-HOLD) signals.
RISK_POLICY = {
    "conservative": {"invested": 0.60, "max_position": 0.35},
    "moderate": {"invested": 0.80, "max_position": 0.45},
    "aggressive": {"invested": 0.95, "max_position": 0.60},
}

STRATEGIES = ("engine_tilt", "static_hold", "static_rebalanced", "random_tilt", "cash")


# --------------------------------------------------------------- price data --


class PriceBook:
    """Closes and per-day engine signals for a set of symbols, keyed by
    'YYYY-MM-DD' strings. Build with PriceBook.from_frames()."""

    def __init__(self) -> None:
        self.close: Dict[str, Dict[str, float]] = {}
        self.signal: Dict[str, Dict[str, Tuple[str, float, float]]] = {}  # date -> (signal, confidence, rsi)
        self._sorted_dates: Dict[str, List[str]] = {}
        self.dates: List[str] = []

    @classmethod
    def from_frames(cls, frames: Dict[str, Any], params: Dict[str, Any]) -> "PriceBook":
        import numpy as np
        import pandas as pd

        book = cls()
        all_dates = set()
        for sym, df in frames.items():
            if df is None or len(df) == 0 or "Close" not in df:
                continue
            idx = pd.to_datetime(df.index)
            dstr = [ts.strftime("%Y-%m-%d") for ts in idx]
            p = params.get(sym, {})
            fast_col = f"MA_{p.get('fast_ma', 20)}"
            slow_col = f"MA_{p.get('slow_ma', 50)}"
            close = df["Close"].astype(float).to_numpy()
            rsi = df["RSI"].astype(float).to_numpy() if "RSI" in df else np.full(len(df), 50.0)
            fast = (df[fast_col] if fast_col in df else df["MA_20"] if "MA_20" in df else df["Close"]).astype(float).to_numpy()
            slow = (df[slow_col] if slow_col in df else df["MA_50"] if "MA_50" in df else df["Close"]).astype(float).to_numpy()

            closes: Dict[str, float] = {}
            sigs: Dict[str, Tuple[str, float, float]] = {}
            for i, d in enumerate(dstr):
                if not math.isfinite(close[i]) or close[i] <= 0:
                    continue
                closes[d] = float(close[i])
                # NaN indicators (warm-up rows) fail every comparison -> HOLD,
                # exactly as get_live_signals treats them.
                if fast[i] > slow[i]:
                    cross = "BULLISH"
                elif fast[i] < slow[i]:
                    cross = "BEARISH"
                else:
                    cross = "NEUTRAL"
                r = float(rsi[i]) if math.isfinite(rsi[i]) else 50.0
                sig, conf = ds.signal_from_indicators(r, cross, p)
                sigs[d] = (sig, float(conf), r)
            book.close[sym] = closes
            book.signal[sym] = sigs
            book._sorted_dates[sym] = sorted(closes)
            all_dates.update(closes)
        book.dates = sorted(all_dates)
        return book

    @property
    def symbols(self) -> List[str]:
        return sorted(self.close)

    @property
    def latest_date(self) -> Optional[str]:
        return self.dates[-1] if self.dates else None

    def close_on(self, sym: str, d: str) -> Optional[float]:
        """Close on `d`, or the last known close before it (a halted symbol
        keeps its last price for valuation; it just can't be traded)."""
        series = self.close.get(sym)
        if not series:
            return None
        if d in series:
            return series[d]
        ds_ = self._sorted_dates[sym]
        i = bisect.bisect_right(ds_, d)
        return series[ds_[i - 1]] if i else None

    def signal_at(self, sym: str, d: str) -> Tuple[str, float]:
        s = self.signal.get(sym, {}).get(d)
        return (s[0], s[1]) if s else ("HOLD", 50.0)

    def signals_on(self, d: str, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        out = []
        for sym in symbols or self.symbols:
            s = self.signal.get(sym, {}).get(d)
            if s:
                out.append({"symbol": sym, "signal": s[0], "confidence": s[1], "rsi": round(s[2], 1), "close": self.close[sym][d]})
        return out


# ---------------------------------------------------------------- accounts --


def _normalise(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(w for w in weights.values() if w > 0)
    return {k: w / total for k, w in weights.items() if w > 0} if total > 0 else {}


def new_account(
    account_id: str,
    name: str,
    kind: str,
    strategy: str,
    weights: Dict[str, float],
    *,
    invested: float,
    start_cash: float = 100_000.0,
    risk_level: Optional[str] = None,
    username: Optional[str] = None,
    benchmark_id: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    note: str = "",
) -> Dict[str, Any]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}")
    return {
        "id": account_id,
        "name": name,
        "kind": kind,  # profile | benchmark | control
        "strategy": strategy,
        "weights": _normalise(weights),
        "invested": invested,
        "risk_level": risk_level,
        "username": username,
        "benchmark_id": benchmark_id,
        "profile": profile or {},
        "note": note,
        "start_cash": float(start_cash),
        "cash": float(start_cash),
        "positions": {},
        "pending": None,
        "inception": None,
        "last_date": None,
        "curve": [],  # [date, equity, mode]
        "trades": [],
        "trade_count": 0,
        "cost_paid": 0.0,
        "traded_notional": 0.0,
        "last_targets": {},
        "last_tilt_key": None,
        "since_rebalance": 10**6,  # first decision is always "due"
    }


def equity(acct: Dict[str, Any], book: PriceBook, d: str) -> float:
    total = acct["cash"]
    for sym, shares in acct["positions"].items():
        px = book.close_on(sym, d)
        if px:
            total += shares * px
    return total


def current_weights(acct: Dict[str, Any], book: PriceBook, d: str) -> Dict[str, float]:
    eq = equity(acct, book, d)
    if eq <= 0:
        return {}
    out = {}
    for sym, shares in acct["positions"].items():
        px = book.close_on(sym, d)
        if px:
            out[sym] = shares * px / eq
    return out


def _placebo_symbol(seed: str, sym: str, symbols: List[str]) -> str:
    """The symbol whose real signal history stands in for `sym`: a cyclic shift
    of the sorted universe by a seeded amount (never 0, so never itself)."""
    n = len(symbols)
    if n < 2 or sym not in symbols:
        return sym
    k = 1 + int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % (n - 1)
    return symbols[(symbols.index(sym) + k) % n]


def _target_weights(acct: Dict[str, Any], book: PriceBook, d: str) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, str]]:
    """The weights this account wants to hold after seeing day d's close.
    Returns (weights, human-readable reasons, raw signal per symbol)."""
    strategy = acct["strategy"]
    if strategy == "cash":
        return {}, {}, {}
    invested, base = acct["invested"], acct["weights"]
    if strategy == "static_hold":
        return {s: invested * w for s, w in base.items()}, {s: "strategic weight" for s in base}, {s: "HOLD" for s in base}

    raw: Dict[str, float] = {}
    reasons: Dict[str, str] = {}
    sigs: Dict[str, str] = {}
    symbols = book.symbols
    for sym, w in base.items():
        if strategy == "static_rebalanced":
            sig, conf = "HOLD", 50.0
        elif strategy == "random_tilt":
            sig, conf = book.signal_at(_placebo_symbol(acct["id"], sym, symbols), d)
        else:
            sig, conf = book.signal_at(sym, d)
        sigs[sym] = sig
        raw[sym] = invested * w * TILT[sig]
        reasons[sym] = f"{sig} ({conf:.0f}%)" if strategy == "engine_tilt" else ("policy weight" if strategy == "static_rebalanced" else f"placebo {sig}")
    total = sum(raw.values())
    if total > 1.0:
        raw = {s: v / total for s, v in raw.items()}
    policy = RISK_POLICY.get(acct.get("risk_level") or "")
    if policy:
        raw = {s: min(v, max(policy["max_position"], invested * base[s])) for s, v in raw.items()}
    return raw, reasons, sigs


def _record_trade(acct: Dict[str, Any], d: str, sym: str, side: str, shares: float, price: float, cost: float, reason: str) -> None:
    acct["trade_count"] += 1
    acct["cost_paid"] += cost
    acct["traded_notional"] += shares * price
    acct["trades"].append(
        {"date": d, "symbol": sym, "side": side, "shares": round(shares, 6), "price": round(price, 4), "cost": round(cost, 2), "reason": reason}
    )
    if len(acct["trades"]) > MAX_STORED_TRADES:
        del acct["trades"][: len(acct["trades"]) - MAX_STORED_TRADES]


def _execute_pending(acct: Dict[str, Any], book: PriceBook, d: str) -> None:
    pend, acct["pending"] = acct["pending"], None
    if not pend:
        return
    targets, reasons = pend["weights"], pend.get("reasons", {})
    eq = equity(acct, book, d)
    if eq <= 0:
        return
    bps = COMMISSION_BPS / 10_000.0
    sells: List[Tuple[str, float, float]] = []
    buys: List[Tuple[str, float, float]] = []
    for sym in set(acct["positions"]) | set(targets):
        price = book.close.get(sym, {}).get(d)  # tradable only on a day it actually printed
        if not price:
            continue
        held_value = acct["positions"].get(sym, 0.0) * price
        delta = targets.get(sym, 0.0) * eq - held_value
        if abs(delta) < max(1.0, MIN_TRADE_FRACTION * eq):
            continue
        (sells if delta < 0 else buys).append((sym, delta, price))

    for sym, delta, price in sells:
        shares = min(-delta / price, acct["positions"].get(sym, 0.0))
        proceeds = shares * price
        cost = proceeds * bps
        acct["cash"] += proceeds - cost
        left = acct["positions"].get(sym, 0.0) - shares
        if left > 1e-9:
            acct["positions"][sym] = left
        else:
            acct["positions"].pop(sym, None)
        _record_trade(acct, d, sym, "SELL", shares, price, cost, reasons.get(sym, "rebalance"))

    want = sum(delta for _s, delta, _p in buys)
    if want > 0:
        scale = min(1.0, acct["cash"] / (want * (1 + bps)))  # never spend cash we don't have
        for sym, delta, price in buys:
            notional = delta * scale
            if notional < 1.0:
                continue
            shares = notional / price
            cost = notional * bps
            acct["cash"] -= notional + cost
            acct["positions"][sym] = acct["positions"].get(sym, 0.0) + shares
            _record_trade(acct, d, sym, "BUY", shares, price, cost, reasons.get(sym, "rebalance"))


def _decide(acct: Dict[str, Any], book: PriceBook, d: str) -> None:
    if acct["strategy"] == "cash":
        return
    if acct["strategy"] == "static_hold":
        if acct["inception"] == d:  # buy once, on the first day only
            targets, reasons, _ = _target_weights(acct, book, d)
            acct["pending"] = {"weights": targets, "reasons": reasons, "decided": d}
            acct["last_targets"] = targets
        return
    targets, reasons, sigs = _target_weights(acct, book, d)
    acct["last_targets"] = targets
    tilt_key = "|".join(f"{s}:{sigs[s]}" for s in sorted(sigs))
    first = acct["last_tilt_key"] is None
    changed = tilt_key != acct["last_tilt_key"]
    now = current_weights(acct, book, d)
    drift = max((abs(targets.get(s, 0.0) - now.get(s, 0.0)) for s in set(targets) | set(now)), default=0.0)
    due = acct["since_rebalance"] >= REBALANCE_DAYS and drift > DRIFT_THRESHOLD
    if first or changed or due:
        acct["pending"] = {"weights": targets, "reasons": reasons, "decided": d}
        acct["last_tilt_key"] = tilt_key
        acct["since_rebalance"] = 0


def advance(
    acct: Dict[str, Any],
    book: PriceBook,
    *,
    live_from: str,
    upto: Optional[str] = None,
    start: Optional[str] = None,
) -> int:
    """Process every trading day after the account's last processed date (or
    from `start` for a new account) through `upto` (default: latest data).
    Idempotent: calling it again with nothing new processes nothing. Returns
    the number of days processed."""
    upto = upto or book.latest_date
    if upto is None:
        return 0
    if acct["last_date"] is not None:
        lo = bisect.bisect_right(book.dates, acct["last_date"])
    else:
        lo = bisect.bisect_left(book.dates, start) if start else 0
    hi = bisect.bisect_right(book.dates, upto)
    processed = 0
    for d in book.dates[lo:hi]:
        if acct["inception"] is None:
            acct["inception"] = d
        acct["since_rebalance"] += 1
        _execute_pending(acct, book, d)
        acct["curve"].append([d, round(equity(acct, book, d), 2), "live" if d >= live_from else "backtest"])
        _decide(acct, book, d)
        acct["last_date"] = d
        processed += 1
    return processed


# ----------------------------------------------------------------- metrics --


def _returns(values: List[float]) -> List[float]:
    return [b / a - 1 for a, b in zip(values, values[1:]) if a > 0]


def max_drawdown(values: List[float]) -> float:
    peak, worst = float("-inf"), 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1)
    return worst


def sharpe(values: List[float]) -> float:
    r = _returns(values)
    if len(r) < 2:
        return 0.0
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / (len(r) - 1)
    return 0.0 if var <= 0 else mean / math.sqrt(var) * math.sqrt(TRADING_DAYS)


def annual_volatility(values: List[float]) -> float:
    r = _returns(values)
    if len(r) < 2:
        return 0.0
    mean = sum(r) / len(r)
    return math.sqrt(sum((x - mean) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(TRADING_DAYS)


def summarize(acct: Dict[str, Any], bench: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Leaderboard row: total and live-only return, risk, cost, and alpha vs
    the account's benchmark over the same dates."""
    curve = acct["curve"]
    values = [p[1] for p in curve]
    last = values[-1] if values else acct["start_cash"]
    total = last / acct["start_cash"] - 1
    live_pts = [p for p in curve if p[2] == "live"]
    live_ret: Optional[float] = None
    if live_pts:
        bt = [p for p in curve if p[2] == "backtest"]
        base = bt[-1][1] if bt else acct["start_cash"]
        live_ret = last / base - 1
    years = max(len(values) / TRADING_DAYS, 1e-9)
    out = {
        "id": acct["id"],
        "name": acct["name"],
        "kind": acct["kind"],
        "strategy": acct["strategy"],
        "username": acct.get("username"),
        "risk_level": acct.get("risk_level"),
        "profile": acct.get("profile") or {},
        "equity": round(last, 2),
        "total_return": total,
        "cagr": (last / acct["start_cash"]) ** (1 / years) - 1 if last > 0 and len(values) > 20 else None,
        "live_return": live_ret,
        "max_drawdown": max_drawdown(values),
        "sharpe": sharpe(values),
        "volatility": annual_volatility(values),
        "trade_count": acct["trade_count"],
        "cost_paid": round(acct["cost_paid"], 2),
        "turnover": acct["traded_notional"] / acct["start_cash"] / years,  # annualised, in multiples of starting capital
        "days": len(values),
        "live_days": len(live_pts),
        "inception": acct["inception"],
        "last_date": acct["last_date"],
        "cash_weight": (acct["cash"] / last) if last else 1.0,
        "benchmark_id": acct.get("benchmark_id"),
        "alpha": None,
        "live_alpha": None,
    }
    if bench and bench["curve"]:
        b_last = bench["curve"][-1][1]
        out["benchmark_return"] = b_last / bench["start_cash"] - 1
        out["alpha"] = total - out["benchmark_return"]
        b_live = [p for p in bench["curve"] if p[2] == "live"]
        if live_ret is not None and b_live:
            b_bt = [p for p in bench["curve"] if p[2] == "backtest"]
            b_base = b_bt[-1][1] if b_bt else bench["start_cash"]
            out["live_alpha"] = live_ret - (b_last / b_base - 1)
    return out


# --------------------------------------------------------------- scorecard --


def signal_scorecard(book: PriceBook, horizons: Tuple[int, ...] = (1, 5, 20)) -> Dict[str, Any]:
    """How good has the engine's signal been? For every historical BUY / SELL /
    HOLD, the forward return over each horizon, measured the way the paper
    trader would trade it (enter at the NEXT day's close). Reported against the
    unconditional average so a signal's edge is visible, not just its sign.
    IN-SAMPLE, like the backtest (parameters were fitted on this history)."""
    stats: Dict[str, Dict[int, List[float]]] = {s: {h: [] for h in horizons} for s in ("BUY", "SELL", "HOLD", "ALL")}
    per_symbol: Dict[str, Dict[str, Dict[int, List[float]]]] = {}
    for sym in book.symbols:
        dates = book._sorted_dates[sym]
        closes = book.close[sym]
        sigs = book.signal[sym]
        per_symbol[sym] = {s: {h: [] for h in horizons} for s in ("BUY", "SELL", "HOLD")}
        for i, d in enumerate(dates):
            sig = sigs.get(d, ("HOLD", 50.0, 50.0))[0]
            for h in horizons:
                if i + 1 + h >= len(dates):
                    continue
                entry, exit_ = closes[dates[i + 1]], closes[dates[i + 1 + h]]
                r = exit_ / entry - 1
                stats[sig][h].append(r)
                stats["ALL"][h].append(r)
                per_symbol[sym][sig][h].append(r)

    def agg(vals: List[float], signal: str) -> Dict[str, Any]:
        if not vals:
            return {"n": 0, "mean_return": None, "hit_rate": None}
        mean = sum(vals) / len(vals)
        if signal == "BUY":
            hit = sum(1 for v in vals if v > 0) / len(vals)
        elif signal == "SELL":
            hit = sum(1 for v in vals if v < 0) / len(vals)
        else:
            hit = sum(1 for v in vals if v > 0) / len(vals)  # share of up-moves
        return {"n": len(vals), "mean_return": mean, "hit_rate": hit}

    overall = {
        sig: {str(h): agg(stats[sig][h], sig if sig != "ALL" else "HOLD") for h in horizons} for sig in ("BUY", "SELL", "HOLD", "ALL")
    }
    edge = {}
    for sig in ("BUY", "SELL"):
        edge[sig] = {}
        for h in horizons:
            m, base = overall[sig][str(h)]["mean_return"], overall["ALL"][str(h)]["mean_return"]
            # BUY edge = mean above average; SELL edge = mean BELOW average (a good sell avoids gains)
            edge[sig][str(h)] = None if m is None or base is None else (m - base if sig == "BUY" else base - m)
    return {
        "horizons": list(horizons),
        "signals": overall,
        "edge_vs_average": edge,
        "by_symbol": {
            sym: {sig: {str(h): agg(per_symbol[sym][sig][h], sig) for h in horizons} for sig in ("BUY", "SELL", "HOLD")} for sym in book.symbols
        },
        "in_sample": True,
        "as_of": book.latest_date,
    }
