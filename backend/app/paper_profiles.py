"""The paper-trading test cohort: 11 portfolio archetypes spread across risk
level, horizon and asset mix (growth, income, index, financials, diversified,
60/40, all-weather, quality, momentum, cyclical, capital preservation).

This registry is the single source of truth for those profiles. It is used by
  * app/paper_cycle.py -- every profile here gets a paper-trading account (and a
    policy benchmark) whether or not anyone can log in as it, so the admin
    master view never depends on known-password accounts existing on a public
    deployment; and
  * app/scripts/seed_demo_users.py -- which OPTIONALLY creates a login for each,
    for QA/demo of the user-facing dashboard.

Every ticker must be one of data_source.STOCK_INFO (the 15 symbols with price
history on the server) -- tests enforce that. A profile may carry
`strategic_weights` (a policy allocation over its tickers, e.g. the classic
60/40); without it the engine splits the watchlist equally.
"""
from __future__ import annotations

from typing import Any, Dict, List

STARTING_CASH = 100_000  # matches the system portfolio's initial capital


def _p(archetype: str, risk: str, years: int, **extra: Any) -> Dict[str, Any]:
    return {"archetype": archetype, "risk_level": risk, "horizon_years": years, "starting_cash": STARTING_CASH, **extra}


DEMO_PROFILES: List[Dict[str, Any]] = [
    {"username": "demo_growth", "tickers": ["AAPL", "NVDA", "TSLA"], "note": "Aggressive tech growth",
     "profile": _p("growth", "aggressive", 10)},
    {"username": "demo_income", "tickers": ["JNJ", "V", "TLT"], "note": "Defensive / income-oriented",
     "profile": _p("income", "conservative", 5)},
    {"username": "demo_index", "tickers": ["SPY", "QQQ", "IWM"], "note": "Broad index / ETF core",
     "profile": _p("index", "moderate", 15)},
    {"username": "demo_finance", "tickers": ["JPM", "V", "GOOGL"], "note": "Financials + mega-cap tilt",
     "profile": _p("financials", "moderate", 7)},
    {"username": "demo_diversified", "tickers": ["AAPL", "JPM", "JNJ", "GLD", "TLT"], "note": "Multi-sector diversified (5 symbols)",
     "profile": _p("diversified", "moderate", 10)},
    {"username": "demo_balanced", "tickers": ["SPY", "TLT"], "note": "Balanced 60/40 -- the classic institutional baseline",
     "profile": _p("balanced_60_40", "moderate", 10, strategic_weights={"SPY": 0.6, "TLT": 0.4})},
    {"username": "demo_allweather", "tickers": ["SPY", "TLT", "GLD"], "note": "All-weather / risk-parity style -- tests drawdown control",
     "profile": _p("all_weather", "conservative", 15, strategic_weights={"SPY": 0.3, "TLT": 0.5, "GLD": 0.2})},
    {"username": "demo_quality", "tickers": ["MSFT", "GOOGL", "AAPL", "V", "JNJ"], "note": "Quality mega-cap compounding",
     "profile": _p("quality_megacap", "moderate", 10)},
    {"username": "demo_momentum", "tickers": ["NVDA", "META", "TSLA", "QQQ"], "note": "Concentrated momentum -- high volatility, tests risk management",
     "profile": _p("momentum", "aggressive", 5)},
    {"username": "demo_cyclical", "tickers": ["IWM", "JPM", "AMZN", "TSLA"], "note": "Cyclical / small-cap -- tests regime sensitivity",
     "profile": _p("cyclical_smallcap", "aggressive", 7)},
    {"username": "demo_preserve", "tickers": ["TLT", "JNJ", "GLD", "V"], "note": "Capital preservation -- low-risk mandate",
     "profile": _p("capital_preservation", "conservative", 3)},
]
