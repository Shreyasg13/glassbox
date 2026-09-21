"""The arena: outside decision-makers compete on OUR scoreboard.

TradingAgents (Apache-2.0, https://github.com/TauricResearch/TradingAgents), a human analyst, another
framework, a future version of our own committee -- anything that can say BUY / SELL / HOLD about a symbol on
a date can be a challenger. Its calls are recorded here; paper_cycle then runs a paper account that trades
exactly on them (strategy `external_tilt`), and research.evidence_table judges it with the SAME live
out-of-sample gate as every strategy of ours: same stocks, same days, same rules, after costs.

That is what "keep ours superior" can honestly mean. Nobody can promise to stay ahead of a research framework
that is free to copy from; what can be kept is a fair, public, continuously-running yardstick, so that if a
challenger IS better the platform finds out first and adopts the idea.

Integrity rules baked in: a call can only be recorded for a date up to today (never the future), for a symbol
we track, in the challenger's own name; and the challenger's calls are stored apart from our committee's
decisions, so they can never contaminate our scorecards.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from . import data_source as ds
from . import db

SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")

# Other frameworks say it differently; map the common vocabulary onto BUY / SELL / HOLD.
_SYNONYMS = {
    "BUY": "BUY", "STRONG BUY": "BUY", "OVERWEIGHT": "BUY", "LONG": "BUY", "ACCUMULATE": "BUY", "OUTPERFORM": "BUY",
    "SELL": "SELL", "STRONG SELL": "SELL", "UNDERWEIGHT": "SELL", "SHORT": "SELL", "REDUCE": "SELL", "UNDERPERFORM": "SELL",
    "HOLD": "HOLD", "NEUTRAL": "HOLD", "MAINTAIN": "HOLD", "WAIT": "HOLD", "MARKET PERFORM": "HOLD",
}
_WORDS = sorted(_SYNONYMS, key=len, reverse=True)


def normalize_decision(raw: Any) -> Optional[str]:
    """BUY / SELL / HOLD from whatever a framework returned ("**BUY**", "Final decision: Overweight", ...). None when
    no recognised call is in it -- an unreadable answer is skipped, never guessed."""
    if not isinstance(raw, str):
        return None
    text = re.sub(r"[^A-Za-z ]", " ", raw).upper()
    text = re.sub(r"\s+", " ", text).strip()
    if text in _SYNONYMS:
        return _SYNONYMS[text]
    best: Optional[Tuple[int, str]] = None
    for w in _WORDS:
        m = re.search(rf"\b{w}\b", text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), _SYNONYMS[w])
    return best[1] if best else None


Decisions = Union[Dict[str, Any], Iterable[Dict[str, Any]]]


def _pairs(decisions: Decisions) -> List[Tuple[str, Any, Dict[str, Any]]]:
    if isinstance(decisions, dict):
        return [(k, v, {}) for k, v in decisions.items()]
    out = []
    for item in decisions:
        meta = {k: v for k, v in item.items() if k not in ("symbol", "decision")}
        out.append((item.get("symbol", ""), item.get("decision"), meta))
    return out


def record(source: str, d: str, decisions: Decisions, *, today: Optional[date] = None) -> Dict[str, Any]:
    """Store a challenger's calls for one date. Returns {"recorded": n, "skipped": [(symbol, why)]}."""
    if not SOURCE_RE.match(source or ""):
        raise ValueError("source must be 2-32 characters: lowercase letters, digits, '-' or '_' (e.g. 'tradingagents')")
    try:
        day = date.fromisoformat(d)
    except (TypeError, ValueError):
        raise ValueError(f"date must be YYYY-MM-DD, got {d!r}") from None
    today = today or datetime.now(timezone.utc).date()
    if day > today:
        raise ValueError(f"{d} is in the future: a call can only be recorded for a date that has happened")
    recorded, skipped = 0, []
    for symbol, raw, meta in _pairs(decisions):
        sym = str(symbol).strip().upper()
        action = normalize_decision(raw)
        if sym not in ds.STOCK_INFO:
            skipped.append((sym or "?", "not a tracked symbol"))
        elif action is None:
            skipped.append((sym, f"unreadable call {raw!r}"))
        else:
            db.save_challenger_decision(source, d, sym, action, meta)
            recorded += 1
    return {"source": source, "date": d, "recorded": recorded, "skipped": skipped}


def summary(source: Optional[str] = None) -> List[Dict[str, Any]]:
    """What is on record per challenger: how many calls, over which dates and symbols, and the mix."""
    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in db.list_challenger_decisions(source):
        by.setdefault(r["source"], []).append(r)
    out = []
    for src, rows in sorted(by.items()):
        dates = sorted({r["date"] for r in rows})
        out.append(
            {
                "source": src,
                "calls": len(rows),
                "first": dates[0],
                "last": dates[-1],
                "days": len(dates),
                "symbols": len({r["symbol"] for r in rows}),
                "mix": {a: sum(1 for r in rows if r["action"] == a) for a in ("BUY", "SELL", "HOLD")},
            }
        )
    return out
