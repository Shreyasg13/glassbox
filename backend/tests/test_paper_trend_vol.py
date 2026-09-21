"""The trend filter and volatility-targeted sizing: no lookahead, no leverage, sensible states."""
from __future__ import annotations

import copy
import math
import random

import pytest

from app import paper, paper_cycle
from tests.test_paper_cycle import N_FULL, fake, make_book as cycle_book, day  # noqa: F401  (fake is a fixture)
from tests.test_paper_tax_committee import D, N, book_with


def series_book(series_by_sym):
    return book_with({sym: {i: c for i, c in enumerate(closes)} for sym, closes in series_by_sym.items()})


def acct(strategy, weights=None, invested=1.0, aid="t"):
    return paper.new_account(aid, "T", "control", strategy, weights or {"AAA": 1.0}, invested=invested, start_cash=100_000.0)


def rise_then_crash():
    """A steady climb for 400 bars, a sharp fall through the 200-day average, then flat."""
    return [100 + 0.15 * i for i in range(400)] + [160 - 1.6 * k for k in range(60)] + [64.0] * (N - 460)


def noisy(sigma, seed, drift=0.0003, n=N):
    rnd, px, out = random.Random(seed), 100.0, []
    for _ in range(n):
        px *= 1 + rnd.gauss(drift, sigma)
        out.append(px)
    return out


# --------------------------------------------------------------- trend filter --


def test_the_trend_state_is_fixed_for_a_whole_month_and_only_flips_on_the_first_bar_of_a_month():
    book = series_book({"AAA": rise_then_crash()})
    states = [(i, paper._trend_state(book, "AAA", D[i])[0]) for i in range(250, N)]
    by_month = {}
    for i, on in states:
        by_month.setdefault(D[i][:7], set()).add(on)
    assert all(len(v) == 1 for v in by_month.values())  # constant within every month
    flips = [i for (i, on), (_, prev) in zip(states[1:], states) if on != prev]
    assert flips and all(D[i][:7] != D[i - 1][:7] for i in flips)  # a flip only ever lands on a month's first bar
    assert states[0][1] is True and states[-1][1] is False  # invested in the climb, out after the crash


def test_the_trend_state_uses_only_the_previous_month_end_and_never_looks_ahead():
    base = rise_then_crash()
    i = 430
    scrambled = base[: i + 1] + [1.0] * (N - i - 1)  # identical up to day i, garbage after
    a, b = series_book({"AAA": base}), series_book({"AAA": scrambled})
    for day_i in range(300, i + 1):
        assert paper._trend_state(a, "AAA", D[day_i]) == paper._trend_state(b, "AAA", D[day_i])
    # and it really is "last bar of the previous month vs its 200-day average"
    month = D[i][:7]
    first = next(x for x in range(N) if D[x][:7] == month)
    k = first - 1
    sma = sum(base[k - 199: k + 1]) / 200
    assert paper._trend_state(a, "AAA", D[i])[0] == (base[k] > sma)


def test_with_less_than_200_days_of_history_the_trend_filter_stays_invested():
    book = series_book({"AAA": rise_then_crash()})
    assert paper._trend_state(book, "AAA", D[100]) == (True, "not enough history for a 200-day average: stay invested")


def test_the_trend_filter_holds_what_is_in_an_uptrend_and_sits_in_cash_for_the_rest():
    up = [100 + 0.2 * i for i in range(N)]
    down = [200 - 0.2 * i for i in range(N)]
    book = series_book({"UP": up, "DOWN": down})
    a = acct("trend_filter", {"UP": 0.5, "DOWN": 0.5}, invested=1.0)
    weights, reasons, sigs = paper._target_weights(a, book, D[N - 1])
    assert weights == {"UP": pytest.approx(0.5), "DOWN": 0.0} and sigs == {"UP": "BUY", "DOWN": "SELL"}
    assert "above" in reasons["UP"] and "below" in reasons["DOWN"]
    assert sum(weights.values()) <= 1.0


# ------------------------------------------------------------ volatility target --


def test_calm_markets_are_fully_invested_and_turbulent_ones_are_cut_in_tenth_steps_never_levered():
    exposures = {}
    for label, sigma in (("calm", 0.004), ("medium", 0.02), ("wild", 0.03)):
        book = series_book({"AAA": noisy(sigma, 1), "BBB": noisy(sigma, 2)})
        a = acct("vol_target", {"AAA": 0.5, "BBB": 0.5}, invested=1.0)
        weights, reasons, _ = paper._target_weights(a, book, D[N - 1])
        exposures[label] = sum(weights.values())
        assert exposures[label] <= 1.0 + 1e-9  # no leverage, ever
        assert abs(exposures[label] * 10 - round(exposures[label] * 10)) < 1e-9  # a 10% step
        assert "vol-target exposure" in reasons["AAA"]
    assert exposures["calm"] == pytest.approx(1.0)
    assert exposures["calm"] > exposures["medium"] > exposures["wild"] >= 0.0
    assert exposures["wild"] < 0.5


def test_the_volatility_target_never_looks_ahead():
    base = noisy(0.012, 3)
    i = 400
    calm_tail = base[: i + 1] + noisy(0.0005, 9, n=N - i - 1)  # the same to day i, very different afterwards
    a, b = series_book({"AAA": base}), series_book({"AAA": calm_tail})
    acc = acct("vol_target")
    for day_i in range(200, i + 1, 7):
        assert paper._target_weights(acc, a, D[day_i]) == paper._target_weights(acc, b, D[day_i])


def test_without_enough_history_the_volatility_target_is_fully_invested():
    book = series_book({"AAA": noisy(0.03, 4)})
    weights, reasons, _ = paper._target_weights(acct("vol_target"), book, D[5])
    assert weights == {"AAA": pytest.approx(1.0)} and "not enough history" in reasons["AAA"]
    assert paper._basket_vol(book, {"AAA": 1.0}, D[5]) is None


def test_basket_volatility_matches_a_hand_computation():
    closes = noisy(0.01, 5)
    book = series_book({"AAA": closes})
    d = 300
    rets = [closes[k] / closes[k - 1] - 1 for k in range(d - paper.VOL_WINDOW + 1, d + 1)]
    m = sum(rets) / len(rets)
    expected = math.sqrt(sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252)
    assert paper._basket_vol(book, {"AAA": 1.0}, D[d]) == pytest.approx(expected)


# ----------------------------------------------------------------- end to end --


def test_both_strategies_run_a_full_history_without_leverage_and_actually_trade():
    book = series_book({"AAA": rise_then_crash(), "BBB": noisy(0.02, 6)})
    for strategy in ("trend_filter", "vol_target"):
        a = acct(strategy, {"AAA": 0.5, "BBB": 0.5})
        paper.advance(a, book, live_from=D[-1])
        assert a["cash"] >= -1e-6 and len(a["curve"]) == N and a["trade_count"] > 2
        assert {t["side"] for t in a["trades"]} == {"BUY", "SELL"}
        for i in range(260, N, 11):
            w, _, _ = paper._target_weights(a, book, D[i])
            assert sum(w.values()) <= 1.0 + 1e-9
    trend = acct("trend_filter", {"AAA": 1.0})
    paper.advance(trend, book, live_from=D[-1])
    assert paper.summarize(trend)["cash_weight"] > 0.9  # it walked away from the crash and is sitting in cash


def test_the_trend_filter_trades_rarely_compared_with_the_signal_engine():
    book = series_book({"AAA": noisy(0.015, 7), "BBB": noisy(0.015, 8)})
    trend = acct("trend_filter", {"AAA": 0.5, "BBB": 0.5})
    paper.advance(trend, book, live_from=D[-1])
    assert trend["trade_count"] <= 40  # at most a few flips a year across two symbols


# ---------------------------------------------------------------- the accounts --


def test_the_new_controls_exist_in_both_wrappers_and_the_twins_trade_identically(fake):
    book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    a = fake.accounts
    for taxable, sheltered, strat in (("ctl_trend", "ctl_trend_ira", "trend_filter"), ("ctl_voltarget", "ctl_voltarget_ira", "vol_target")):
        assert a[taxable]["strategy"] == a[sheltered]["strategy"] == strat
        assert (a[taxable]["tax_status"], a[sheltered]["tax_status"]) == ("taxable", "sheltered")
        assert a[taxable]["curve"] == a[sheltered]["curve"]
        assert paper.summarize(a[sheltered])["est_tax"] == 0
    out = paper_cycle.rebuild_accounts(book=book)
    assert out["differs"] == [] and out["identical"] == len(a)


def test_a_rebuild_reproduces_the_new_strategies_exactly(fake):
    book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    before = copy.deepcopy(fake.accounts)
    out = paper_cycle.rebuild_accounts(apply=True, book=book)
    assert out["differs"] == []
    for aid in ("ctl_trend", "ctl_voltarget", "ctl_trend_ira", "ctl_voltarget_ira"):
        assert fake.accounts[aid]["curve"] == before[aid]["curve"]
