"""The tax-aware engine, wash-sale handling and the taxable / sheltered wrappers."""
from __future__ import annotations

import copy

import pytest

from app import paper, paper_cycle
from tests.test_paper_cycle import N_FULL, fake, make_book as cycle_book, day  # noqa: F401  (fake is a fixture)
from tests.test_paper_tax_committee import D, book_with


@pytest.fixture(autouse=True)
def fixed_rates(monkeypatch):
    monkeypatch.setattr(paper, "TAX_ST", 0.30)
    monkeypatch.setattr(paper, "TAX_LT", 0.10)
    monkeypatch.setattr(paper, "COMMISSION_BPS", 0.0)


def acct(strategy="engine_taxaware", weights=None, invested=1.0, tax_status="taxable", aid="t", seed=None):
    return paper.new_account(aid, "T", "control", strategy, weights or {"AAA": 1.0}, invested=invested, start_cash=100_000.0, tax_status=tax_status, seed=seed)


def trade(a, book, i, weights):
    a["pending"] = {"weights": weights, "reasons": {}, "decided": D[i - 1]}
    paper._execute_pending(a, book, D[i])


def risk_is(level):
    return lambda book, sym, d: {"level": level, "score": 90.0} if level else None


# ----------------------------------------------------------- persistent signal --


def test_a_signal_is_acted_on_only_after_it_has_persisted_and_the_last_persistent_one_stands():
    book = book_with({"AAA": {0: 100.0}}, signals={"AAA": {**{i: "BUY" for i in (10, 11, 12)}, **{i: "BUY" for i in range(30, 35)}}})
    sig = lambda i: paper._persistent_signal(book, "AAA", D[i])[0]  # noqa: E731
    assert sig(12) == "HOLD"  # only 3 BUY days: too short to act on
    assert sig(14) == "HOLD"
    assert sig(34) == "BUY"  # 5 in a row
    assert sig(36) == "BUY"  # a 2-day HOLD blip does not undo a persistent BUY
    assert sig(40) == "HOLD"  # HOLD has now persisted 5+ days
    assert paper._persistent_signal(book, "AAA", D[0]) == ("HOLD", 50.0)


def test_a_high_risk_regime_holds_a_persistent_buy_at_hold_for_the_taxaware_engine_only(monkeypatch):
    book = book_with({"AAA": {0: 100.0}}, signals={"AAA": {i: "BUY" for i in range(30, 40)}})
    monkeypatch.setattr(paper._risk, "risk_at", risk_is("HIGH"))
    assert paper._target_weights(acct("engine_taxaware"), book, D[38])[2] == {"AAA": "HOLD"}
    assert paper._target_weights(acct("engine_tilt"), book, D[38])[2] == {"AAA": "BUY"}
    monkeypatch.setattr(paper._risk, "risk_at", risk_is("MEDIUM"))
    assert paper._target_weights(acct("engine_taxaware"), book, D[38])[2] == {"AAA": "BUY"}


# ------------------------------------------------------------------- the lock --


def test_a_short_term_gain_is_locked_for_the_taxaware_engine_but_realised_by_the_plain_engine(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    book = book_with({"AAA": {0: 100.0, 100: 120.0}})
    ta, plain = acct("engine_taxaware"), acct("engine_tilt", aid="p")
    for a in (ta, plain):
        trade(a, book, 0, {"AAA": 1.0})
        trade(a, book, 100, {})  # ask to sell everything at a 20% short-term gain
    assert ta["positions"]["AAA"] == pytest.approx(1000) and ta["tax"]["st"] == 0 and ta["tax"]["deferred_sells"] == 1
    assert ta["tax"]["deferred_notional"] == pytest.approx(120_000)
    assert plain["positions"] == {} and plain["tax"]["st"] == pytest.approx(20_000)
    assert paper.summarize(ta)["deferred_sells"] == 1


def test_high_risk_unlocks_a_short_term_gain_because_protecting_it_beats_the_tax(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is("HIGH"))
    book = book_with({"AAA": {0: 100.0, 100: 120.0}})
    a = acct("engine_taxaware")
    trade(a, book, 0, {"AAA": 1.0})
    trade(a, book, 100, {})
    assert a["positions"] == {} and a["tax"]["st"] == pytest.approx(20_000) and a["tax"]["deferred_sells"] == 0


def test_a_long_term_gain_is_never_locked(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    book = book_with({"AAA": {0: 100.0, 400: 150.0}})
    a = acct("engine_taxaware")
    trade(a, book, 0, {"AAA": 1.0})
    trade(a, book, 400, {})
    assert a["positions"] == {} and a["tax"]["lt"] == pytest.approx(50_000) and a["tax"]["deferred_sells"] == 0


def _two_lots(strategy):
    """20 shares: 10 bought at 100 (long-term by idx 400), 10 bought at 140 (a short-term LOSS at 130)."""
    book = book_with({"AAA": {0: 100.0, 300: 140.0, 400: 130.0}})
    a = acct(strategy)
    a["positions"], a["cash"] = {"AAA": 20.0}, 0.0
    a["lots"] = {"AAA": [[D[0], 10.0, 100.0], [D[300], 10.0, 140.0]]}
    trade(a, book, 400, {"AAA": 5 * 130 / (20 * 130)})  # sell 15 of 20 shares
    return a


def test_the_taxaware_engine_sells_the_loss_lot_first_then_long_term_gain_where_fifo_would_not(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    ta, plain = _two_lots("engine_taxaware"), _two_lots("engine_tilt")
    assert ta["tax"]["st"] == pytest.approx(-100) and ta["tax"]["lt"] == pytest.approx(150)  # 10 @ -10 short-term, then 5 @ +30 long-term
    assert plain["tax"]["lt"] == pytest.approx(300) and plain["tax"]["st"] == pytest.approx(-50)  # FIFO burns the big long-term gain first
    assert paper.estimate_tax(ta["tax"]["st"], ta["tax"]["lt"]) < paper.estimate_tax(plain["tax"]["st"], plain["tax"]["lt"])


# ---------------------------------------------------------------------- bands --


def _drifted(strategy):
    book = book_with({"AAA": {0: 100.0}, "BBB": {0: 100.0}})
    a = acct(strategy, {"AAA": 0.5, "BBB": 0.5}, invested=0.8)
    paper._decide(a, book, D[300])  # first decision
    a["pending"], a["since_rebalance"] = None, 100
    a["positions"], a["cash"] = {"AAA": 470.0, "BBB": 330.0}, 20_000.0  # weights 0.47 / 0.33 vs targets 0.40 / 0.40: drift 0.07
    paper._decide(a, book, D[301])
    return a


def test_the_taxaware_engine_tolerates_more_drift_before_rebalancing(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    assert _drifted("engine_tilt")["pending"] is not None  # 7% drift > the 5% band
    assert _drifted("engine_taxaware")["pending"] is None  # 7% drift < the 10% band


# ------------------------------------------------------------------ wash sale --


def _round_trip(rebuy_at, status="taxable"):
    book = book_with({"AAA": {0: 100.0, 50: 80.0, rebuy_at: 82.0, 130: 90.0}})
    a = acct("engine_tilt", tax_status=status)
    trade(a, book, 0, {"AAA": 1.0})
    trade(a, book, 50, {})  # sell 1000 shares @ 80: a 20,000 short-term loss
    trade(a, book, rebuy_at, {"AAA": 1.0})
    return a, book


def test_a_loss_followed_by_a_rebuy_within_30_days_is_disallowed_and_moves_into_the_basis():
    a, book = _round_trip(60)
    bought = a["positions"]["AAA"]
    assert (D_days := (paper._date.fromisoformat(D[60]) - paper._date.fromisoformat(D[50])).days) <= paper.WASH_DAYS, D_days
    assert a["tax"]["wash_disallowed"] == pytest.approx(bought * 20)
    assert a["tax"]["st"] == pytest.approx(-20_000 + bought * 20)  # only the un-replaced part still counts as a loss
    assert a["lots"]["AAA"][0][2] == pytest.approx(82 + 20)  # cost basis carries the disallowed loss
    trade(a, book, 130, {})  # later sale at 90 vs a 102 basis: an ordinary loss, no rebuy after it
    assert a["tax"]["st"] == pytest.approx(-20_000 + bought * 20 - bought * 12)


def test_a_rebuy_after_the_window_leaves_the_loss_standing():
    a, _ = _round_trip(100)
    assert (paper._date.fromisoformat(D[100]) - paper._date.fromisoformat(D[50])).days > paper.WASH_DAYS
    assert a["tax"]["wash_disallowed"] == 0 and a["tax"]["st"] == pytest.approx(-20_000)
    assert a["lots"]["AAA"][0][2] == pytest.approx(82)


def test_shares_bought_in_the_30_days_before_a_loss_sale_make_it_a_wash_sale(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    book = book_with({"AAA": {0: 100.0, 40: 90.0, 50: 80.0}})
    a = acct("engine_tilt")
    a["positions"], a["cash"] = {"AAA": 20.0}, 0.0
    a["lots"] = {"AAA": [[D[0], 10.0, 100.0], [D[40], 10.0, 90.0]]}
    trade(a, book, 50, {"AAA": 10 * 80 / (20 * 80)})  # sell the old 10 shares (FIFO) at a loss while 10 replacement shares bought 10 days ago are held
    assert a["tax"]["st"] == pytest.approx(0) and a["tax"]["wash_disallowed"] == pytest.approx(200)
    assert a["lots"]["AAA"][0][2] == pytest.approx(90 + 20)  # the replacement lot inherits the disallowed loss


def test_a_sheltered_account_ignores_wash_sales_and_pays_no_tax():
    a, _ = _round_trip(60, status="sheltered")
    assert a["tax"]["wash_disallowed"] == 0 and a["tax"]["st"] == pytest.approx(-20_000)  # still tracked, just not taxed
    s = paper.summarize(a)
    assert s["tax_status"] == "sheltered" and s["est_tax"] == 0 and s["tax_drag"] == 0
    assert s["after_tax_return"] == pytest.approx(s["total_return"])


def test_a_sheltered_gain_is_untaxed_while_the_same_gain_in_a_taxable_account_is_not():
    book = book_with({"AAA": {0: 100.0, 100: 120.0}})
    out = {}
    for status in ("taxable", "sheltered"):
        a = acct("engine_tilt", tax_status=status, aid=status)
        trade(a, book, 0, {"AAA": 1.0})
        trade(a, book, 100, {})
        out[status] = paper.summarize(a)
    assert out["taxable"]["est_tax"] == pytest.approx(6_000) and out["sheltered"]["est_tax"] == 0
    assert out["sheltered"]["after_tax_return"] == pytest.approx(out["taxable"]["total_return"])
    assert out["taxable"]["after_tax_return"] == pytest.approx(out["taxable"]["total_return"] - 0.06)


def test_accounts_from_before_wash_tracking_or_tax_status_still_work():
    book = book_with({"AAA": {0: 100.0, 50: 80.0}})
    a = acct("engine_tilt")
    for k in ("recent_losses", "tax_status", "seed"):
        a.pop(k)
    a["tax"].pop("wash_disallowed"), a["tax"].pop("deferred_notional"), a["tax"].pop("deferred_sells")
    trade(a, book, 0, {"AAA": 1.0})
    trade(a, book, 50, {})  # a loss sale with none of the newer fields present
    s = paper.summarize(a)
    assert s["tax_status"] == "taxable" and s["realized_st"] == pytest.approx(-20_000) and s["wash_disallowed"] == 0
    a.pop("tax")
    assert paper.summarize(a)["wash_disallowed"] is None and paper.summarize(a)["tax_tracked"] is False


def test_unknown_tax_status_is_rejected():
    with pytest.raises(ValueError):
        acct(tax_status="offshore")


# ---------------------------------------------------------- the account set --


def test_sheltered_twins_trade_exactly_like_their_taxable_counterparts_and_only_the_tax_differs(fake):
    book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    a = fake.accounts
    assert {a[k]["tax_status"] for k in ("ctl_engine_ira", "ctl_placebo_ira")} == {"sheltered"} and a["ctl_engine"]["tax_status"] == "taxable"
    assert a["ctl_engine_ira"]["curve"] == a["ctl_engine"]["curve"]
    assert a["ctl_placebo_ira"]["curve"] == a["ctl_placebo"]["curve"]  # same placebo draw, so the comparison is fair
    eng, ira = paper.summarize(a["ctl_engine"]), paper.summarize(a["ctl_engine_ira"])
    assert ira["est_tax"] == 0 and ira["after_tax_return"] == pytest.approx(ira["total_return"]) and eng["total_return"] == pytest.approx(ira["total_return"])
    ta = a["ctl_taxaware"]
    assert ta["strategy"] == "engine_taxaware" and ta["tax_status"] == "taxable" and ta["tax"]["tracked"]


def test_rebuild_keeps_each_accounts_wrapper_and_placebo_seed(fake):
    book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    before = copy.deepcopy(fake.accounts)
    out = paper_cycle.rebuild_accounts(apply=True, book=book)
    assert out["differs"] == [] and out["replaced"] == len(before)
    for aid in ("ctl_engine_ira", "ctl_placebo_ira", "ctl_taxaware", "ctl_engine"):
        assert fake.accounts[aid]["tax_status"] == before[aid]["tax_status"] and fake.accounts[aid]["seed"] == before[aid]["seed"]
        assert fake.accounts[aid]["curve"] == before[aid]["curve"]


# ------------------------------------------------------- "if sold today" tax --


def test_if_sold_today_taxes_the_gains_not_yet_realised_so_buy_and_hold_is_not_free():
    book = book_with({"AAA": {0: 100.0, 450: 200.0}})
    a = acct("static_hold")
    trade(a, book, 0, {"AAA": 1.0})
    paper.refresh_unrealized(a, book, D[450])
    s = paper.summarize(a)
    assert s["est_tax"] == 0 and s["after_tax_return"] == pytest.approx(s["total_return"])  # nothing realised: untaxed so far
    assert s["liquidation_tax"] == pytest.approx(100_000 * 0.10)  # a 100,000 long-term gain at the 10% test rate
    assert s["after_tax_liquidated_return"] == pytest.approx(s["total_return"] - 0.10)


def test_liquidation_tax_nets_open_losses_against_open_gains_and_sheltered_accounts_owe_none(monkeypatch):
    monkeypatch.setattr(paper._risk, "risk_at", risk_is(None))
    book = book_with({"AAA": {0: 100.0, 100: 120.0}})
    a = acct("engine_tilt")
    trade(a, book, 0, {"AAA": 1.0})
    a["tax"]["st"] = -5_000.0  # an earlier realised short-term loss
    paper.refresh_unrealized(a, book, D[100])  # + 20,000 short-term unrealised gain
    assert paper.summarize(a)["liquidation_tax"] == pytest.approx(15_000 * 0.30)
    a["tax_status"] = "sheltered"
    s = paper.summarize(a)
    assert s["liquidation_tax"] == 0 and s["after_tax_liquidated_return"] == pytest.approx(s["total_return"])


def test_untracked_accounts_report_no_liquidation_figures():
    a = acct("engine_tilt")
    a.pop("tax")
    s = paper.summarize(a)
    assert s["liquidation_tax"] is None and s["after_tax_liquidated_return"] is None
