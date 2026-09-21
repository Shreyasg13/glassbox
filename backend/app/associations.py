"""How the tracked stocks move together: correlations, clusters, market cohesion, lead-lag.

Purely deterministic arithmetic on the price history (no model, no fitted parameters), recomputed
from the data every day, so it is always current and needs no storage. It exists to give the
committee and the admin context that a single-symbol view hides:

  * peers      -- who does this stock actually move with today (and what are THEY signalling)?
  * clusters   -- groups of names that behave as one bet (diversification that is only apparent)
  * cohesion   -- how much everything is moving together now, against its own history; when it is
                  high, holding many names buys less diversification than it looks
  * lead-lag   -- does one name reliably move before another?

Lead-lag is where a "self-discovering" system fools itself: 15 stocks make 210 ordered pairs x 5
lags = 1,050 tests, and at a 5% level ~50 of them would look "significant" by pure chance. A textbook
correction (Bonferroni on a bell-curve p-value) is not enough either: real returns have fat tails and
volatility clustering, which make chance correlations bigger than a bell curve predicts -- an earlier
version of this scan "discovered" a relationship in pure noise for exactly that reason. So the bar is
set empirically: every series is shuffled independently (circular shifts, which keep its own
volatility clustering but destroy any relationship between series), the LARGEST lagged correlation
anywhere across all pairs and lags is recorded, and a relationship is only reported if it beats the
95th percentile of that maximum. On daily bars between liquid large caps the honest usual answer is
"none".
"""
from __future__ import annotations

import bisect
import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

MAX_GAP_DAYS = 5  # calendar days between consecutive bars above which the data has a hole
CORR_WINDOW = 60  # trading days for correlations and cohesion
CLUSTER_THRESHOLD = 0.70  # single-link: two names this correlated are treated as one group
CROWDED_MIN_CORR = 0.30  # average pairwise correlation below this is never 'crowded'
COHESION_HISTORY_DAYS = 750  # how far back "its own history" reaches
COHESION_STEP = 21
LEAD_LAG_WINDOW = 252
MAX_LAG = 5
ALPHA = 0.05
LEAD_LAG_PERMUTATIONS = 400
LEAD_LAG_SEED = 20260921  # fixed, so the same data always gives the same answer


def _pearson(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 3 or n != len(y):
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def aligned_returns(book: Any, d: str, window: int = CORR_WINDOW, symbols: Optional[List[str]] = None) -> Dict[str, List[float]]:
    """Daily returns for each symbol over the last `window` trading days up to and including d, on the
    common calendar (a symbol that skipped a day carries its last price, so its return that day is 0).
    Symbols without enough history are left out."""
    syms = symbols or book.symbols
    key = (tuple(syms), d, window)
    cache = book.__dict__.setdefault("_assoc_cache", {})
    if key in cache:
        return cache[key]
    end = bisect.bisect_right(book.dates, d)
    days = book.dates[max(0, end - window - 1): end]
    out: Dict[str, List[float]] = {}
    if len(days) >= min(30, window):
        prev = {s: book.close_on(s, days[0]) for s in syms}
        rets: Dict[str, List[float]] = {s: [] for s in syms if prev[s]}
        for k, day in enumerate(days[1:], start=1):
            # a hole in the data (a week or more of missing bars) turns the next "daily" return into a multi-week
            # move that hits every symbol at once and swamps every correlation: treat it as unknown (0), not as a day
            gap = (date.fromisoformat(day) - date.fromisoformat(days[k - 1])).days > MAX_GAP_DAYS
            for s in rets:
                px = book.close.get(s, {}).get(day)
                if px and prev[s]:
                    rets[s].append(0.0 if gap else px / prev[s] - 1)
                    prev[s] = px
                else:
                    rets[s].append(0.0)
        out = rets
    cache[key] = out
    return out


def correlations(book: Any, d: str, window: int = CORR_WINDOW) -> Dict[str, Dict[str, float]]:
    rets = aligned_returns(book, d, window)
    syms = sorted(rets)
    return {a: {b: (1.0 if a == b else _pearson(rets[a], rets[b])) for b in syms} for a in syms}


def top_peers(corr: Dict[str, Dict[str, float]], sym: str, k: int = 3) -> List[Tuple[str, float]]:
    row = corr.get(sym, {})
    return sorted(((b, r) for b, r in row.items() if b != sym), key=lambda t: -t[1])[:k]


def clusters(corr: Dict[str, Dict[str, float]], threshold: float = CLUSTER_THRESHOLD) -> List[List[str]]:
    """Connected groups (single link): names joined by a correlation at or above `threshold`."""
    syms = sorted(corr)
    parent = {s: s for s in syms}

    def find(s: str) -> str:
        while parent[s] != s:
            parent[s] = parent[parent[s]]
            s = parent[s]
        return s

    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            if corr[a][b] >= threshold:
                parent[find(a)] = find(b)
    groups: Dict[str, List[str]] = {}
    for s in syms:
        groups.setdefault(find(s), []).append(s)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g))


def _mean_pairwise(corr: Dict[str, Dict[str, float]]) -> Optional[float]:
    syms = sorted(corr)
    vals = [corr[a][b] for i, a in enumerate(syms) for b in syms[i + 1:]]
    return sum(vals) / len(vals) if vals else None


def cohesion(book: Any, d: str) -> Dict[str, Any]:
    """Average pairwise correlation now, and where that sits in its own past (percentile)."""
    now = _mean_pairwise(correlations(book, d))
    if now is None:
        return {"value": None, "percentile": None, "label": "n/a", "samples": 0}
    end = bisect.bisect_right(book.dates, d) - 1
    samples: List[float] = []
    i = end - COHESION_STEP
    while i >= max(CORR_WINDOW + 1, end - COHESION_HISTORY_DAYS):
        v = _mean_pairwise(correlations(book, book.dates[i]))
        if v is not None:
            samples.append(v)
        i -= COHESION_STEP
    if len(samples) < 8:
        return {"value": now, "percentile": None, "label": "n/a", "samples": len(samples)}
    pct = 100.0 * sum(1 for v in samples if v <= now) / len(samples)
    # "crowded" is about everything moving together, so a high percentile alone is not enough: the level must be high too
    label = "crowded" if pct >= 80 and now >= CROWDED_MIN_CORR else "diversifying" if pct <= 20 else "normal"
    return {"value": now, "percentile": pct, "label": label, "samples": len(samples)}


def lead_lag_scan(book: Any, d: str, window: int = LEAD_LAG_WINDOW, max_lag: int = MAX_LAG, alpha: float = ALPHA, permutations: int = LEAD_LAG_PERMUTATIONS) -> Dict[str, Any]:
    """Does any name's return today predict another's over the next 1..max_lag days? Every ordered pair and
    lag is tested; a finding is kept only if its correlation beats the (1-alpha) quantile of the LARGEST
    lagged correlation found in `permutations` independently shuffled copies of the same data."""
    rets = aligned_returns(book, d, window + max_lag)
    syms = sorted(rets)
    n_tests = len(syms) * (len(syms) - 1) * max_lag
    out: Dict[str, Any] = {"tests": n_tests, "window": window, "findings": [], "threshold_r": None, "method": "max-statistic over shuffled copies, rank-based"}
    if n_tests == 0:
        return out
    R = np.array([rets[s] for s in syms], dtype=float).T  # days x symbols
    T = R.shape[0]
    if T - max_lag < 60:
        out["note"] = "not enough history"
        return out
    # Rank-transform each series first (Spearman-style). Real returns contain single-day jumps (earnings moves of
    # 10-15%); under plain correlation one such day is worth ~15 standard deviations, so two jumps that happen to
    # line up in a shuffled copy alone produce r near 1, the significance bar balloons to ~0.8, and the scan
    # becomes blind. By rank a jump is simply "the biggest day", so the bar reflects ordinary chance (~0.25).
    R = pd.DataFrame(R).rank(axis=0).to_numpy(dtype=float)
    sd = R.std(axis=0)
    Z = (R - R.mean(axis=0)) / np.where(sd > 0, sd, 1.0)
    S = len(syms)
    off_diag = ~np.eye(S, dtype=bool)

    def lagged(M: "np.ndarray") -> "np.ndarray":  # [lag-1][a, b] = corr(a today, b `lag` days later)
        return np.stack([M[: T - k].T @ M[k:] / (T - k) for k in range(1, max_lag + 1)])

    obs = lagged(Z)
    rng = np.random.default_rng(LEAD_LAG_SEED)
    null_max = np.empty(permutations)
    for i in range(permutations):
        shifts = rng.integers(max_lag + 1, T - max_lag - 1, size=S)  # every series moved by its own amount
        shuffled = np.column_stack([np.roll(Z[:, j], int(shifts[j])) for j in range(S)])
        null_max[i] = np.abs(lagged(shuffled)[:, off_diag]).max()
    thr = float(np.quantile(null_max, 1 - alpha))
    out["threshold_r"] = thr
    for a in range(S):
        for b in range(S):
            if a == b:
                continue
            lag = int(np.argmax(np.abs(obs[:, a, b])))
            r = float(obs[lag, a, b])
            if abs(r) >= thr:
                out["findings"].append({"leader": syms[a], "follower": syms[b], "lag_days": lag + 1, "r": r})
    out["findings"].sort(key=lambda f: -abs(f["r"]))
    return out


def association_report(book: Any, d: str) -> Dict[str, Any]:
    """Everything above for one day, in one serialisable block."""
    corr = correlations(book, d)
    syms = sorted(corr)
    pairs = sorted(((corr[a][b], a, b) for i, a in enumerate(syms) for b in syms[i + 1:]), reverse=True)
    return {
        "date": d,
        "window_days": CORR_WINDOW,
        "symbols": len(syms),
        "cohesion": cohesion(book, d),
        "clusters": clusters(corr),
        "strongest_pairs": [{"a": a, "b": b, "r": r} for r, a, b in pairs[:5]],
        "weakest_pairs": [{"a": a, "b": b, "r": r} for r, a, b in pairs[-3:][::-1]],
        "lead_lag": lead_lag_scan(book, d),
    }


def peer_context(book: Any, sym: str, d: str, k: int = 3) -> Optional[str]:
    """One prompt line for the committee: who this stock moves with, what those peers are signalling,
    and whether the whole market is moving as one. None when there is not enough history."""
    try:
        corr = correlations(book, d)
        if sym not in corr or len(corr) < 3:
            return None
        peers = top_peers(corr, sym, k)
        parts = []
        for p, r in peers:
            sig = book.signal_at(p, d)[0]
            parts.append(f"{p} (correlation {r:+.2f}, engine {sig})")
        line = f"Moves most with: {', '.join(parts)} over the last {CORR_WINDOW} days."
        c = cohesion(book, d)
        if c["label"] in ("crowded", "diversifying"):
            line += f" Market cohesion is {c['label']} ({c['percentile']:.0f}th percentile of its own history)."
        group = next((g for g in clusters(corr) if sym in g), None)
        if group:
            line += f" It trades as one group with {', '.join(x for x in group if x != sym)}: these are largely one bet, not several."
        return line
    except Exception:  # noqa: BLE001 -- context is a nicety; never let it break a review
        return None
