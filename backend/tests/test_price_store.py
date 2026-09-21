"""The price store: DB is the source of truth, deltas only, final bars only, parquet is a rebuildable cache."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app import price_store as ps
from app.scripts import update_daily_data as ud


def ohlcv(index, start=100.0, seed=1, tz=True):
    rnd, px, rows = random.Random(seed), start, []
    for _ in index:
        o = px
        px *= 1 + rnd.gauss(0.0003, 0.01)
        rows.append((o, max(o, px) * 1.004, min(o, px) * 0.996, px, float(rnd.randint(1_000_000, 90_000_000)), 0.0, 0.0))
    df = pd.DataFrame(rows, columns=ps.RAW_COLS, index=index)
    if tz:
        df.index = pd.DatetimeIndex(df.index).tz_localize(ps.ET)
    df.index.name = "Date"
    df["Volume"] = df["Volume"].astype("int64")
    return df


def utc(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


# --------------------------------------------------------------- the calendar --


def test_a_bar_is_final_only_after_the_close_in_new_york_time_in_summer_and_winter():
    assert ps.final_cutoff(utc(2026, 7, 15, 20, 10)) == "2026-07-14"  # 16:10 EDT: the closing prices are not settled yet
    assert ps.final_cutoff(utc(2026, 7, 15, 20, 20)) == "2026-07-15"  # 16:20 EDT
    assert ps.final_cutoff(utc(2026, 1, 15, 21, 10)) == "2026-01-14"  # 16:10 EST
    assert ps.final_cutoff(utc(2026, 1, 15, 21, 20)) == "2026-01-15"  # 16:20 EST
    assert ps.final_cutoff(utc(2026, 7, 15, 15, 0)) == "2026-07-14"  # mid-session
    assert str(ps.last_weekday(datetime(2026, 9, 20).date())) == "2026-09-18"  # a Sunday -> Friday


# ------------------------------------------------------------ rows and frames --


def test_a_provisional_bar_for_a_session_still_open_is_never_stored():
    df = ohlcv(pd.bdate_range("2026-09-14", "2026-09-18"))
    rows, rej, not_final = ps.frame_to_rows("AAA", df, now=utc(2026, 9, 18, 19, 0))  # 15:00 EDT on the 18th
    assert [r["d"] for r in rows][-1] == "2026-09-17" and not_final == 1 and rej == []
    rows2, _r, nf2 = ps.frame_to_rows("AAA", df, now=utc(2026, 9, 18, 21, 0))  # 17:00 EDT: the 18th is final
    assert rows2[-1]["d"] == "2026-09-18" and nf2 == 0


def test_bars_that_fail_sanity_are_rejected_and_reported_not_stored():
    df = ohlcv(pd.bdate_range("2026-09-01", periods=6))
    df.iloc[2, df.columns.get_loc("Close")] = -5.0
    df.iloc[3, df.columns.get_loc("High")] = df.iloc[3]["Low"] - 1.0
    df.iloc[5, df.columns.get_loc("Close")] = df.iloc[4]["Close"] * 1.9  # +90% in a day
    rows, rej, _ = ps.frame_to_rows("AAA", df, now=utc(2026, 9, 30, 1))
    assert [r["d"] for r in rows] == ["2026-09-01", "2026-09-02", "2026-09-07"] and len(rej) == 3  # 09-03 negative, 09-04 high<low, 09-08 +90%
    assert {r["why"].split(" ")[0] for r in rej} >= {"non-positive", "high"}
    assert any("one day" in r["why"] for r in rej)
    imported, _r, _n = ps.frame_to_rows("AAA", df, trust=True)  # history we already hold is taken as-is
    assert len(imported) == 6


def test_the_first_fresh_bar_is_checked_against_the_last_stored_close():
    df = ohlcv(pd.bdate_range("2026-09-14", periods=2))
    rows, rej, _ = ps.frame_to_rows("AAA", df, prev_close=df.iloc[0]["Close"] / 3, now=utc(2026, 9, 30, 1))
    assert rows == [] and [r["date"] for r in rej] == ["2026-09-14", "2026-09-15"]  # an unadjusted split keeps quarantining until the source fixes it
    ok_rows, ok_rej, _ = ps.frame_to_rows("AAA", df, prev_close=df.iloc[0]["Close"] * 1.01, now=utc(2026, 9, 30, 1))
    assert len(ok_rows) == 2 and ok_rej == []


# ---------------------------------------------------- round trip and rebuilding --


def seed_parquet(tmp_path, symbol="AAA", n=400, seed=1):
    d = tmp_path / "data_parquet"
    d.mkdir(exist_ok=True)
    df = ps.recompute_indicators(ohlcv(pd.bdate_range("2025-01-02", periods=n), seed=seed))
    df.to_parquet(d / f"{symbol}.parquet")
    return d, df


def test_importing_a_parquet_and_rebuilding_from_the_database_reproduces_it_exactly(real_db, tmp_path):
    d, original = seed_parquet(tmp_path)
    assert ps.import_parquet("AAA", d) == len(original)
    check = ps.verify_roundtrip("AAA", d)
    assert check["ok"] and check["max_abs_diff"] == 0.0 and check["dtypes_equal"] and check["rows"] == len(original)
    on_disk = pd.read_parquet(d / "AAA.parquet")
    (d / "AAA.parquet").unlink()  # the VM's disk is gone
    assert ps.materialize_all(d) == ["AAA"]
    assert_frame_equal(pd.read_parquet(d / "AAA.parquet"), on_disk, check_freq=False)  # bit-for-bit what it was


def test_the_import_is_idempotent_and_corrections_overwrite(real_db, tmp_path):
    d, _ = seed_parquet(tmp_path)
    ps.import_parquet("AAA", d)
    ps.import_parquet("AAA", d)
    assert real_db.price_bars_summary()["AAA"]["count"] == 400  # the same rows twice: nothing duplicated
    bars = real_db.load_price_bars("AAA")
    fixed = dict(bars[-1], close=999.0)
    real_db.upsert_price_bars([fixed])
    assert real_db.load_price_bars("AAA")[-1]["close"] == 999.0 and real_db.price_bars_summary()["AAA"]["count"] == 400


def test_the_data_version_changes_only_when_bars_are_added(real_db, tmp_path):
    d, _ = seed_parquet(tmp_path)
    ps.import_parquet("AAA", d)
    v1 = ps.data_version()
    ps.import_parquet("AAA", d)
    assert ps.data_version() == v1
    real_db.upsert_price_bars([dict(real_db.load_price_bars("AAA")[-1], d="2099-01-01")])
    assert ps.data_version() != v1


# ---------------------------------------------------------------- the updater --


def fake_yf(monkeypatch, frame_for_start):
    seen = {}

    class T:
        def __init__(self, sym):
            self.sym = sym

        def history(self, **kw):
            seen.setdefault(self.sym, []).append(kw)
            return frame_for_start(self.sym, kw["start"])

    monkeypatch.setattr(ud, "yf", SimpleNamespace(Ticker=T))
    return seen


def test_the_first_run_seeds_the_database_then_fetches_only_the_delta(real_db, tmp_path, monkeypatch):
    d, original = seed_parquet(tmp_path, n=300)  # bars to 2026-02-... : find the last stored date
    last = original.index[-1].date()
    fresh_idx = pd.bdate_range(last - pd.Timedelta(days=7), last + pd.Timedelta(days=10))
    seen = fake_yf(monkeypatch, lambda s, start: ohlcv(fresh_idx, start=float(original.iloc[-8]["Close"]), seed=9))
    ok, msg, info = ud.update_symbol("AAA", d, now=utc(2030, 1, 1, 0))
    assert ok, msg
    assert seen["AAA"] == [{"start": (last - pd.Timedelta(days=7)).isoformat()}]  # from 7 days before the LAST stored bar, not the full history
    assert "imported 300 bars from parquet" in msg and info["new"] > 0 and info["rejected"] == []
    assert real_db.price_bars_summary()["AAA"]["count"] == 300 + info["new"]
    assert pd.read_parquet(d / "AAA.parquet").index.max().date() == fresh_idx.max().date()  # the cache follows the database
    ok2, msg2, info2 = ud.update_symbol("AAA", d, now=utc(2030, 1, 1, 0))  # run again: nothing new
    assert ok2 and info2["new"] == 0 and "imported" not in msg2


def test_a_session_still_open_is_not_stored_by_the_updater(real_db, tmp_path, monkeypatch):
    d, original = seed_parquet(tmp_path, n=300)
    last = original.index[-1].date()
    day1 = (last + pd.offsets.BDay(1)).date()
    idx = pd.bdate_range(last - pd.Timedelta(days=7), day1)
    fake_yf(monkeypatch, lambda s, start: ohlcv(idx, seed=4))
    noon_et = datetime(day1.year, day1.month, day1.day, 16, 0, tzinfo=timezone.utc)  # ~12:00 ET: still trading
    ok, msg, info = ud.update_symbol("AAA", d, now=noon_et)
    assert ok and info["not_final"] == 1 and info["latest"] < day1.isoformat() and "provisional" in msg
    ok2, _m, info2 = ud.update_symbol("AAA", d, now=datetime(day1.year, day1.month, day1.day, 23, 0, tzinfo=timezone.utc))  # after the close
    assert info2["latest"] == day1.isoformat() and info2["new"] == 1


def test_the_updater_heals_a_hole_in_the_middle_of_the_history(real_db, tmp_path, monkeypatch):
    d = tmp_path / "data_parquet"
    d.mkdir()
    holed = pd.bdate_range("2025-01-02", "2025-12-29").append(pd.bdate_range("2026-08-20", "2026-09-17"))
    ps.recompute_indicators(ohlcv(holed)).to_parquet(d / "AAA.parquet")
    assert len(ud.find_gaps(holed)) == 1
    seen = fake_yf(monkeypatch, lambda s, start: ohlcv(pd.bdate_range(start, "2026-09-18"), start=130.0, seed=4))
    ok, msg, info = ud.update_symbol("AAA", d, now=utc(2026, 9, 19, 12))
    assert ok, msg
    assert seen["AAA"][0]["start"] == "2025-12-22"  # 7 days before the START of the hole, though the last bar was in September
    assert price_dates_gaps(real_db) == [] and real_db.price_bars_summary()["AAA"]["last"] == "2026-09-18"
    assert ud.find_gaps(pd.read_parquet(d / "AAA.parquet").index) == []


def price_dates_gaps(real_db):
    return ps.find_gaps_dates(ps.stored_dates("AAA"))


def test_an_empty_fetch_or_a_missing_file_changes_nothing(real_db, tmp_path, monkeypatch):
    d, original = seed_parquet(tmp_path, n=100)
    fake_yf(monkeypatch, lambda s, start: pd.DataFrame())
    ok, msg, _ = ud.update_symbol("AAA", d, now=utc(2030, 1, 1, 0))
    assert not ok and "no data" in msg and real_db.price_bars_summary()["AAA"]["count"] == 100
    ok2, msg2, _ = ud.update_symbol("ZZZ", d, now=utc(2030, 1, 1, 0))
    assert not ok2 and "not creating from scratch" in msg2


def test_a_bad_bar_is_reported_and_left_out_but_the_good_ones_are_kept(real_db, tmp_path, monkeypatch):
    d, original = seed_parquet(tmp_path, n=300)
    last = original.index[-1].date()
    idx = pd.bdate_range(last + pd.Timedelta(days=1), periods=3)
    fresh = ohlcv(idx, start=float(original.iloc[-1]["Close"]), seed=6)
    fresh.iloc[1, fresh.columns.get_loc("Close")] = fresh.iloc[0]["Close"] * 4  # +300%: an unadjusted split
    fake_yf(monkeypatch, lambda s, start: fresh)
    ok, msg, info = ud.update_symbol("AAA", d, now=utc(2030, 1, 1, 0))
    assert ok and len(info["rejected"]) == 1 and info["rejected"][0]["date"] == idx[1].date().isoformat() and "rejected" in msg


def test_run_updates_every_symbol_and_isolates_a_failure(real_db, tmp_path, monkeypatch):
    d = tmp_path / "data_parquet"
    d.mkdir()
    orig = {}
    for i, s in enumerate(("AAA", "BBB")):
        df = ps.recompute_indicators(ohlcv(pd.bdate_range("2025-01-02", periods=200), seed=i + 1))
        df.to_parquet(d / f"{s}.parquet")
        orig[s] = df
    monkeypatch.setattr(ud, "TRADING_STORAGE_PATH", tmp_path)

    def frames(sym, start):
        if sym == "BBB":
            raise RuntimeError("network down")
        return ohlcv(pd.bdate_range(start, pd.Timestamp(start) + pd.Timedelta(days=14)), seed=8)

    fake_yf(monkeypatch, frames)
    out = ud.run(now=utc(2030, 1, 1, 0), symbols=["AAA", "BBB"])
    assert out["ok"] == ["AAA"] and out["failed"] == ["BBB"] and out["new_bars"] > 0 and out["latest"]
    assert real_db.price_bars_summary()["BBB"]["count"] == 200  # BBB was still seeded from its file: nothing lost


def test_a_repeat_poll_writes_nothing_and_leaves_the_parquet_cache_untouched(real_db, tmp_path, monkeypatch):
    d, original = seed_parquet(tmp_path, n=300)
    last = original.index[-1].date()
    idx = pd.bdate_range(last - pd.Timedelta(days=7), last + pd.Timedelta(days=3))
    fresh = ohlcv(idx, start=float(original.iloc[-8]["Close"]), seed=9)
    fake_yf(monkeypatch, lambda s, start: fresh)
    now = utc(2030, 1, 1, 0)
    _ok, _m, first = ud.update_symbol("AAA", d, now=now)
    assert first["changed"] > 0
    stamp = (d / "AAA.parquet").stat().st_mtime_ns
    writes = []
    real = real_db.upsert_price_bars
    monkeypatch.setattr(real_db, "upsert_price_bars", lambda rows: writes.append(len(rows)) or real(rows))
    _ok, _m, second = ud.update_symbol("AAA", d, now=now)
    assert second["changed"] == 0 and second["new"] == 0 and writes == [0]
    assert (d / "AAA.parquet").stat().st_mtime_ns == stamp  # not rewritten: the app's caches key on this file's mtime


def test_delta_rows_keeps_new_and_corrected_bars_only(real_db, tmp_path):
    d, _ = seed_parquet(tmp_path, n=50)
    ps.import_parquet("AAA", d)
    stored = real_db.load_price_bars("AAA")
    same = dict(stored[-1])
    fixed = dict(stored[-2], close=stored[-2]["close"] * 1.01)
    new = dict(stored[-1], d="2099-01-01")
    assert ps.delta_rows("AAA", [same, fixed, new]) == [fixed, new]
    assert ps.delta_rows("AAA", []) == []
