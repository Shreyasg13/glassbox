"""A user's committee-run paper portfolio: growth initial -> final, per-symbol P&L, the Monte Carlo estimate,
per-user agent record, and the admin's cross-user validation dataset. Synthetic prices, no network."""
from __future__ import annotations

import pytest

from app import paper, paper_cycle, portfolio_analytics as pa, portfolio_view as pv
from tests.test_paper_tax_committee import D, book_with

LIVE = 400  # index of the first live day
RUNS = [
    {"date": D[LIVE + 1], "symbol": "AAA", "decision": "SELL", "action": "SELL", "engine_signal": "BUY", "quorum_ok": True, "gate": None,
     "ceo": {"label": "strong consensus", "headline": "Valuation stretched"}, "answered": 10, "total": 10, "agents": []},
    {"date": D[LIVE + 2], "symbol": "BBB", "decision": "BUY", "action": "BUY", "engine_signal": "BUY", "quorum_ok": True, "gate": None,
     "ceo": {"label": "majority", "headline": "Steady"}, "answered": 9, "total": 10, "agents": []},
    {"date": D[10], "symbol": "ZZZ", "decision": "BUY", "action": "BUY", "engine_signal": "BUY", "quorum_ok": True, "gate": None, "ceo": {}, "answered": 10, "total": 10, "agents": []},
]


def make_book():
    prices = {"AAA": {0: 100.0, LIVE + 1: 100.0, LIVE + 5: 90.0, 500: 95.0}, "BBB": {0: 100.0, 450: 110.0}}
    signals = {"AAA": {i: "BUY" for i in range(5, 590)}, "BBB": {i: "BUY" for i in range(5, 590)}}
    book = book_with(prices, signals)
    book.set_committee({"AAA": {D[LIVE + 1]: "SELL"}, "BBB": {D[LIVE + 2]: "BUY"}})
    return book


def make_accounts(book, user="demo_growth", weights=None):
    weights = weights or {"AAA": 0.5, "BBB": 0.5}
    base, out = user, {}
    for aid, kind, strat in ((f"profile:{base}", "profile", "engine_tilt"), (f"committee:{base}", "twin", "committee_tilt"), (f"bench:{base}", "benchmark", "static_rebalanced")):
        a = paper.new_account(aid, aid, kind, strat, weights, invested=0.8, start_cash=100_000.0, risk_level="moderate", username=user, profile={"archetype": "growth"})
        paper.advance(a, book, live_from=D[LIVE])
        paper_cycle._refresh_holdings(a, book)
        out[aid] = a
    return out


@pytest.fixture(scope="module")
def world():
    book = make_book()
    return book, make_accounts(book)


# -------------------------------------------------------------------- growth --


def test_before_the_committee_started_its_account_is_identical_to_the_engines(world):
    book, accts = world
    eng, com = accts["profile:demo_growth"]["curve"], accts["committee:demo_growth"]["curve"]
    assert [p[1] for p in eng if p[2] == "backtest"] == [p[1] for p in com if p[2] == "backtest"]
    assert [p[1] for p in eng] != [p[1] for p in com]  # ...and they part ways once the committee overrules the engine


def test_view_reports_initial_to_final_profit_and_what_the_committee_added(world):
    book, accts = world
    v = pv.user_portfolio("demo_growth", book, RUNS, accts)
    c, e = v["committee"], v["engine"]
    assert c["initial"] == 100_000.0 and c["profit"] == pytest.approx(c["final"] - c["initial"], abs=0.01)
    assert c["return"] == pytest.approx(c["final"] / c["initial"] - 1)
    assert v["committee_added"]["dollars"] == pytest.approx(round(c["final"] - e["final"], 2))
    assert v["committee_added"]["dollars"] != 0  # the committee's SELL on AAA changed a trade
    assert v["is_model_portfolio"] is False and v["simulated"] is True and v["live_days"] > 0 and v["live_from"] == D[LIVE]
    cur = v["curves"]
    assert len(cur["dates"]) == len(cur["committee"]) == len(cur["engine"]) == len(cur["benchmark"])


def test_per_symbol_pnl_adds_up_to_total_profit_costs_included(world):
    book, accts = world
    v = pv.user_portfolio("demo_growth", book, RUNS, accts)
    assert sum(s["pnl"] for s in v["symbols"]) == pytest.approx(v["committee"]["profit"], abs=0.05)
    assert sum(s["engine_pnl"] for s in v["symbols"]) == pytest.approx(v["engine"]["profit"], abs=0.05)


def test_symbols_show_the_committee_call_its_reason_and_disagreement(world):
    book, accts = world
    rows = {s["symbol"]: s for s in pv.user_portfolio("demo_growth", book, RUNS, accts)["symbols"]}
    assert rows["AAA"]["committee_action"] == "SELL" and rows["AAA"]["disagrees"] is True and rows["AAA"]["headline"] == "Valuation stretched"
    assert rows["BBB"]["committee_action"] == "BUY" and rows["BBB"]["disagrees"] is False
    assert {"policy_weight", "current_weight", "value", "engine_signal"} <= set(rows["AAA"])


def test_decisions_only_include_the_users_own_symbols_and_trades_flag_committee_ones(world):
    book, accts = world
    v = pv.user_portfolio("demo_growth", book, RUNS, accts)
    assert {d["symbol"] for d in v["decisions"]} == {"AAA", "BBB"}  # ZZZ is not on this watchlist
    assert any(t["by_committee"] for t in v["trades"])


# --------------------------------------------------------- who can see what --


def test_no_account_means_no_result_for_admin_and_the_labelled_model_portfolio_for_a_user(world):
    book, accts = world
    assert pv.user_portfolio("nobody", book, RUNS, accts, allow_fallback=False) is None
    assert pv.user_portfolio("nobody", book, RUNS, accts) is None  # no ctl_* accounts here either
    model = dict(accts)
    for role, src in (("ctl_committee", "committee:demo_growth"), ("ctl_engine", "profile:demo_growth"), ("ctl_equal", "bench:demo_growth")):
        model[role] = dict(accts[src], id=role, name=role)
    v = pv.user_portfolio("nobody", book, RUNS, model)
    assert v["is_model_portfolio"] is True and "model portfolio" in v["label"]


def test_a_user_never_gets_another_users_numbers(world):
    book, accts = world
    other = make_accounts(book, "demo_income")
    both = {**accts, **other}
    assert pv.user_portfolio("demo_growth", book, RUNS, both)["committee"]["id"] == "committee:demo_growth"
    assert pv.user_portfolio("Demo_Income", book, RUNS, both)["committee"]["id"] == "committee:demo_income"  # case-insensitive, still only their own


def test_selectable_users_lists_only_those_with_a_committee_account(world):
    _book, accts = world
    users = pv.selectable_users([], accts)
    assert [u["username"] for u in users] == ["demo_growth"] and users[0]["tickers"] == ["AAA", "BBB"]


# --------------------------------------------------------------- Monte Carlo --


def test_monte_carlo_is_ordered_deterministic_and_bounded(world):
    _book, accts = world
    a = accts["committee:demo_growth"]
    m1, m2 = pa.monte_carlo(a), pa.monte_carlo(a)
    assert m1 == m2  # same data, same picture
    for h in m1["horizons"]:
        assert h["p5"] <= h["p25"] <= h["p50"] <= h["p75"] <= h["p95"]
        assert 0.0 <= h["prob_above_current"] <= 1.0 and 0.0 <= h["prob_loss_10pct"] <= 1.0
    assert [h["days"] for h in m1["horizons"]] == [21, 63, 252]
    assert m1["fan"]["start"] == pytest.approx(a["curve"][-1][1], abs=0.01) and len(m1["fan"]["p50"]) == len(m1["fan"]["days"])


def test_monte_carlo_refuses_a_too_short_history(world):
    _book, accts = world
    short = dict(accts["committee:demo_growth"], curve=accts["committee:demo_growth"]["curve"][:20])
    assert pa.monte_carlo(short) is None


# ------------------------------------------------- aggregate validation dataset --


def test_validation_rows_are_one_per_user_symbol_review_with_forward_returns(world):
    book, accts = world
    rows = pa.validation_rows([], book, RUNS, accts)
    assert {(r["symbol"], r["date"]) for r in rows} == {("AAA", D[LIVE + 1]), ("BBB", D[LIVE + 2])}  # ZZZ not on the watchlist
    aaa = next(r for r in rows if r["symbol"] == "AAA")
    assert aaa["disagrees_with_engine"] is True and aaa["account_acted"] is True and aaa["committee_action"] == "SELL"
    assert aaa["fwd_5d"] is not None
    assert aaa["committee_edge_5d"] == pytest.approx(-aaa["fwd_5d"])  # a SELL is right when the stock falls
    assert aaa["engine_edge_5d"] == pytest.approx(aaa["fwd_5d"])


def test_aggregate_pools_users_and_warns_they_are_not_independent(world):
    book, accts = world
    both = {**accts, **make_accounts(book, "demo_income")}
    agg = pa.aggregate([], book, RUNS, both)
    assert agg["users"] == 2 and agg["reviews"] == 4 and agg["live_days"] > 0
    assert agg["scored_reviews"] > 0 and agg["pooled"]["committee_hit_rate_5d"] is not None
    assert agg["pooled"]["committee_added_dollars"] == pytest.approx(sum(u["committee_added_dollars"] for u in agg["per_user"]))
    assert "NOT independent" in agg["note"]


def test_csv_export_has_a_header_and_one_line_per_row(world):
    book, accts = world
    rows = pa.validation_rows([], book, RUNS, accts)
    lines = pa.to_csv(rows).strip().split("\n")
    assert lines[0].startswith("user,archetype") and len(lines) == len(rows) + 1
    assert pa.to_csv([]) == ""


def test_agent_progress_scopes_to_the_users_symbols(world):
    book, _ = world
    out = pa.agent_progress(["AAA", "BBB"], book, RUNS)
    assert out["reviews"] == 2
