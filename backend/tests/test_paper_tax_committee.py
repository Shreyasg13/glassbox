"""Tax lots (FIFO, short vs long term, after-tax return) and the committee_tilt strategy."""
from __future__ import annotations

import pandas as pd
import pytest

from app import paper

PARAMS = {"rsi_low": 30, "rsi_high": 70, "fast_ma": 20, "slow_ma": 50}
N = 600
IDX = pd.bdate_range("2022-01-03", periods=N)
D = [d.strftime("%Y-%m-%d") for d in IDX]


def book_with(prices, signals=None):
    """prices: {sym: {index: close}} (others carry forward 100). signals: {sym: {index: 'BUY'|'SELL'}}."""
    frames = {}
    for sym, marks in prices.items():
        closes, last = [], 100.0
        for i in range(N):
            last = marks.get(i, last)
            closes.append(last)
        sig = (signals or {}).get(sym, {})
        rsi = [20.0 if sig.get(i) == "BUY" else 80.0 if sig.get(i) == "SELL" else 50.0 for i in range(N)]
        fast = [101.0 if sig.get(i) == "BUY" else 99.0 if sig.get(i) == "SELL" else 100.0 for i in range(N)]
        frames[sym] = pd.DataFrame({"Close": closes, "RSI": rsi, "MA_20": fast, "MA_50": [100.0] * N}, index=IDX)
    return paper.PriceBook.from_frames(frames, {s: PARAMS for s in frames})


def acct(strategy="engine_tilt", weights=None, invested=1.0):
    return paper.new_account("t", "T", "control", strategy, weights or {"AAA": 1.0}, invested=invested, start_cash=100_000.0)


def trade(a, book, i, weights):
    """Queue target weights and execute them on bar i."""
    a["pending"] = {"weights": weights, "reasons": {}, "decided": D[i - 1]}
    paper._execute_pending(a, book, D[i])


@pytest.fixture(autouse=True)
def fixed_rates(monkeypatch):
    monkeypatch.setattr(paper, "TAX_ST", 0.30)
    monkeypatch.setattr(paper, "TAX_LT", 0.10)
    monkeypatch.setattr(paper, "COMMISSION_BPS", 0.0)


def test_a_sale_inside_a_year_is_short_term_and_taxed_at_the_short_rate():
    book = book_with({"AAA": {0: 100.0, 100: 120.0}})
    a = acct()
    trade(a, book, 0, {"AAA": 1.0})  # buy 1000 shares @100
    trade(a, book, 100, {})  # sell everything @120
    assert a["tax"]["st"] == pytest.approx(20_000) and a["tax"]["lt"] == 0
    assert paper.estimate_tax(a["tax"]["st"], a["tax"]["lt"]) == pytest.approx(6_000)
    assert a["lots"] == {}
    s = paper.summarize(a)
    assert s["tax_tracked"] and s["est_tax"] == pytest.approx(6_000)
    assert s["tax_drag"] == pytest.approx(0.06) and s["avg_holding_days"] == pytest.approx((_days(0, 100)))


def _days(i, j):
    return (IDX[j] - IDX[i]).days


def test_holding_more_than_a_year_makes_the_gain_long_term():
    book = book_with({"AAA": {0: 100.0, 400: 150.0}})
    assert _days(0, 400) > 365
    a = acct()
    trade(a, book, 0, {"AAA": 1.0})
    trade(a, book, 400, {})
    assert a["tax"]["lt"] == pytest.approx(50_000) and a["tax"]["st"] == 0
    assert paper.estimate_tax(0, a["tax"]["lt"]) == pytest.approx(5_000)


def test_selling_takes_the_oldest_lot_first_and_splits_short_and_long():
    book = book_with({"AAA": {0: 100.0, 300: 110.0, 400: 130.0}})
    a = acct(invested=1.0)
    a["start_cash"] = a["cash"] = 2_100.0  # buys 10 @100, then 10 @110 = 2,100
    a["positions"], a["lots"] = {}, {}
    trade(a, book, 0, {"AAA": 1000 / 2100})  # 10 shares @100
    a["cash"] = 1_100.0
    trade(a, book, 300, {"AAA": 1.0})  # tops up ~10 shares @110
    held = a["positions"]["AAA"]
    assert held == pytest.approx(20.0, rel=1e-3) and len(a["lots"]["AAA"]) == 2
    a["pending"] = {"weights": {"AAA": 5 * 130 / (a["cash"] + held * 130)}, "reasons": {}, "decided": D[399]}
    paper._execute_pending(a, book, D[400])  # sell ~15 shares @130: 10 from the old lot (long), ~5 from the newer (short)
    sold = 20.0 - a["positions"]["AAA"]
    assert 14.5 < sold < 15.5
    assert a["tax"]["lt"] == pytest.approx(10 * 30, rel=0.02)
    assert a["tax"]["st"] == pytest.approx((sold - 10) * 20, rel=0.05)
    assert a["lots"]["AAA"][0][2] == pytest.approx(110.0)  # only the newer lot remains


def test_a_short_term_loss_offsets_a_long_term_gain_and_a_net_loss_costs_nothing():
    assert paper.estimate_tax(-1000, 5000) == pytest.approx(4000 * 0.10)
    assert paper.estimate_tax(5000, -1000) == pytest.approx(4000 * 0.30)
    assert paper.estimate_tax(-500, -500) == 0.0
    assert paper.estimate_tax(1000, 1000) == pytest.approx(300 + 100)


def test_a_buy_and_hold_account_pays_no_tax_but_shows_a_deferred_long_term_gain():
    book = book_with({"AAA": {0: 100.0, 450: 200.0}})
    a = acct("static_hold")
    trade(a, book, 0, {"AAA": 1.0})
    paper.refresh_unrealized(a, book, D[450])
    s = paper.summarize(a)
    assert s["est_tax"] == 0 and s["realized_st"] == 0 and s["realized_lt"] == 0
    assert s["unrealized_lt"] == pytest.approx(100_000) and s["unrealized_st"] == 0
    assert s["avg_holding_days"] is None  # nothing has been sold


def test_an_account_from_before_tax_tracking_reports_unknown_not_zero():
    a = acct()
    a.pop("tax"), a.pop("lots")
    s = paper.summarize(a)
    assert s["tax_tracked"] is False and s["est_tax"] is None and s["after_tax_return"] is None


def test_selling_with_no_recorded_lots_does_not_crash_or_invent_a_gain():
    book = book_with({"AAA": {0: 100.0}})
    a = acct()
    a["positions"] = {"AAA": 10.0}  # a position with no lots (should not happen for a tracked account)
    trade(a, book, 5, {})
    assert a["tax"]["st"] == 0 and a["tax"]["lt"] == 0


# ------------------------------------------------------------ committee_tilt --


def test_committee_views_expire_after_the_max_age_and_ignore_the_future():
    book = book_with({"AAA": {0: 100.0}})
    book.set_committee({"AAA": {D[10]: "SELL"}})
    assert book.committee_at("AAA", D[9]) is None  # not yet decided
    assert book.committee_at("AAA", D[10]) == "SELL"
    assert book.committee_at("AAA", D[10 + paper.COMMITTEE_MAX_AGE_DAYS]) == "SELL"
    assert book.committee_at("AAA", D[10 + paper.COMMITTEE_MAX_AGE_DAYS + 1]) is None  # stale
    assert book.committee_at("ZZZ", D[10]) is None


def test_committee_tilt_follows_the_committee_where_it_has_a_view_and_the_engine_elsewhere():
    book = book_with({"AAA": {0: 100.0}, "BBB": {0: 100.0}}, signals={"AAA": {10: "BUY"}, "BBB": {10: "BUY"}})
    book.set_committee({"AAA": {D[10]: "SELL"}})  # committee overrules the engine's BUY on AAA only
    a = acct("committee_tilt", {"AAA": 0.5, "BBB": 0.5}, invested=0.8)
    weights, reasons, sigs = paper._target_weights(a, book, D[10])
    assert sigs == {"AAA": "SELL", "BBB": "BUY"}
    assert weights["AAA"] < weights["BBB"]
    assert reasons["AAA"] == "committee SELL" and "no committee view" in reasons["BBB"]
    engine_weights, _, engine_sigs = paper._target_weights(acct("engine_tilt", {"AAA": 0.5, "BBB": 0.5}, invested=0.8), book, D[10])
    assert engine_sigs == {"AAA": "BUY", "BBB": "BUY"} and engine_weights["AAA"] > weights["AAA"]


def test_without_any_committee_history_the_strategy_matches_the_engine_exactly():
    prices = {"AAA": {0: 100.0, 50: 110.0, 90: 95.0}}
    sigs = {"AAA": {30: "BUY", 60: "SELL"}}
    book = book_with(prices, sigs)
    e, c = acct("engine_tilt", invested=0.8), acct("committee_tilt", invested=0.8)
    paper.advance(e, book, live_from=D[-1])
    paper.advance(c, book, live_from=D[-1])
    assert e["curve"] == c["curve"] and e["trade_count"] == c["trade_count"]


def test_the_committee_strategy_is_a_registered_strategy():
    assert "committee_tilt" in paper.STRATEGIES
