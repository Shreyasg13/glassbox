"""Daily paper-trading cycle + admin API: bootstrap, daily runs, idempotency,
frozen accounts, reports, the run lock, and the /api/admin/paper endpoints.
Uses an in-memory stand-in for app/db.py (same approach as test_auth.py) and
synthetic prices, so nothing touches a real database or price file."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import auth, data_source as ds, paper, paper_cycle, paper_profiles, rate_limit
from app.main import app

N_FULL, N_SHORT = 80, 60
DATES = pd.bdate_range("2024-01-02", periods=N_FULL)
PARAMS = {"rsi_low": 30, "rsi_high": 70, "fast_ma": 20, "slow_ma": 50}


def _frame(n, close_fn, buy=(), sell=()):
    rsi, fast, slow = [], [], []
    for i in range(n):
        if i in buy:
            rsi.append(20.0), fast.append(101.0), slow.append(100.0)
        elif i in sell:
            rsi.append(80.0), fast.append(99.0), slow.append(100.0)
        else:
            rsi.append(50.0), fast.append(100.0), slow.append(100.0)
    return pd.DataFrame({"Close": [close_fn(i) for i in range(n)], "RSI": rsi, "MA_20": fast, "MA_50": slow}, index=DATES[:n])


def make_book(n):
    frames = {
        "SPY": _frame(n, lambda i: 100 + i * 0.5),
        "AAA": _frame(n, lambda i: 50 + (i % 9) + i * 0.2, buy={10, 40}, sell={25}),
        "BBB": _frame(n, lambda i: 80 - i * 0.1 + (i % 4), buy={30}),
    }
    return paper.PriceBook.from_frames(frames, {s: PARAMS for s in frames})


def day(i):
    return DATES[i].strftime("%Y-%m-%d")


USERS = [
    {"username": "demo_a", "username_lower": "demo_a", "role": "viewer", "tickers": ["AAA", "BBB"],
     "profile": {"archetype": "growth", "risk_level": "aggressive", "horizon_years": 10, "starting_cash": 100000}},
    {"username": "demo_b", "username_lower": "demo_b", "role": "viewer", "tickers": ["SPY", "BBB", "ZZZ"],  # ZZZ has no price data
     "profile": {"archetype": "balanced", "risk_level": "moderate", "horizon_years": 5, "starting_cash": 50000,
                 "strategic_weights": {"SPY": 0.7, "BBB": 0.3}}},
    {"username": "no_profile", "username_lower": "no_profile", "role": "viewer", "tickers": ["AAA"]},
    {"username": "an_admin", "username_lower": "an_admin", "role": "admin", "tickers": ["AAA"], "profile": {"risk_level": "moderate"}},
    {"username": "no_tickers", "username_lower": "no_tickers", "role": "viewer", "tickers": [], "profile": {"risk_level": "moderate"}},
]


class FakeDB:
    def __init__(self, users):
        # deep copy: tests edit users (e.g. a changed watchlist) and must not leak into each other
        self.users, self.accounts, self.meta, self.signals, self.narratives, self.audit = _copy(list(users)), {}, None, {}, [], []

    def install(self, monkeypatch):
        db = paper_cycle.db
        m = monkeypatch.setattr
        m(db, "list_users", lambda: list(self.users))
        m(db, "list_paper_accounts", lambda: [dict(a) for a in self.accounts.values()])
        m(db, "get_paper_account", lambda i: dict(self.accounts[i]) if i in self.accounts else None)
        m(db, "save_paper_account", lambda a: self.accounts.__setitem__(a["id"], _copy(a)) or a)
        m(db, "get_paper_meta", lambda: dict(self.meta) if self.meta else None)
        m(db, "save_paper_meta", lambda x: setattr(self, "meta", dict(x)) or x)
        m(db, "save_paper_signals", lambda d, doc: self.signals.__setitem__(d, dict(doc, id=f"signals:{d}", date=d)) or doc)  # real db adds id/date
        m(db, "list_paper_signals", lambda limit=30: [self.signals[k] for k in sorted(self.signals, reverse=True)][:limit])
        m(db, "list_report_narratives", lambda: list(self.narratives))
        m(db, "create_report_narrative", lambda n: self.narratives.append(n) or n)
        m(db, "log_audit", lambda *a, **k: self.audit.append(a))


def _copy(a):
    import copy

    return copy.deepcopy(a)


@pytest.fixture
def fake(monkeypatch):
    f = FakeDB(USERS)
    f.install(monkeypatch)
    monkeypatch.delenv("PAPER_LLM_NARRATIVES", raising=False)
    # The real registry (11 profiles) is tested separately below; every other test
    # controls exactly who is in the cohort via USERS.
    monkeypatch.setattr(paper_profiles, "DEMO_PROFILES", [])
    rate_limit._admin_limiter._hits.clear()
    return f


# ---------------------------------------------------------------- bootstrap --


def test_bootstrap_creates_controls_profiles_and_benchmarks(fake):
    r = paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    ids = set(fake.accounts)
    assert {"ctl_spy", "ctl_equal", "ctl_engine", "ctl_placebo", "ctl_committee", "ctl_cash"} <= ids
    assert {"profile:demo_a", "bench:demo_a", "profile:demo_b", "bench:demo_b"} <= ids
    assert r["accounts"] == len(ids) == 10  # 6 controls + 2 profiles + 2 benchmarks
    assert not any(k for k in ids if "no_profile" in k or "an_admin" in k or "no_tickers" in k)  # skipped users


def test_bootstrap_history_is_all_backtest_and_live_starts_the_day_after_the_data(fake):
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    assert fake.meta["live_from"] > day(N_SHORT - 1) and fake.meta["last_date"] == day(N_SHORT - 1)
    for a in fake.accounts.values():
        assert {p[2] for p in a["curve"]} == {"backtest"} and a["last_date"] == day(N_SHORT - 1)
    assert fake.narratives == [] and fake.signals == {}  # no live day yet -> no reports


def test_profile_accounts_honour_strategic_weights_starting_cash_and_drop_unpriced_symbols(fake):
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    b = fake.accounts["profile:demo_b"]
    assert b["weights"] == pytest.approx({"SPY": 0.7, "BBB": 0.3})  # ZZZ (no data) dropped
    assert b["start_cash"] == 50000 and b["risk_level"] == "moderate" and b["benchmark_id"] == "bench:demo_b"
    assert b["invested"] == paper.RISK_POLICY["moderate"]["invested"]
    a = fake.accounts["profile:demo_a"]
    assert a["weights"] == {"AAA": 0.5, "BBB": 0.5}  # no strategic weights -> equal split
    assert fake.accounts["bench:demo_a"]["strategy"] == "static_rebalanced" and a["strategy"] == "engine_tilt"


def test_dry_run_saves_nothing(fake):
    r = paper_cycle.run_cycle(bootstrap=True, start=day(0), dry_run=True, book=make_book(N_SHORT))
    assert r["dry_run"] and r["accounts"] == 10
    assert fake.accounts == {} and fake.meta is None and fake.narratives == []


def test_cycle_refuses_to_run_before_bootstrap_and_refuses_a_second_bootstrap(fake):
    with pytest.raises(paper_cycle.CycleError, match="not initialised"):
        paper_cycle.run_cycle(book=make_book(N_SHORT))
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    with pytest.raises(paper_cycle.CycleError, match="already bootstrapped"):
        paper_cycle.run_cycle(bootstrap=True, book=make_book(N_SHORT))


def test_cycle_refuses_when_there_is_no_price_data(fake):
    with pytest.raises(paper_cycle.CycleError, match="no price data"):
        paper_cycle.run_cycle(bootstrap=True, book=paper.PriceBook())


def test_cycle_refuses_to_overlap_itself(fake):
    assert paper_cycle._cycle_lock.acquire(blocking=False)
    try:
        with pytest.raises(paper_cycle.CycleError, match="already running"):
            paper_cycle.run_cycle(bootstrap=True, book=make_book(N_SHORT))
    finally:
        paper_cycle._cycle_lock.release()


# -------------------------------------------------------------- daily runs --


def _bootstrap_then_advance(fake):
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    return paper_cycle.run_cycle(book=make_book(N_FULL))


def test_daily_run_processes_new_days_as_live_and_writes_signals_and_reports(fake):
    r = _bootstrap_then_advance(fake)
    assert r["new_live_days"] == [day(i) for i in range(N_SHORT, N_FULL)]
    assert set(fake.signals) == set(r["new_live_days"]) and len(fake.signals[day(N_FULL - 1)]["signals"]) == 3
    assert r["reports_written"] == 2  # one per profile, for the latest live day
    for a in fake.accounts.values():
        assert [p[2] for p in a["curve"]][-1] == "live" and a["last_date"] == day(N_FULL - 1)
        assert {p[2] for p in a["curve"] if p[0] < day(N_SHORT)} == {"backtest"}


def test_daily_run_is_idempotent_no_duplicate_days_reports_or_signals(fake):
    _bootstrap_then_advance(fake)
    snapshot = {k: _copy(v) for k, v in fake.accounts.items()}
    n_reports, n_signals = len(fake.narratives), len(fake.signals)
    again = paper_cycle.run_cycle(book=make_book(N_FULL))
    assert again["new_live_days"] == [] and again["days_processed"] == {} and again["reports_written"] == 0
    assert fake.accounts == snapshot and len(fake.narratives) == n_reports and len(fake.signals) == n_signals


def test_bootstrap_then_daily_runs_match_a_single_full_replay(fake):
    _bootstrap_then_advance(fake)
    step = {k: [p[:2] for p in v["curve"]] for k, v in fake.accounts.items()}
    fake2 = FakeDB(USERS)
    with pytest.MonkeyPatch.context() as mp:
        fake2.install(mp)
        paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_FULL))
    whole = {k: [p[:2] for p in v["curve"]] for k, v in fake2.accounts.items()}
    assert step == whole


def test_accounts_are_frozen_after_creation_but_new_users_are_backfilled(fake):
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    before = _copy(fake.accounts["profile:demo_a"])
    fake.users[0]["tickers"] = ["SPY"]  # user edits their watchlist later
    fake.users.append({"username": "late", "username_lower": "late", "role": "viewer", "tickers": ["SPY", "AAA"],
                       "profile": {"archetype": "x", "risk_level": "conservative", "horizon_years": 3, "starting_cash": 100000}})
    r = paper_cycle.run_cycle(book=make_book(N_FULL))
    assert fake.accounts["profile:demo_a"]["weights"] == before["weights"]  # history not rewritten
    assert fake.accounts["profile:demo_a"]["curve"][: len(before["curve"])] == before["curve"]
    assert r["accounts_created"] == ["bench:late", "profile:late"]
    assert fake.accounts["profile:late"]["inception"] == day(0)  # backfilled from the same start as everyone


# ----------------------------------------------------------------- reports --


def test_reports_are_written_as_system_narratives_with_the_key_facts(fake):
    _bootstrap_then_advance(fake)
    (rep_a,) = [n for n in fake.narratives if n["profile"] == "profile:demo_a"]
    assert rep_a["provider"] == "system" and rep_a["model"] == "paper-engine" and rep_a["date"] == day(N_FULL - 1).replace("-", "")
    text = rep_a["narrative"]
    for needle in ("demo_a", "SIMULATED", "not investment advice", "Equity $", "policy benchmark", "Holdings:", "Engine signals on this watchlist"):
        assert needle in text, needle
    assert "AAA" in text and "BBB" in text and "ZZZ" not in text


def test_llm_note_is_off_by_default_and_appended_when_enabled_and_failures_are_harmless(fake, monkeypatch):
    assert paper_cycle._llm_note("ctx") is None  # PAPER_LLM_NARRATIVES unset
    monkeypatch.setenv("PAPER_LLM_NARRATIVES", "1")
    monkeypatch.setattr(paper_cycle, "_llm_note", lambda ctx: "Momentum faded late in the week.")
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    paper_cycle.run_cycle(book=make_book(N_FULL))
    assert all("Analyst note (AI-generated, may be wrong)" in n["narrative"] and n["model"] == "paper-engine+llm" for n in fake.narratives)


def test_a_failing_llm_never_blocks_the_factual_report(fake, monkeypatch):
    monkeypatch.setenv("PAPER_LLM_NARRATIVES", "1")

    async def boom(*a, **k):
        raise RuntimeError("Gemini API error: HTTP 429")

    monkeypatch.setattr("app.llm_call_logging.complete_with_logging", boom)
    assert paper_cycle._llm_note("ctx") is None
    _bootstrap_then_advance(fake)
    assert len(fake.narratives) == 2 and all(n["model"] == "paper-engine" for n in fake.narratives)


# ------------------------------------------------------------- read models --


def test_downsample_keeps_first_and_last_and_respects_the_cap():
    curve = [[f"d{i}", float(i), "backtest"] for i in range(1000)]
    out = paper_cycle.downsample(curve, 50)
    assert len(out) <= 51 and out[0] == curve[0] and out[-1] == curve[-1]
    assert paper_cycle.downsample(curve[:10], 50) == curve[:10]


def test_overview_lists_profiles_first_with_alpha_against_their_benchmark(fake):
    _bootstrap_then_advance(fake)
    ov = paper_cycle.overview()
    kinds = [r["kind"] for r in ov["accounts"]]
    assert ov["initialised"] and kinds[:2] == ["profile", "profile"] and set(kinds) == {"profile", "benchmark", "control"}
    prof = next(r for r in ov["accounts"] if r["id"] == "profile:demo_a")
    assert prof["alpha"] is not None and prof["benchmark_id"] == "bench:demo_a" and prof["live_days"] == N_FULL - N_SHORT


def test_overview_before_bootstrap_says_so(fake):
    assert paper_cycle.overview() == {"initialised": False, "meta": None, "accounts": []}


def test_account_detail_has_curves_holdings_and_recent_trades_newest_first(fake):
    _bootstrap_then_advance(fake)
    d = paper_cycle.account_detail("profile:demo_a", max_points=20)
    assert len(d["curve"]) <= 21 and {p[0] for p in d["benchmark_curve"]} <= {p[0] for p in d["curve"]}
    trades = d["recent_trades"]
    assert trades == sorted(trades, key=lambda t: t["date"], reverse=True)
    assert set(d["holdings"]) <= {"AAA", "BBB"} and d["summary"]["id"] == "profile:demo_a"
    assert paper_cycle.account_detail("nope") is None


def test_scorecard_is_cached_until_forced(monkeypatch):
    calls = []
    monkeypatch.setattr(paper_cycle, "load_book", lambda: make_book(N_SHORT))
    monkeypatch.setattr(paper, "signal_scorecard", lambda book: calls.append(1) or {"in_sample": True})
    paper_cycle._scorecard_cache.clear()
    paper_cycle.scorecard()
    paper_cycle.scorecard()
    assert len(calls) == 1
    paper_cycle.scorecard(force=True)
    assert len(calls) == 2


# ----------------------------------------------------------------- HTTP API --


@pytest.fixture
def client():
    return TestClient(app)


def _auth(role, sub="someone"):
    return {"Authorization": "Bearer " + auth.create_access_token(auth.TokenPayload(sub=sub, role=role))}


ADMIN, VIEWER = _auth("admin", "admin"), _auth("viewer")


@pytest.mark.parametrize("method,path", [("get", "/api/admin/paper/overview"), ("get", "/api/admin/paper/scorecard"),
                                          ("get", "/api/admin/paper/signals"), ("get", "/api/admin/paper/accounts/ctl_spy"),
                                          ("post", "/api/admin/paper/run")])
def test_every_paper_endpoint_is_admin_only(client, fake, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers=VIEWER, **kwargs).status_code == 403


def test_api_run_needs_bootstrap_then_bootstraps_once_then_runs_daily(client, fake, monkeypatch):
    monkeypatch.setattr(paper_cycle, "load_book", lambda: make_book(N_SHORT))
    r = client.post("/api/admin/paper/run", json={}, headers=ADMIN)
    assert r.status_code == 409 and "bootstrap" in r.json()["detail"]
    r = client.post("/api/admin/paper/run", json={"bootstrap": True, "start": day(0)}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["accounts"] == 10
    assert client.post("/api/admin/paper/run", json={"bootstrap": True}, headers=ADMIN).status_code == 409
    monkeypatch.setattr(paper_cycle, "load_book", lambda: make_book(N_FULL))
    r = client.post("/api/admin/paper/run", json={}, headers=ADMIN)
    assert r.status_code == 200 and len(r.json()["new_live_days"]) == N_FULL - N_SHORT and r.json()["reports_written"] == 2
    assert any(a[1] == "paper.run" for a in fake.audit)  # admin action is audit-logged


def test_api_run_validates_the_start_date_format(client, fake):
    assert client.post("/api/admin/paper/run", json={"start": "01/02/2024"}, headers=ADMIN).status_code == 422


def test_api_overview_account_and_signals_after_a_run(client, fake, monkeypatch):
    monkeypatch.setattr(paper_cycle, "load_book", lambda: make_book(N_SHORT))
    client.post("/api/admin/paper/run", json={"bootstrap": True, "start": day(0)}, headers=ADMIN)
    monkeypatch.setattr(paper_cycle, "load_book", lambda: make_book(N_FULL))
    client.post("/api/admin/paper/run", json={}, headers=ADMIN)
    ov = client.get("/api/admin/paper/overview", headers=ADMIN).json()
    assert ov["initialised"] and len(ov["accounts"]) == 10
    acc = client.get("/api/admin/paper/accounts/profile:demo_a", headers=ADMIN)  # ids contain ':'
    assert acc.status_code == 200 and acc.json()["summary"]["id"] == "profile:demo_a"
    assert client.get("/api/admin/paper/accounts/nope", headers=ADMIN).status_code == 404
    sig = client.get("/api/admin/paper/signals?limit=3", headers=ADMIN).json()
    assert [s["date"] for s in sig] == [day(N_FULL - 1), day(N_FULL - 2), day(N_FULL - 3)]


def test_api_scorecard_reports_503_when_price_data_is_unavailable(client, fake, monkeypatch):
    def boom():
        raise FileNotFoundError("no parquet here")

    monkeypatch.setattr(paper_cycle, "load_book", boom)
    paper_cycle._scorecard_cache.clear()
    r = client.get("/api/admin/paper/scorecard?refresh=true", headers=ADMIN)
    assert r.status_code == 503 and "FileNotFoundError" in r.json()["detail"]


def test_system_reports_validate_against_the_narratives_response_model(client, fake, monkeypatch):
    # /api/reports/narratives has response_model List[DailyReportNarrative]; provider "system" must be accepted.
    from app import db as real_db

    _bootstrap_then_advance(fake)
    monkeypatch.setattr(real_db, "list_report_narratives", lambda: list(fake.narratives))
    r = client.get("/api/reports/narratives", headers=ADMIN)
    assert r.status_code == 200 and {n["provider"] for n in r.json()} == {"system"}
    assert all(n["profile"] and n["title"] for n in r.json())


# ---------------------------------------------------- the shared profile registry --


def test_registry_profiles_get_paper_accounts_without_any_login_rows(fake, monkeypatch):
    monkeypatch.setattr(
        paper_profiles, "DEMO_PROFILES",
        [{"username": "Reg_One", "tickers": ["AAA", "BBB"], "note": "n",
          "profile": {"archetype": "x", "risk_level": "conservative", "horizon_years": 5, "starting_cash": 75000}}],
    )
    fake.users.clear()  # nobody can log in as anything
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    a = fake.accounts["profile:reg_one"]
    assert a["username"] == "Reg_One" and a["start_cash"] == 75000 and a["risk_level"] == "conservative"
    assert a["benchmark_id"] == "bench:reg_one" and "bench:reg_one" in fake.accounts


def test_registry_wins_a_username_clash_and_real_users_with_profiles_are_still_added(fake, monkeypatch):
    monkeypatch.setattr(
        paper_profiles, "DEMO_PROFILES",
        [{"username": "demo_a", "tickers": ["SPY"], "note": "n", "profile": {"archetype": "registry", "risk_level": "moderate", "horizon_years": 5, "starting_cash": 100000}}],
    )
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=make_book(N_SHORT))
    assert fake.accounts["profile:demo_a"]["profile"]["archetype"] == "registry"  # not the user row's "growth"
    assert fake.accounts["profile:demo_a"]["weights"] == {"SPY": 1.0}
    assert "profile:demo_b" in fake.accounts  # a real user's profile outside the registry still counts
    assert sum(1 for k in fake.accounts if k == "profile:demo_a") == 1  # no duplicate


def test_the_real_registry_builds_all_28_accounts_on_a_full_universe_with_no_users(fake, monkeypatch):
    monkeypatch.undo()  # drop the fixture's empty-registry patch, keep everything else below explicit
    f = FakeDB([])
    with pytest.MonkeyPatch.context() as mp:
        f.install(mp)
        mp.delenv("PAPER_LLM_NARRATIVES", raising=False)
        frames = {sym: _frame(N_SHORT, lambda i, s=sym: 100 + i * 0.1 + len(s)) for sym in ds.STOCK_INFO}
        book = paper.PriceBook.from_frames(frames, {sym: PARAMS for sym in frames})
        r = paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    assert len(paper_profiles.DEMO_PROFILES) == 11
    assert r["accounts"] == len(f.accounts) == 6 + 11 * 2  # controls + (profile + benchmark) per registry entry
    assert sum(1 for a in f.accounts.values() if a["kind"] == "profile") == 11


def test_registry_is_valid_against_the_tracked_universe():
    seen = set()
    for p in paper_profiles.DEMO_PROFILES:
        assert p["username"].lower() not in seen and p["username"].lower() not in auth.RESERVED_USERNAMES
        seen.add(p["username"].lower())
        assert p["tickers"] and set(p["tickers"]) <= set(ds.STOCK_INFO) and len(set(p["tickers"])) == len(p["tickers"])
        prof = p["profile"]
        assert prof["risk_level"] in paper.RISK_POLICY and prof["horizon_years"] > 0 and prof["starting_cash"] > 0
        if "strategic_weights" in prof:
            assert set(prof["strategic_weights"]) == set(p["tickers"]) and sum(prof["strategic_weights"].values()) == pytest.approx(1.0)
