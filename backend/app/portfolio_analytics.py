"""Forward-looking and cross-user views built on the committee-run accounts (see portfolio_view.py):

  * monte_carlo(): a bootstrap ESTIMATE of where one account could be in 1 month / 1 quarter / 1 year.
  * agent_progress(): each committee member's record on ONE user's stocks.
  * validation_rows() / aggregate(): the admin's cross-user validation + inference dataset -- one row per
    (user, symbol, committee review) with what the engine and the committee said, whether the committee-run
    account acted on it, and the forward return once it has aged.

Read-only over stored data; nothing here trades or writes.
"""
from __future__ import annotations

import zlib
from typing import Any, Dict, List, Optional

from . import paper_cycle
from .portfolio_view import _ids, _money

MC_HORIZONS = (21, 63, 252)  # about 1 month, 1 quarter, 1 year of trading days
MC_SIMS = 2000
MC_MIN_RETURNS = 60
MC_FAN_POINTS = 60
FWD_HORIZONS = (1, 5, 20)
ACT_WINDOW = 2  # a committee call "acted" if the committee account traded that symbol within this many trading days


def monte_carlo(acct: Dict[str, Any], horizons=MC_HORIZONS, sims: int = MC_SIMS) -> Optional[Dict[str, Any]]:
    """Resample the account's own daily returns (with replacement) into `sims` futures. Seeded from the account
    and its last date, so the same data always draws the same picture (no flicker on refresh). It treats
    tomorrow as a random draw from the account's past, so it ignores regime shifts and volatility clustering:
    a range, not a forecast."""
    import numpy as np

    values = np.array([p[1] for p in acct["curve"]], dtype=float)
    if len(values) < MC_MIN_RETURNS + 1 or (values <= 0).any():
        return None
    rets = values[1:] / values[:-1] - 1
    last, start = float(values[-1]), float(acct["start_cash"])
    rng = np.random.default_rng(zlib.crc32(f"{acct['id']}|{acct.get('last_date')}".encode()))
    longest = max(horizons)
    growth = np.cumprod(1 + rng.choice(rets, size=(sims, longest)), axis=1)  # one set of futures, read at each horizon
    out: Dict[str, Any] = {"method": "bootstrap of this account's own daily returns", "simulations": sims, "based_on_days": int(len(rets)), "horizons": []}
    for h in horizons:
        final = last * growth[:, h - 1]
        p5, p25, p50, p75, p95 = (round(float(x), 2) for x in np.percentile(final, [5, 25, 50, 75, 95]))
        out["horizons"].append(
            {
                "days": int(h), "p5": p5, "p25": p25, "p50": p50, "p75": p75, "p95": p95,
                "prob_above_current": float((final > last).mean()),
                "prob_above_initial": float((final > start).mean()),
                "prob_loss_10pct": float((final < last * 0.9).mean()),
            }
        )
    step = max(1, longest // MC_FAN_POINTS)
    days = list(range(step, longest + 1, step))
    q = np.percentile(last * growth[:, [d - 1 for d in days]], [5, 50, 95], axis=0)
    out["fan"] = {"start": round(last, 2), "days": days, "p5": [round(float(x), 2) for x in q[0]], "p50": [round(float(x), 2) for x in q[1]], "p95": [round(float(x), 2) for x in q[2]]}
    return out


def agent_progress(symbols: List[str], book, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Committee members' record on THIS user's stocks only (same scoring as the admin-wide leaderboard)."""
    from . import strategy

    want = set(symbols)
    mine = [r for r in runs if r["symbol"] in want]
    board = strategy.agent_leaderboard(book, mine)
    return {"reviews": len(mine), "agents": board.get("agents", []), "note": board.get("note")}


def _direction(action: Optional[str]) -> int:
    return {"BUY": 1, "SELL": -1}.get(action or "", 0)


def _acted(trades: List[Dict[str, Any]], sym: str, d: str, dates: List[str]) -> bool:
    if d not in dates:
        return False
    i = dates.index(d)
    window = set(dates[i : i + ACT_WINDOW + 1])
    return any(t["symbol"] == sym and t["date"] in window for t in trades)


def validation_rows(users: List[Dict[str, Any]], book, runs: List[Dict[str, Any]], accounts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per (user, symbol, committee review). Forward returns are None until they have aged, never guessed."""
    from . import strategy

    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_symbol.setdefault(r["symbol"], []).append(r)
    rows = []
    for u in paper_cycle._cohort(users):
        acct = accounts.get(_ids(u["username"])["committee"])
        if not acct:
            continue
        cm_trades = [t for t in acct["trades"] if str(t["reason"]).startswith("committee")]
        for sym in acct["weights"]:
            for r in sorted(by_symbol.get(sym, []), key=lambda x: x["date"]):
                action = r.get("action") or r.get("decision")
                fwd = {f"fwd_{h}d": strategy._fwd_return(book, sym, r["date"], h) for h in FWD_HORIZONS}
                d5, eng = fwd["fwd_5d"], r.get("engine_signal")
                rows.append(
                    {
                        "user": u["username"], "archetype": (acct.get("profile") or {}).get("archetype"), "risk_level": acct.get("risk_level"),
                        "date": r["date"], "symbol": sym,
                        "engine_signal": eng, "committee_decision": r.get("decision"), "committee_action": action,
                        "consensus": (r.get("ceo") or {}).get("label"), "gated": bool(r.get("gate")),
                        "answered": r.get("answered"), "total": r.get("total"),
                        "disagrees_with_engine": bool(action and eng and action != eng),
                        "account_acted": _acted(cm_trades, sym, r["date"], book.dates),
                        **fwd,
                        "committee_edge_5d": d5 * _direction(action) if d5 is not None and _direction(action) else None,
                        "engine_edge_5d": d5 * _direction(eng) if d5 is not None and _direction(eng) else None,
                    }
                )
    return rows


def _mean(xs: List[Optional[float]]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def aggregate(users: List[Dict[str, Any]], book, runs: List[Dict[str, Any]], accounts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Every user side by side plus pooled totals: is the committee helping across the cohort, and is there yet
    enough evidence to say so? Early on there are few live days, and the response says so instead of implying more."""
    rows = validation_rows(users, book, runs, accounts)
    per_user, live_days = [], 0
    for u in paper_cycle._cohort(users):
        ids = _ids(u["username"])
        if not all(accounts.get(i) for i in ids.values()):
            continue
        c, e, b = (_money(accounts[ids[k]]) for k in ("committee", "engine", "benchmark"))
        mine = [r for r in rows if r["user"] == u["username"]]
        live_days = max(live_days, sum(1 for p in accounts[ids["committee"]]["curve"] if p[2] == "live"))
        per_user.append(
            {
                "username": u["username"], "archetype": (accounts[ids["committee"]].get("profile") or {}).get("archetype"),
                "risk_level": accounts[ids["committee"]].get("risk_level"),
                "committee_return": c["return"], "engine_return": e["return"], "benchmark_return": b["return"],
                "committee_live_return": c["live_return"], "engine_live_return": e["live_return"],
                "committee_added_dollars": round(c["final"] - e["final"], 2),
                "reviews": len(mine), "disagreements": sum(1 for r in mine if r["disagrees_with_engine"]),
            }
        )
    c_edges = [r["committee_edge_5d"] for r in rows if r["committee_edge_5d"] is not None]
    e_edges = [r["engine_edge_5d"] for r in rows if r["engine_edge_5d"] is not None]
    return {
        "users": len(per_user),
        "live_days": live_days,
        "reviews": len(rows),
        "scored_reviews": len(c_edges),
        "pooled": {
            "committee_added_dollars": round(sum(u["committee_added_dollars"] for u in per_user), 2),
            "mean_committee_edge_5d": _mean(c_edges),
            "mean_engine_edge_5d": _mean(e_edges),
            "committee_hit_rate_5d": (sum(1 for x in c_edges if x > 0) / len(c_edges)) if c_edges else None,
            "engine_hit_rate_5d": (sum(1 for x in e_edges if x > 0) / len(e_edges)) if e_edges else None,
            "disagreement_rate": (sum(1 for r in rows if r["disagrees_with_engine"]) / len(rows)) if rows else None,
        },
        "per_user": sorted(per_user, key=lambda x: x["username"]),
        "note": (
            "Users share the same 15 stocks and the same committee reviews, so these rows are NOT independent samples: "
            "eleven users is not eleven experiments. Judge the committee on the pooled scored reviews, and only once there are enough of them."
        ),
    }


def to_csv(rows: List[Dict[str, Any]]) -> str:
    import csv
    import io

    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
