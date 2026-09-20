"""The risk signal: no lookahead, sensible levels, and a scorecard that separates calm from rough."""
from __future__ import annotations

import math
import random

import pandas as pd

from app import paper, risk

PARAMS = {"rsi_low": 30, "rsi_high": 70, "fast_ma": 20, "slow_ma": 50}


def book_from(closes_by_sym):
    frames = {}
    for sym, closes in closes_by_sym.items():
        n = len(closes)
        idx = pd.bdate_range("2020-01-01", periods=n)
        frames[sym] = pd.DataFrame({"Close": closes, "RSI": [50.0] * n, "MA_20": [100.0] * n, "MA_50": [100.0] * n}, index=idx)
    return paper.PriceBook.from_frames(frames, {s: PARAMS for s in frames})


def regime_series(n_calm=400, n_wild=120, seed=1):
    """Calm drift, then a violent, falling stretch."""
    rnd = random.Random(seed)
    px, out = 100.0, []
    for _ in range(n_calm):
        px *= 1 + rnd.gauss(0.0004, 0.005)
        out.append(px)
    for _ in range(n_wild):
        px *= 1 + rnd.gauss(-0.002, 0.03)
        out.append(px)
    return out


def alternating_regimes(cycles=8, calm=90, wild=60, seed=0):
    """ONE continuous price path that alternates calm and violent regimes (no jumps at the joins)."""
    rnd = random.Random(seed)
    px, out = 100.0, []
    for _ in range(cycles):
        for _ in range(calm):
            px *= 1 + rnd.gauss(0.0006, 0.005)
            out.append(px)
        for _ in range(wild):
            px *= 1 + rnd.gauss(-0.0008, 0.025)
            out.append(px)
    return out


def test_nothing_is_rated_until_a_year_of_history_exists():
    s = risk.compute_series([100.0 + i * 0.1 for i in range(300)])
    assert all(x is None for x in s[: risk.MIN_HISTORY - 1])
    assert s[risk.MIN_HISTORY - 1] is not None and s[-1] is not None


def test_a_calm_steady_riser_is_low_risk_and_a_violent_slump_is_high_risk():
    series = risk.compute_series(regime_series())
    calm = series[380]
    wild = series[-1]
    assert calm["level"] in ("LOW", "MEDIUM") and calm["score"] < 50
    assert wild["level"] == "HIGH" and wild["score"] > 66
    assert wild["drawdown"] < -0.2 and wild["vol"] > calm["vol"]


def test_todays_risk_never_depends_on_the_future():
    closes = regime_series()
    full = risk.compute_series(closes)
    for cut in (300, 420, 500):
        assert risk.compute_series(closes[:cut])[cut - 1] == full[cut - 1]  # same answer with the future removed


def test_score_and_level_stay_inside_their_bounds():
    for r in risk.compute_series(regime_series(seed=7)):
        if r:
            assert 0.0 <= r["score"] <= 100.0 and r["level"] in ("LOW", "MEDIUM", "HIGH")
            assert not math.isnan(r["vol"]) and r["drawdown"] <= 0.0


def test_levels_follow_the_thresholds():
    assert risk.level_for(66.0) == "HIGH" and risk.level_for(65.9) == "MEDIUM"
    assert risk.level_for(33.0) == "LOW" and risk.level_for(33.1) == "MEDIUM"


def test_risk_at_and_the_ranked_table_use_the_book():
    book = book_from({"CALM": [100 + i * 0.05 for i in range(500)], "WILD": regime_series()})
    d = book.latest_date
    assert risk.risk_at(book, "WILD", d)["level"] == "HIGH"
    assert risk.risk_at(book, "CALM", "1999-01-01") is None  # a date with no bar
    table = risk.risk_table(book, d)
    assert [r["symbol"] for r in table][0] == "WILD" and table[0]["score"] >= table[-1]["score"]


def test_the_scorecard_shows_high_risk_precedes_rougher_weeks_than_low_risk():
    # several volatility regimes so both LOW and HIGH days exist with a future to grade
    closes = alternating_regimes(seed=3)
    book = book_from({"X": closes, "Y": alternating_regimes(seed=4)})
    sc = risk.risk_scorecard(book, horizons=(5, 20))
    hi, lo = sc["levels"]["HIGH"]["20"], sc["levels"]["LOW"]["20"]
    assert hi["n"] > 20 and lo["n"] > 20
    assert hi["fwd_vol"] > lo["fwd_vol"]
    assert sc["lift"]["20"]["vol"] > 1.0
    # Deliberately NOT asserted: that dips are deeper after HIGH. A volatility signal lags a sudden onset
    # (the last calm days before a crash rate LOW), so worst-dip separation is something the scorecard
    # measures on real data, not something the design can promise.
    assert hi["fwd_worst_dip"] is not None and lo["fwd_worst_dip"] is not None
    assert sc["levels"]["ALL"]["20"]["n"] == sum(sc["levels"][lv]["20"]["n"] for lv in ("LOW", "MEDIUM", "HIGH"))


def test_the_scorecard_copes_with_no_rated_days():
    book = book_from({"X": [100.0 + i for i in range(60)]})  # too short to rate
    sc = risk.risk_scorecard(book)
    assert sc["levels"]["ALL"]["5"]["n"] == 0 and sc["lift"]["5"]["vol"] is None
