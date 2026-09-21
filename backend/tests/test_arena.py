"""The arena: challengers' calls, the account that trades them, and the shared evidence gate."""
from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from app import arena, paper, paper_cycle, research, strategy
from app.scripts import record_challenger
from tests.test_paper_cycle import N_FULL, fake, make_book as cycle_book, day  # noqa: F401  (fake is a fixture)
from tests.test_research import acct as curve_acct, noise


class MemDB:
    def __init__(self):
        self.rows = {}

    def install(self, mp):
        def save(source, d, symbol, action, meta=None):
            doc = {"id": f"chal:{source}:{d}:{symbol}", "source": source, "date": d, "symbol": symbol, "action": action, "meta": meta or {}}
            self.rows[doc["id"]] = doc
            return doc

        mp.setattr(arena.db, "save_challenger_decision", save)
        mp.setattr(arena.db, "list_challenger_decisions", lambda source=None: [copy.deepcopy(r) for r in self.rows.values() if source is None or r["source"] == source])
        mp.setattr(paper_cycle.db, "list_challenger_decisions", lambda source=None: [copy.deepcopy(r) for r in self.rows.values() if source is None or r["source"] == source])


@pytest.fixture
def mem(monkeypatch):
    m = MemDB()
    m.install(monkeypatch)
    monkeypatch.setattr(arena.ds, "STOCK_INFO", {"AAA": {}, "BBB": {}, "SPY": {}})
    return m


# --------------------------------------------------------------------- intake --


@pytest.mark.parametrize(
    "raw,expected",
    [("BUY", "BUY"), ("buy", "BUY"), ("**SELL**", "SELL"), ("Final decision: Overweight", "BUY"), ("Strong Buy", "BUY"), ("Underweight.", "SELL"),
     ("HOLD - wait for confirmation", "HOLD"), ("Neutral", "HOLD"), ("I would not buy, hold instead", "BUY")],
)
def test_common_ways_of_saying_it_map_to_buy_sell_hold(raw, expected):
    assert arena.normalize_decision(raw) == expected  # the EARLIEST call word wins (the last case documents that rule)


@pytest.mark.parametrize("raw", ["", "maybe later", None, 5, "no idea"])
def test_an_unreadable_answer_is_never_guessed(raw):
    assert arena.normalize_decision(raw) is None


def test_recording_validates_the_source_the_date_and_never_accepts_the_future(mem):
    with pytest.raises(ValueError, match="source"):
        arena.record("Bad Name!", "2026-09-01", {"AAA": "BUY"})
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        arena.record("ta", "09/01/2026", {"AAA": "BUY"})
    with pytest.raises(ValueError, match="future"):
        arena.record("tradingagents", "2026-09-25", {"AAA": "BUY"}, today=date(2026, 9, 21))
    assert mem.rows == {}


def test_recording_stores_normalised_calls_and_reports_what_it_skipped(mem):
    out = arena.record("tradingagents", "2026-09-18", [{"symbol": "aaa", "decision": "Overweight", "note": "why"}, {"symbol": "ZZZ", "decision": "BUY"}, {"symbol": "BBB", "decision": "???"}])
    assert out["recorded"] == 1 and {s for s, _ in out["skipped"]} == {"ZZZ", "BBB"}
    row = mem.rows["chal:tradingagents:2026-09-18:AAA"]
    assert row["action"] == "BUY" and row["meta"] == {"note": "why"}
    arena.record("tradingagents", "2026-09-18", {"AAA": "SELL"})  # the same key is replaced, not duplicated
    assert len(mem.rows) == 1 and mem.rows["chal:tradingagents:2026-09-18:AAA"]["action"] == "SELL"


def test_the_summary_describes_each_challenger(mem):
    arena.record("tradingagents", "2026-09-17", {"AAA": "BUY", "BBB": "HOLD"})
    arena.record("tradingagents", "2026-09-18", {"AAA": "SELL"})
    arena.record("other-bot", "2026-09-18", {"SPY": "HOLD"})
    s = {r["source"]: r for r in arena.summary()}
    assert s["tradingagents"] == {"source": "tradingagents", "calls": 3, "first": "2026-09-17", "last": "2026-09-18", "days": 2, "symbols": 2, "mix": {"BUY": 1, "SELL": 1, "HOLD": 1}}
    assert len(arena.summary("other-bot")) == 1


def test_the_cli_records_lists_and_rejects_bad_input(mem, tmp_path, capsys):
    f = tmp_path / "today.json"
    f.write_text(json.dumps({"AAA": "BUY", "BBB": "sell"}))
    assert record_challenger.main(["--source", "tradingagents", "--date", "2026-09-18", "--file", str(f)]) == 0
    assert record_challenger.main(["--source", "tradingagents", "--date", "2026-09-18", "--symbol", "SPY", "--decision", "hold"]) == 0
    assert len(mem.rows) == 3
    capsys.readouterr()
    assert record_challenger.main(["--list"]) == 0 and '"calls": 3' in capsys.readouterr().out
    assert record_challenger.main(["--source", "x", "--date", "2026-09-18", "--symbol", "AAA", "--decision", "BUY"]) == 1  # source too short
    assert record_challenger.main(["--source", "tradingagents", "--date", "2099-01-01", "--symbol", "AAA", "--decision", "BUY"]) == 1
    assert record_challenger.main(["--source", "tradingagents", "--date", "2026-09-18", "--symbol", "AAA", "--decision", "???"]) == 1  # nothing readable


# ------------------------------------------------------------ storage isolation --


@pytest.fixture
def real_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine

    from app import db as real

    eng = create_engine(f"sqlite:///{tmp_path / 'arena.db'}", connect_args={"check_same_thread": False})
    real.metadata.create_all(eng)
    monkeypatch.setattr(real, "engine", eng)
    return real


def test_challenger_calls_never_appear_among_our_committee_decisions(real_db):
    real_db.save_committee_run({"id": "2026-09-18:AAA", "date": "2026-09-18", "symbol": "AAA", "decision": "HOLD"})
    real_db.save_challenger_decision("tradingagents", "2026-09-18", "AAA", "BUY")
    real_db.save_challenger_decision("tradingagents", "2026-09-18", "AAA", "SELL")  # replaces
    assert [r["symbol"] for r in real_db.list_all_committee_runs()] == ["AAA"] and real_db.list_all_committee_runs()[0]["decision"] == "HOLD"
    assert len(real_db.list_committee_runs_for_date("2026-09-18")) == 1 and len(real_db.list_committee_runs()) == 1
    ch = real_db.list_challenger_decisions()
    assert len(ch) == 1 and ch[0]["action"] == "SELL" and ch[0]["source"] == "tradingagents"
    assert real_db.list_challenger_decisions("someone-else") == []


# ---------------------------------------------------------------- paper account --


def bookwith(calls):
    book = cycle_book(N_FULL)
    book.set_external("ta", calls)
    return book


def test_a_challengers_call_stays_fresh_for_five_trading_days_and_never_leaks_forward():
    book = bookwith({"AAA": {day(30): "SELL"}})
    assert book.external_at("ta", "AAA", day(29)) is None
    assert book.external_at("ta", "AAA", day(30)) == "SELL"
    assert book.external_at("ta", "AAA", day(30 + paper.COMMITTEE_MAX_AGE_DAYS)) == "SELL"
    assert book.external_at("ta", "AAA", day(30 + paper.COMMITTEE_MAX_AGE_DAYS + 1)) is None
    assert book.external_at("nobody", "AAA", day(30)) is None and book.external_at(None, "AAA", day(30)) is None


def test_the_challenger_account_follows_its_calls_and_is_neutral_where_it_is_silent_never_our_engine():
    book = bookwith({"AAA": {day(10): "SELL"}})
    a = paper.new_account("chal_ta", "Challenger: ta", "control", "external_tilt", {"AAA": 0.5, "BBB": 0.5}, invested=0.8, source="ta")
    w, reasons, sigs = paper._target_weights(a, book, day(10))
    assert sigs == {"AAA": "SELL", "BBB": "HOLD"}  # BBB: no call, so neutral even if our engine had a view
    assert w["AAA"] < w["BBB"] and reasons["AAA"] == "ta SELL" and "neutral" in reasons["BBB"]
    engine = paper.new_account("e", "E", "control", "engine_tilt", {"AAA": 0.5, "BBB": 0.5}, invested=0.8)
    assert paper._target_weights(engine, book, day(10))[2] != sigs  # it really is a different decision-maker


def test_the_cycle_creates_a_challenger_account_only_once_calls_exist_and_a_rebuild_reproduces_it(fake, mem):
    book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    assert not any(k.startswith("chal_") for k in fake.accounts)
    calls = {"AAA": {day(50): "BUY", day(60): "SELL"}, "BBB": {day(55): "BUY"}}
    book.set_external("tradingagents", calls)
    paper_cycle.run_cycle(book=book)
    acct = fake.accounts["chal_tradingagents"]
    assert acct["strategy"] == "external_tilt" and acct["source"] == "tradingagents" and acct["kind"] == "control" and acct["curve"]
    assert acct["trade_count"] > 0
    before = copy.deepcopy(acct["curve"])
    out = paper_cycle.rebuild_accounts(apply=True, book=book)
    assert out["accounts"]["chal_tradingagents"] == "identical" and fake.accounts["chal_tradingagents"]["source"] == "tradingagents"
    assert fake.accounts["chal_tradingagents"]["curve"] == before


def test_challenger_views_load_from_the_store(mem):
    arena.record("tradingagents", "2026-09-17", {"AAA": "BUY"})
    arena.record("tradingagents", "2026-09-18", {"AAA": "SELL", "BBB": "hold"})
    assert paper_cycle.challenger_views() == {"tradingagents": {"AAA": {"2026-09-17": "BUY", "2026-09-18": "SELL"}, "BBB": {"2026-09-18": "HOLD"}}}


# --------------------------------------------------------- the shared scoreboard --


def test_a_challenger_faces_the_same_evidence_gate_as_our_own_strategies():
    base = noise(90, 0.0004, 0.01, 1)
    accounts = [
        curve_acct("ctl_equal", base),
        curve_acct("ctl_placebo", noise(90, 0.0004, 0.01, 2)),
        curve_acct("ctl_engine", noise(90, 0.0004, 0.01, 3)),
        {**curve_acct("chal_tradingagents", [b + 0.003 for b in base]), "name": "Challenger: tradingagents", "strategy": "external_tilt"},
    ]
    rows = {r["id"]: r for r in research.evidence_table(accounts)}
    assert set(rows) == {"ctl_engine", "chal_tradingagents"}
    ch = rows["chal_tradingagents"]
    assert ch["challenger"] is True and rows["ctl_engine"]["challenger"] is False and ch["name"] == "Challenger: tradingagents"
    assert set(ch["vs"]) == {"ctl_equal", "ctl_placebo"}
    assert ch["vs"]["ctl_equal"]["verdict"] == "edge" and ch["vs"]["ctl_equal"]["mean_excess_bps"] == pytest.approx(30.0)  # same rules, same gate
    assert research.build_proposals([ch], {"agents": []})[0].startswith("Challenger: tradingagents has beaten equal-weight hold")


def test_users_never_see_a_challenger_in_the_track_record(fake, mem, monkeypatch):
    book = cycle_book(N_FULL)
    book.set_external("tradingagents", {"AAA": {day(50): "BUY"}})
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=book)
    assert "chal_tradingagents" in fake.accounts
    monkeypatch.setattr(strategy.db, "list_paper_accounts", lambda: [copy.deepcopy(a) for a in fake.accounts.values()])
    monkeypatch.setattr(strategy.db, "get_paper_meta", lambda: dict(fake.meta))
    tr = strategy.track_record()
    assert all(s["id"] in strategy.CONTROL_ORDER for s in tr["strategies"]) and set(tr["curves"]) <= set(strategy.CONTROL_ORDER)
    assert "chal_tradingagents" not in {s["id"] for s in tr["strategies"]}
    admin = strategy._control_rows(list(fake.accounts.values()))
    assert "chal_tradingagents" in {r["id"] for r in admin}  # the admin does
