"""A user's paper portfolio as the Investment Committee runs it: initial -> final, profit, and why.

For every profile the daily paper cycle keeps three accounts with the same watchlist, weights and
starting cash (see paper_cycle._profile_accounts):

    profile:<u>    trades on the quant ENGINE's signals            ("what the engine alone would do")
    committee:<u>  same, but follows the COMMITTEE where it has a fresh, risk-checked call
    bench:<u>      the policy weights, signals ignored             ("just hold your plan")

So the gap committee - engine is exactly what the committee added for that user. Read-only: this
curates what those accounts and the stored committee runs already say; nothing is recomputed.

HONESTY RULES baked in:
  * The committee only started reviewing on live days. Before `live_from` the committee account is
    identical to the engine account BY CONSTRUCTION, so the response separates the whole history
    from the live (out-of-sample) part and the UI must say so.
  * Money is simulated paper trading, never real.
  * A user with no paper account (a real signup without a profile) sees the shared model portfolio
    over the full universe, labelled as such -- never another user's numbers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import paper, paper_cycle

MAX_POINTS = 300
RECENT_DECISIONS = 30
RECENT_TRADES = 30
FALLBACK = {"committee": "ctl_committee", "engine": "ctl_engine", "benchmark": "ctl_equal"}


def _ids(username: str) -> Dict[str, str]:
    base = username.strip().lower()
    return {"committee": f"committee:{base}", "engine": f"profile:{base}", "benchmark": f"bench:{base}"}


def _money(acct: Dict[str, Any]) -> Dict[str, Any]:
    curve = acct["curve"]
    start = acct["start_cash"]
    last = curve[-1][1] if curve else start
    live = [p for p in curve if p[2] == "live"]
    bt = [p for p in curve if p[2] == "backtest"]
    base = bt[-1][1] if bt else start
    return {
        "id": acct["id"],
        "name": acct["name"],
        "initial": round(start, 2),
        "final": round(last, 2),
        "profit": round(last - start, 2),
        "return": last / start - 1 if start else None,
        "live_profit": round(last - base, 2) if live else None,
        "live_return": (last / base - 1) if live and base else None,
        "since": acct.get("inception"),
        "as_of": acct.get("last_date"),
    }


def _curves(accts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    main = accts["committee"]["curve"]
    dates = [p[0] for p in paper_cycle.downsample(main, MAX_POINTS)]
    keep = set(dates)
    out: Dict[str, Any] = {"dates": dates, "live_from": next((p[0] for p in main if p[2] == "live"), None)}
    for role, a in accts.items():
        by = {p[0]: p[1] for p in a["curve"]}
        out[role] = [by.get(d) for d in dates if d in keep]
    return out


def _symbol_pnl(acct: Dict[str, Any]) -> Dict[str, float]:
    """Net P&L per symbol from cash flows, costs included: sells - buys - costs + what is still held."""
    pnl: Dict[str, float] = {}
    for t in acct["trades"]:
        gross = t["shares"] * t["price"]
        pnl[t["symbol"]] = pnl.get(t["symbol"], 0.0) + (gross if t["side"] == "SELL" else -gross) - t.get("cost", 0.0)
    for sym, h in (acct.get("holdings") or {}).items():
        pnl[sym] = pnl.get(sym, 0.0) + h["value"]
    return pnl


def _latest_calls(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """The most recent usable committee review per symbol, however old: the user should still see the last
    call and its reason. `committee_fresh` says whether the paper account would still act on it."""
    best: Dict[str, Dict[str, Any]] = {}
    for r in runs:
        if not r.get("action") and not (r.get("quorum_ok") and r.get("decision")):
            continue
        if r["symbol"] not in best or r["date"] > best[r["symbol"]]["date"]:
            best[r["symbol"]] = r
    return best


def _age(book, then: str, now: str) -> int:
    import bisect

    return bisect.bisect_left(book.dates, now) - bisect.bisect_left(book.dates, then)


def _symbols(accts: Dict[str, Dict[str, Any]], book, runs: List[Dict[str, Any]], engine_last_targets: Dict[str, Any]) -> List[Dict[str, Any]]:
    from . import strategy

    committee = accts["committee"]
    d = committee.get("last_date") or book.latest_date
    views = _latest_calls(runs)
    pnl = _symbol_pnl(committee)
    eng_pnl = _symbol_pnl(accts["engine"])
    hold = committee.get("holdings") or {}
    rows = []
    for sym, policy in committee["weights"].items():
        v = views.get(sym)
        sig, conf = book.signal_at(sym, d) if d else ("HOLD", 0.0)
        action = (v.get("action") or v.get("decision")) if v else None
        ceo = (v or {}).get("ceo") or {}
        rows.append(
            {
                "symbol": sym,
                "policy_weight": round(policy * committee["invested"], 4),
                "current_weight": (hold.get(sym) or {}).get("weight", 0.0),
                "value": (hold.get(sym) or {}).get("value", 0.0),
                "engine_signal": sig,
                "engine_confidence": conf,
                "committee_action": action,
                "committee_date": v["date"] if v else None,
                "committee_fresh": bool(v and d and _age(book, v["date"], d) <= strategy.STALE_VIEW_DAYS),
                "headline": ceo.get("headline"),
                "consensus": ceo.get("label"),
                "disagrees": bool(action and (v or {}).get("engine_signal") and action != v["engine_signal"]),  # vs the engine's call ON THE REVIEW DAY, not today's
                "pnl": round(pnl.get(sym, 0.0), 2),
                "engine_pnl": round(eng_pnl.get(sym, 0.0), 2),
            }
        )
    rows.sort(key=lambda r: -abs(r["pnl"]))
    return rows


def _decisions(symbols: List[str], runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    want = set(symbols)
    rows = [r for r in runs if r["symbol"] in want]
    rows.sort(key=lambda r: (r["date"], r["symbol"]), reverse=True)
    return [
        {
            "date": r["date"],
            "symbol": r["symbol"],
            "engine_signal": r.get("engine_signal"),
            "decision": r.get("decision"),
            "action": r.get("action"),
            "consensus": (r.get("ceo") or {}).get("label"),
            "headline": (r.get("ceo") or {}).get("headline"),
            "gated": bool(r.get("gate")),
            "answered": r.get("answered"),
            "total": r.get("total"),
        }
        for r in rows[:RECENT_DECISIONS]
    ]


def _trades(acct: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"date": t["date"], "symbol": t["symbol"], "side": t["side"], "shares": round(t["shares"], 4), "price": round(t["price"], 2), "reason": t["reason"], "by_committee": str(t["reason"]).startswith("committee")}
        for t in reversed(acct["trades"][-RECENT_TRADES:])
    ]


def build(accts: Dict[str, Dict[str, Any]], book, runs: List[Dict[str, Any]], *, label: str, is_model: bool) -> Dict[str, Any]:
    from . import portfolio_analytics as pa

    committee, engine, bench = _money(accts["committee"]), _money(accts["engine"]), _money(accts["benchmark"])
    curves = _curves(accts)
    live_days = sum(1 for p in accts["committee"]["curve"] if p[2] == "live")
    added = round(committee["final"] - engine["final"], 2)
    return {
        "label": label,
        "is_model_portfolio": is_model,
        "simulated": True,
        "watchlist": list(accts["committee"]["weights"]),
        "risk_level": accts["committee"].get("risk_level"),
        "profile": accts["committee"].get("profile") or {},
        "live_from": curves["live_from"],
        "live_days": live_days,
        "committee": committee,
        "engine": engine,
        "benchmark": bench,
        "committee_added": {
            "dollars": added,
            "points": (committee["return"] - engine["return"]) if committee["return"] is not None and engine["return"] is not None else None,
            "note": (
                "The committee has not made a live call that changed a trade yet, so its line and the engine's are identical."
                if live_days and added == 0
                else "No live trading days yet: the committee's line equals the engine's by construction."
                if not live_days
                else "Difference in final value between the committee-run account and the engine-only account, same cash and stocks."
            ),
        },
        "curves": curves,
        "symbols": _symbols(accts, book, runs, accts["engine"].get("last_targets", {})),
        "decisions": _decisions(list(accts["committee"]["weights"]), runs),
        "trades": _trades(accts["committee"]),
        "monte_carlo": {"committee": pa.monte_carlo(accts["committee"]), "engine": pa.monte_carlo(accts["engine"])},
        "agents": pa.agent_progress(list(accts["committee"]["weights"]), book, runs),
    }


def user_portfolio(username: str, book, runs: List[Dict[str, Any]], accounts: Optional[Dict[str, Dict[str, Any]]] = None, *, allow_fallback: bool = True) -> Optional[Dict[str, Any]]:
    """The named user's committee-run portfolio; the shared model portfolio if they have no account and
    `allow_fallback`; None if neither exists."""
    from . import db

    accounts = accounts if accounts is not None else {a["id"]: a for a in db.list_paper_accounts()}
    own = {role: accounts.get(i) for role, i in _ids(username).items()}
    if all(own.values()):
        return build(own, book, runs, label=own["committee"]["name"], is_model=False)
    if not allow_fallback:
        return None
    model = {role: accounts.get(i) for role, i in FALLBACK.items()}
    if all(model.values()):
        return build(model, book, runs, label="GlassBox model portfolio (all tracked stocks)", is_model=True)
    return None


def selectable_users(users: List[Dict[str, Any]], accounts: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Every user an admin can inspect: anyone (registry profile or real signup) with a committee-run account."""
    from . import db

    accounts = accounts if accounts is not None else {a["id"]: a for a in db.list_paper_accounts()}
    out = []
    for u in paper_cycle._cohort(users):
        acct = accounts.get(_ids(u["username"])["committee"])
        if not acct:
            continue
        m = _money(acct)
        out.append(
            {
                "username": u["username"],
                "archetype": (acct.get("profile") or {}).get("archetype"),
                "risk_level": acct.get("risk_level"),
                "tickers": list(acct["weights"]),
                "final": m["final"],
                "profit": m["profit"],
                "return": m["return"],
            }
        )
    out.sort(key=lambda r: r["username"])
    return out
