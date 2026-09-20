"""The risk signal: a plain, rule-based read of how dangerous a symbol looks TODAY.

No parameter here is fitted to history and nothing looks ahead: every input for day i
uses closes up to and including day i only, and the volatility percentile is ranked
against the symbol's own PAST volatilities. That matters because it means the scorecard
below can grade the signal over the whole history honestly -- unlike the engine's
BUY/SELL signal, whose parameters were tuned on the same data it is graded on.

score (0-100) = 45% volatility regime + 35% depth of drawdown + 20% trend break
  * volatility regime  -- 20-day annualised volatility, as a percentile of the symbol's own past
  * drawdown           -- distance below the trailing 252-day high, 20% down = full marks
  * trend break        -- price below its 200-day average
level: HIGH >= 66, LOW <= 33, otherwise MEDIUM (a symbol needs ~1 year of history to be rated).

Be clear-eyed about what this is: mostly a volatility-regime detector. Volatility is
persistent, so "HIGH risk now -> bigger moves next month" is expected and the scorecard
should confirm it; it does NOT predict direction, and it LAGS a sudden onset: the last calm days before a crash
still rate LOW, so it separates rough from calm far better in volatility than in worst-case dips.
The scorecard reports both, so the admin can see exactly how much to trust it.
"""
from __future__ import annotations

import bisect
import math
from typing import Any, Dict, List, Optional, Tuple

VOL_WINDOW = 20
DD_WINDOW = 252
TREND_WINDOW = 200
MIN_HISTORY = 252  # bars before a symbol is rated: the vol percentile needs a past to rank against
HIGH_AT, LOW_AT = 66.0, 33.0
W_VOL, W_DD, W_TREND = 0.45, 0.35, 0.20
FULL_DD = 0.20  # a 20% drawdown scores the full drawdown component
TRADING_DAYS = 252

# a "meaningful drop" over each forward horizon, for the scorecard
DROP_THRESHOLD = {5: 0.03, 20: 0.06}


def level_for(score: float) -> str:
    return "HIGH" if score >= HIGH_AT else "LOW" if score <= LOW_AT else "MEDIUM"


def _stdev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def compute_series(closes: List[float]) -> List[Optional[Dict[str, Any]]]:
    """Risk for every bar of a close series (None until MIN_HISTORY bars exist)."""
    n = len(closes)
    rets = [0.0] + [closes[i] / closes[i - 1] - 1 if closes[i - 1] > 0 else 0.0 for i in range(1, n)]
    past_vols: List[float] = []  # sorted; only PAST values, so ranking today's vol never peeks
    out: List[Optional[Dict[str, Any]]] = [None] * n
    for i in range(n):
        if i < VOL_WINDOW:
            continue
        vol = _stdev(rets[i - VOL_WINDOW + 1: i + 1]) * math.sqrt(TRADING_DAYS)
        pct = 100.0 * bisect.bisect_left(past_vols, vol) / len(past_vols) if past_vols else 50.0
        bisect.insort(past_vols, vol)
        if i + 1 < MIN_HISTORY:
            continue
        peak = max(closes[max(0, i - DD_WINDOW + 1): i + 1])
        dd = closes[i] / peak - 1 if peak > 0 else 0.0
        below = i + 1 >= TREND_WINDOW and closes[i] < sum(closes[i - TREND_WINDOW + 1: i + 1]) / TREND_WINDOW
        score = W_VOL * pct + W_DD * min(100.0, -dd / FULL_DD * 100.0) + W_TREND * (100.0 if below else 0.0)
        out[i] = {"score": round(score, 1), "level": level_for(score), "vol": round(vol, 4), "vol_pct": round(pct, 1), "drawdown": round(dd, 4), "below_ma200": bool(below)}
    return out


def series_for(book: Any, sym: str) -> Tuple[List[str], List[Optional[Dict[str, Any]]]]:
    """(dates, risk per date) for a PriceBook symbol, computed once per book."""
    cache = book.__dict__.setdefault("_risk_cache", {})
    if sym not in cache:
        dates = book._sorted_dates.get(sym) or []
        cache[sym] = (dates, compute_series([book.close[sym][d] for d in dates]) if dates else [])
    return cache[sym]


def risk_at(book: Any, sym: str, d: str) -> Optional[Dict[str, Any]]:
    dates, series = series_for(book, sym)
    i = bisect.bisect_left(dates, d)
    return series[i] if i < len(dates) and dates[i] == d else None


def risk_table(book: Any, d: str) -> List[Dict[str, Any]]:
    """Today's risk for every symbol, highest first -- the admin/user risk view."""
    rows = []
    for sym in book.symbols:
        r = risk_at(book, sym, d)
        if r:
            rows.append({"symbol": sym, **r})
    rows.sort(key=lambda r: -r["score"])
    return rows


# ---------------------------------------------------------------- scorecard --


def risk_scorecard(book: Any, horizons: Tuple[int, ...] = (5, 20)) -> Dict[str, Any]:
    """Did HIGH risk days really precede rougher weeks than LOW risk days?

    For every rated (symbol, day): the realised volatility, the worst dip below that
    day's close, and the return over the next `h` trading days, grouped by risk level.
    `lift` is HIGH divided by LOW -- above 1 means the signal separates calm from rough.
    Every number here is out-of-sample by construction (see the module docstring)."""
    buckets: Dict[str, Dict[int, Dict[str, List[float]]]] = {
        lv: {h: {"vol": [], "dip": [], "ret": [], "drop": []} for h in horizons} for lv in ("LOW", "MEDIUM", "HIGH", "ALL")
    }
    for sym in book.symbols:
        dates, series = series_for(book, sym)
        closes = [book.close[sym][d] for d in dates]
        n = len(closes)
        for i, r in enumerate(series):
            if r is None:
                continue
            for h in horizons:
                if i + h >= n:
                    continue
                path = closes[i: i + h + 1]
                fwd_rets = [path[k] / path[k - 1] - 1 for k in range(1, len(path)) if path[k - 1] > 0]
                dip = min(p / path[0] - 1 for p in path)
                vol = _stdev(fwd_rets) * math.sqrt(TRADING_DAYS)
                for key in (r["level"], "ALL"):
                    b = buckets[key][h]
                    b["vol"].append(vol)
                    b["dip"].append(dip)
                    b["ret"].append(path[-1] / path[0] - 1)
                    b["drop"].append(1.0 if dip <= -DROP_THRESHOLD.get(h, 0.05) else 0.0)

    def mean(xs: List[float]) -> Optional[float]:
        return sum(xs) / len(xs) if xs else None

    levels = {
        lv: {str(h): {"n": len(b["vol"]), "fwd_vol": mean(b["vol"]), "fwd_worst_dip": mean(b["dip"]), "fwd_return": mean(b["ret"]), "p_drop": mean(b["drop"])} for h, b in per_h.items()}
        for lv, per_h in buckets.items()
    }

    def ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
        return a / b if a is not None and b not in (None, 0) else None

    lift = {
        str(h): {
            "vol": ratio(levels["HIGH"][str(h)]["fwd_vol"], levels["LOW"][str(h)]["fwd_vol"]),
            "dip": ratio(levels["HIGH"][str(h)]["fwd_worst_dip"], levels["LOW"][str(h)]["fwd_worst_dip"]),
            "p_drop": ratio(levels["HIGH"][str(h)]["p_drop"], levels["LOW"][str(h)]["p_drop"]),
        }
        for h in horizons
    }
    return {
        "horizons": list(horizons),
        "drop_threshold": {str(h): DROP_THRESHOLD.get(h, 0.05) for h in horizons},
        "levels": levels,
        "lift": lift,
        "note": "Out-of-sample by construction (no fitted parameters). Mostly a volatility-regime detector: it says how rough it is likely to be, not which way.",
    }
