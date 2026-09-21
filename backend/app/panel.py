"""The labelled matrix store: every field on ONE (dates x symbols) grid.

Prices, returns, engine signals, risk and the committee's decisions used to live in different shapes
(dicts of dicts, lists of JSON documents). A Panel holds each field as a float array of shape
(T dates, S symbols), with the date and symbol labels next to it, so that:

  * a PATH is a column slice:            panel.path("close", "NVDA", "2026-01-01")
  * a cross-section is a row slice:      panel.at("risk_score", "2026-09-18")
  * CORRELATION is one matrix product:   panel.corr("2026-09-18", 60)
  * a NEW DESIGN is a weights matrix:    panel.portfolio_path(W)  -> a daily return path and equity curve

Missing is NaN, never a fake zero, except where a function says otherwise (correlation treats a missing
return as 0, exactly like app/associations.py, and a test proves the two agree). Everything is aligned by
construction, so a strategy cannot accidentally pair one symbol's Tuesday with another's Wednesday.

portfolio_path is lookahead-safe by construction: the weights in row t are what you decided at the close of
day t, and they earn the return of day t+1. To keep the design honest it also charges trading costs on the
turnover, because a design that ignores costs looks better than it is.

Inference fields (committee decisions and a per-agent lean cube) come from with_inference(); together with
the daily snapshots (app/snapshots.py) they keep what the system BELIEVED, not just what happened.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from . import risk

MAX_GAP_DAYS = 5
SIGNAL_CODE = {"SELL": -1.0, "HOLD": 0.0, "BUY": 1.0}
RISK_CODE = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 2.0}
FIELDS_MARKET = ("close", "ret", "signal", "signal_conf", "rsi", "risk_score", "risk_level", "drawdown", "vol")


@dataclass
class Panel:
    dates: List[str]
    symbols: List[str]
    fields: Dict[str, np.ndarray]
    version: str = ""
    agents: List[str] = field(default_factory=list)
    agent_lean: Optional[np.ndarray] = None  # (T, S, A): +1 BUY, 0 HOLD, -1 SELL, NaN did not answer

    # ------------------------------------------------------------------ labels --
    def row(self, d: str) -> Optional[int]:
        i = bisect.bisect_left(self.dates, d)
        return i if i < len(self.dates) and self.dates[i] == d else None

    def row_le(self, d: str) -> Optional[int]:
        """The last row on or before `d` (a date with no bar maps to the bar before it)."""
        i = bisect.bisect_right(self.dates, d) - 1
        return i if i >= 0 else None

    def col(self, sym: str) -> int:
        return self.symbols.index(sym)

    # --------------------------------------------------------------- retrieval --
    def path(self, name: str, sym: str, start: Optional[str] = None, end: Optional[str] = None, dropna: bool = True) -> Tuple[List[str], np.ndarray]:
        """One symbol's field over time (a column slice)."""
        lo = bisect.bisect_left(self.dates, start) if start else 0
        hi = bisect.bisect_right(self.dates, end) if end else len(self.dates)
        vals = self.fields[name][lo:hi, self.col(sym)]
        ds = self.dates[lo:hi]
        if dropna:
            keep = ~np.isnan(vals)
            return [d for d, k in zip(ds, keep) if k], vals[keep]
        return ds, vals

    def at(self, name: str, d: str) -> Dict[str, float]:
        """Every symbol's value on one date (a row slice), NaN dropped."""
        i = self.row_le(d)
        if i is None:
            return {}
        return {s: float(v) for s, v in zip(self.symbols, self.fields[name][i]) if not np.isnan(v)}

    def window(self, name: str, end: str, n: int) -> np.ndarray:
        """The last `n` rows of a field up to and including `end`, shape (n', S)."""
        i = self.row_le(end)
        if i is None:
            return np.empty((0, len(self.symbols)))
        return self.fields[name][max(0, i + 1 - n): i + 1]

    def frame(self, name: str) -> pd.DataFrame:
        return pd.DataFrame(self.fields[name], index=pd.Index(self.dates, name="date"), columns=self.symbols)

    def slice_dates(self, start: Optional[str] = None, end: Optional[str] = None) -> "Panel":
        lo = bisect.bisect_left(self.dates, start) if start else 0
        hi = bisect.bisect_right(self.dates, end) if end else len(self.dates)
        return Panel(self.dates[lo:hi], self.symbols, {k: v[lo:hi] for k, v in self.fields.items()}, self.version, self.agents, None if self.agent_lean is None else self.agent_lean[lo:hi])

    # ------------------------------------------------------------------- maths --
    def corr(self, end: str, window: int = 60) -> np.ndarray:
        """Pearson correlation of daily returns over the last `window` rows up to `end`, all symbols at once.
        A missing return counts as 0 (the same convention as app/associations.py); a flat series correlates 0."""
        R = np.nan_to_num(self.window("ret", end, window), nan=0.0)
        S = len(self.symbols)
        if R.shape[0] < 3:
            return np.zeros((S, S))
        X = R - R.mean(axis=0)
        ss = (X * X).sum(axis=0)
        denom = np.sqrt(np.outer(ss, ss))
        with np.errstate(invalid="ignore", divide="ignore"):
            C = np.where(denom > 0, (X.T @ X) / denom, 0.0)
        np.fill_diagonal(C, 1.0)
        return C

    def portfolio_path(self, weights: Union[np.ndarray, Dict[str, Sequence[float]]], cost_bps: float = 5.0) -> Dict[str, Any]:
        """Evaluate a design. `weights[t, s]` is what you hold AFTER the close of day t; it earns day t+1's return.
        Trading costs are charged on turnover. Returns {"ret", "equity", "turnover", "total_return", "sharpe", "max_drawdown"}."""
        W = self._weights(weights)
        R = np.nan_to_num(self.fields["ret"], nan=0.0)
        T = R.shape[0]
        held = np.vstack([np.zeros((1, W.shape[1])), W[:-1]])  # decided yesterday, earns today
        gross = (held * R).sum(axis=1)
        turnover = np.abs(np.diff(np.vstack([np.zeros((1, W.shape[1])), held]), axis=0)).sum(axis=1)
        net = gross - turnover * cost_bps / 1e4
        equity = np.cumprod(1.0 + net)
        peak = np.maximum.accumulate(equity)
        sd = net.std(ddof=1) if T > 2 else 0.0
        return {
            "ret": net,
            "equity": equity,
            "turnover": turnover,
            "total_return": float(equity[-1] - 1.0) if T else 0.0,
            "sharpe": float(net.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "max_drawdown": float((equity / peak - 1.0).min()) if T else 0.0,
        }

    def _weights(self, weights: Union[np.ndarray, Dict[str, Sequence[float]]]) -> np.ndarray:
        if isinstance(weights, dict):
            W = np.zeros((len(self.dates), len(self.symbols)))
            for s, col in weights.items():
                W[:, self.col(s)] = np.asarray(col, dtype=float)
        else:
            W = np.asarray(weights, dtype=float)
        if W.shape != (len(self.dates), len(self.symbols)):
            raise ValueError(f"weights must be shape {(len(self.dates), len(self.symbols))}, got {W.shape}")
        if np.isnan(W).any():
            raise ValueError("weights contain NaN: say 0 for 'no position'")
        return W

    # ---------------------------------------------------------------- inference --
    def with_inference(self, runs: List[Dict[str, Any]]) -> "Panel":
        """Add the committee's stored decisions as matrices: committee_code (+1/0/-1, NaN none), committee_consensus,
        committee_answered, and the agent_lean cube (T, S, A)."""
        T, S = len(self.dates), len(self.symbols)
        code, cons, ans = (np.full((T, S), np.nan) for _ in range(3))
        agents = sorted({a["agent"] for r in runs for a in r.get("agents", []) if a.get("agent")})
        cube = np.full((T, S, len(agents)), np.nan) if agents else None
        for r in runs:
            i = self.row(r.get("date", ""))
            if i is None or r.get("symbol") not in self.symbols:
                continue
            j = self.col(r["symbol"])
            action = r.get("action") or (r.get("decision") if r.get("quorum_ok") else None)
            if action in SIGNAL_CODE:
                code[i, j] = SIGNAL_CODE[action]
            ceo = r.get("ceo") or {}
            if ceo.get("consensus") is not None:
                cons[i, j] = ceo["consensus"]
            ans[i, j] = r.get("answered", np.nan)
            for a in r.get("agents", []):
                if a.get("ok") and a.get("lean") in SIGNAL_CODE and cube is not None:
                    cube[i, j, agents.index(a["agent"])] = SIGNAL_CODE[a["lean"]]
        fields = dict(self.fields, committee_code=code, committee_consensus=cons, committee_answered=ans)
        return Panel(self.dates, self.symbols, fields, self.version, agents, cube)

    def to_payload(self, names: Sequence[str], symbols: Optional[Sequence[str]] = None, days: Optional[int] = None) -> Dict[str, Any]:
        """JSON-ready labelled arrays (NaN -> null) for the API."""
        lo = max(0, len(self.dates) - days) if days else 0
        syms = list(symbols) if symbols else self.symbols
        out: Dict[str, Any] = {"dates": self.dates[lo:], "symbols": syms, "fields": {}}
        for n in names:
            if n not in self.fields:
                raise KeyError(n)
            block = self.fields[n][lo:][:, [self.col(s) for s in syms]]
            out["fields"][n] = [[None if np.isnan(v) else round(float(v), 6) for v in row] for row in block]
        return out


# ------------------------------------------------------------------- building --


def from_book(book: Any) -> Panel:
    """The panel for a PriceBook (cached on the book: one build per data version)."""
    cached = book.__dict__.get("_panel")
    if cached is not None:
        return cached
    dates, symbols = list(book.dates), list(book.symbols)
    T, S = len(dates), len(symbols)
    idx = {d: i for i, d in enumerate(dates)}
    f = {k: np.full((T, S), np.nan) for k in FIELDS_MARKET}
    for j, s in enumerate(symbols):
        for d, px in book.close[s].items():
            f["close"][idx[d], j] = px
        for d, (sig, conf, rsi) in book.signal.get(s, {}).items():
            if d in idx:
                f["signal"][idx[d], j] = SIGNAL_CODE.get(sig, 0.0)
                f["signal_conf"][idx[d], j] = conf
                f["rsi"][idx[d], j] = rsi
        rdates, series = risk.series_for(book, s)
        for d, r in zip(rdates, series):
            if r is not None and d in idx:
                i = idx[d]
                f["risk_score"][i, j], f["risk_level"][i, j] = r["score"], RISK_CODE[r["level"]]
                f["drawdown"][i, j], f["vol"][i, j] = r["drawdown"], r["vol"]
    # daily returns on the shared calendar: NaN where a bar is missing or the step spans a hole in the data
    close_ff = pd.DataFrame(f["close"]).ffill().to_numpy()
    prev = np.vstack([np.full((1, S), np.nan), close_ff[:-1]])
    with np.errstate(invalid="ignore", divide="ignore"):
        ret = close_ff / prev - 1.0
    gap = np.array([False] + [(date.fromisoformat(b) - date.fromisoformat(a)).days > MAX_GAP_DAYS for a, b in zip(dates, dates[1:])])
    ret[gap, :] = np.nan
    ret[np.isnan(f["close"])] = np.nan  # a symbol with no bar that day has no return that day
    f["ret"] = ret
    panel = Panel(dates, symbols, f, version=f"{dates[-1] if dates else 'none'}|{T}")
    book.__dict__["_panel"] = panel
    return panel
