"""A hole in the price history (the daily sync once appended 10 days to a file that ended 8 months earlier)
must be healed by the updater and must never masquerade as a huge one-day return in the analytics."""
from __future__ import annotations

import random
from types import SimpleNamespace

import pandas as pd
import pytest

from app import associations, paper, paper_cycle, research, risk, strategy
from app.scripts import update_daily_data as ud
from tests.test_paper_cycle import fake, make_book as cycle_book, day, N_FULL  # noqa: F401  (fake is a fixture)

PARAMS = {"rsi_low": 30, "rsi_high": 70, "fast_ma": 20, "slow_ma": 50}


def ohlcv(index, start=100.0, seed=1):
    rnd, px, closes = random.Random(seed), start, []
    for _ in index:
        px *= 1 + rnd.gauss(0.0003, 0.01)
        closes.append(px)
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1_000_000.0}, index=index)


# ------------------------------------------------------------------- updater --


def test_find_gaps_ignores_weekends_and_holidays_but_reports_real_holes():
    ok = pd.bdate_range("2025-12-15", "2026-01-15")  # spans Christmas and New Year
    assert ud.find_gaps(ok) == []
    holed = ok[:10].append(pd.bdate_range("2026-08-20", periods=5))
    gaps = ud.find_gaps(holed)
    assert len(gaps) == 1 and gaps[0][0] == "2025-12-26" and gaps[0][1] == "2026-08-20" and gaps[0][2] > 200


def test_the_updater_fetches_from_the_last_stored_bar_and_backfills_a_long_hole(tmp_path, monkeypatch):
    data = tmp_path / "data_parquet"
    data.mkdir()
    old_idx = pd.bdate_range("2025-01-02", "2025-12-29")
    ohlcv(old_idx).to_parquet(data / "AAA.parquet")
    calls = {}

    class FakeTicker:
        def __init__(self, sym):
            pass

        def history(self, **kw):
            calls.update(kw)
            return ohlcv(pd.bdate_range(kw["start"], "2026-09-18"), start=120.0, seed=2)  # everything since `start`

    monkeypatch.setattr(ud, "yf", SimpleNamespace(Ticker=FakeTicker))
    ok, msg = ud.update_symbol("AAA", data)
    assert ok, msg
    assert calls == {"start": "2025-12-22"}  # 7 days before the last stored bar, NOT "the last 10 days"
    merged = pd.read_parquet(data / "AAA.parquet")
    assert ud.find_gaps(merged.index) == [] and merged.index.max() == pd.Timestamp("2026-09-18")
    assert merged.index.min() == old_idx.min() and {"RSI", "MA_50", "Volatility"} <= set(merged.columns)
    assert merged["RSI"].iloc[-1] == merged["RSI"].iloc[-1]  # indicators were recomputed over the filled history (not NaN)


def test_the_updater_heals_a_hole_in_the_MIDDLE_of_the_file_not_just_at_its_end(tmp_path, monkeypatch):
    """The real failure: a bad first run left 2025-12-29 -> 2026-08-20 missing, then later runs appended recent days after it."""
    data = tmp_path / "data_parquet"
    data.mkdir()
    holed = pd.bdate_range("2025-01-02", "2025-12-29").append(pd.bdate_range("2026-08-20", "2026-09-17"))
    ohlcv(holed).to_parquet(data / "AAA.parquet")
    assert len(ud.find_gaps(holed)) == 1
    seen = {}

    class T:
        def __init__(self, sym):
            pass

        def history(self, **kw):
            seen.update(kw)
            return ohlcv(pd.bdate_range(kw["start"], "2026-09-18"), start=130.0, seed=4)

    monkeypatch.setattr(ud, "yf", SimpleNamespace(Ticker=T))
    ok, msg = ud.update_symbol("AAA", data)
    assert ok, msg
    assert seen["start"] == "2025-12-22"  # 7 days before the START of the hole, though the last stored bar was in September
    merged = pd.read_parquet(data / "AAA.parquet")
    assert ud.find_gaps(merged.index) == [] and merged.index.max() == pd.Timestamp("2026-09-18") and merged.index.min() == holed.min()


def test_the_updater_still_refuses_to_shrink_or_shift_the_history(tmp_path, monkeypatch):
    data = tmp_path / "data_parquet"
    data.mkdir()
    ohlcv(pd.bdate_range("2025-01-02", "2025-12-29")).to_parquet(data / "AAA.parquet")

    class LaterStart:
        def __init__(self, sym):
            pass

        def history(self, **kw):
            return pd.DataFrame()  # nothing came back

    monkeypatch.setattr(ud, "yf", SimpleNamespace(Ticker=LaterStart))
    ok, msg = ud.update_symbol("AAA", data)
    assert not ok and "no data" in msg
    assert len(pd.read_parquet(data / "AAA.parquet")) == len(pd.bdate_range("2025-01-02", "2025-12-29"))  # untouched


def test_an_up_to_date_file_only_refetches_the_overlap(tmp_path, monkeypatch):
    data = tmp_path / "data_parquet"
    data.mkdir()
    ohlcv(pd.bdate_range("2026-01-02", "2026-09-17")).to_parquet(data / "AAA.parquet")
    seen = {}

    class T:
        def __init__(self, sym):
            pass

        def history(self, **kw):
            seen.update(kw)
            return ohlcv(pd.bdate_range(kw["start"], "2026-09-18"), seed=3)

    monkeypatch.setattr(ud, "yf", SimpleNamespace(Ticker=T))
    ok, msg = ud.update_symbol("AAA", data)
    assert ok and seen["start"] == "2026-09-10" and "rows" in msg


# --------------------------------------------------------- the analytics --


def holed_book(jump=0.35, n_before=420, n_after=120):
    """Two unrelated noisy stocks with an 8-month hole in the middle: the first bar after it is a multi-month move."""
    idx = pd.bdate_range("2024-01-02", periods=n_before).append(pd.bdate_range("2026-01-05", periods=n_after))
    frames = {}
    for k, sym in enumerate(("AAA", "BBB")):
        rnd, px, closes = random.Random(10 + k), 100.0, []
        for i in range(len(idx)):
            px *= 1 + rnd.gauss(0.0003, 0.008)
            if i == n_before:
                px *= 1 + jump  # both jump across the hole
            closes.append(px)
        frames[sym] = pd.DataFrame({"Close": closes, "RSI": 50.0, "MA_20": 100.0, "MA_50": 100.0}, index=idx)
    return paper.PriceBook.from_frames(frames, {s: PARAMS for s in frames})


def test_the_book_reports_its_holes():
    book = holed_book()
    g = book.gaps()
    assert len(g) == 1 and g[0]["days"] > 100 and g[0]["from"] < "2026-01-01" < g[0]["to"]
    assert cycle_book(N_FULL).gaps() == []


def test_a_return_across_a_hole_does_not_inflate_correlations():
    book = holed_book()
    d = book.dates[book.dates.index(next(x for x in book.dates if x >= "2026-01-05")) + 5]  # a few bars after the hole
    r = associations.correlations(book, d)
    assert abs(r["AAA"]["BBB"]) < 0.4  # unrelated stocks: only the fake "same-day jump" could make them look tied
    naive = associations._pearson(*[[x for x in associations.aligned_returns(book, d, 60)[s]] for s in ("AAA", "BBB")])
    assert naive == r["AAA"]["BBB"]


def test_a_return_across_a_hole_does_not_create_volatility_or_risk():
    book = holed_book(jump=0.35)
    first_after = next(i for i, x in enumerate(book.dates) if x >= "2026-01-05")
    closes = [book.close["AAA"][x] for x in book.dates]
    with_dates = risk.compute_series(closes, book.dates)[first_after + 3]
    naive = risk.compute_series(closes)[first_after + 3]
    assert naive is not None and with_dates is not None
    assert naive["vol"] > 2 * with_dates["vol"]  # without the mask the jump reads as a 35% one-day move
    assert with_dates["vol"] < 0.25 and with_dates["level"] != "HIGH"


def test_basket_volatility_ignores_the_return_that_spans_a_hole():
    book = holed_book(jump=0.35)
    d = book.dates[next(i for i, x in enumerate(book.dates) if x >= "2026-01-05") + 3]
    vol = paper._basket_vol(book, {"AAA": 0.5, "BBB": 0.5}, d)
    assert vol is not None and vol < 0.25  # ordinary daily noise, not a 35% day annualised


def test_the_overview_and_the_digest_warn_about_a_hole(monkeypatch):
    monkeypatch.setattr(strategy.db, "list_all_committee_runs", lambda: [])
    monkeypatch.setattr(strategy.db, "list_paper_accounts", lambda: [])
    monkeypatch.setattr(strategy.db, "get_paper_meta", lambda: None)
    dq = strategy.overview(holed_book())["data_quality"]
    assert dq["ok"] is False and dq["gaps"][0]["days"] > 100
    assert strategy.overview(cycle_book(N_FULL))["data_quality"] == {"gaps": [], "ok": True}
    monkeypatch.setattr(research.db, "list_paper_accounts", lambda: [])
    monkeypatch.setattr(research.db, "list_all_committee_runs", lambda: [])
    text = research.build_digest(holed_book(), [], [])["text"]
    assert "DATA QUALITY WARNING" in text and "calendar days" in text
    assert "DATA QUALITY WARNING" not in research.build_digest(cycle_book(N_FULL), [], [])["text"]


# ------------------------------------------------- rebuilding after a data fix --


def test_after_the_prices_are_corrected_a_rebuild_can_replace_every_account_and_shows_old_vs_new(fake):
    old_book = cycle_book(N_FULL)
    paper_cycle.run_cycle(bootstrap=True, start=day(0), book=old_book)
    before = {aid: a["curve"][-1][1] for aid, a in fake.accounts.items()}
    # the corrected prices: same calendar, every close 10% higher from bar 40 on
    fixed = cycle_book(N_FULL)
    for sym in fixed.close:
        for i, d in enumerate(fixed._sorted_dates[sym]):
            if i >= 40:
                fixed.close[sym][d] *= 1.10
    dry = paper_cycle.rebuild_accounts(book=fixed)
    assert dry["differs"] and dry["replaced"] == 0
    kept = paper_cycle.rebuild_accounts(apply=True, book=fixed)  # default: only replaces accounts that replay identically
    assert kept["replaced"] < len(before)
    out = paper_cycle.rebuild_accounts(apply=True, book=fixed, allow_differences=True)
    assert out["replaced"] == len(before)
    changed = [aid for aid, c in out["changes"].items() if c["old_total"] != pytest.approx(c["new_total"])]
    assert changed and all(fake.accounts[aid]["curve"][-1][1] != before[aid] or aid in ("ctl_cash",) for aid in changed)
