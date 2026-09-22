"""Free public data: SEC fundamentals + filings, Treasury and BLS macro. Point-in-time, polite, and never fatal."""
from __future__ import annotations

import json

import httpx
import pytest

from app import free_data as fd


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    return tmp_path / "free_data"


def row(end, val, filed, start=None, form="10-K", fp="FY"):
    r = {"end": end, "val": val, "filed": filed, "form": form, "fp": fp}
    if start:
        r["start"] = start
    return r


def flow(tag, rows, unit="USD"):
    return {tag: {"units": {unit: rows}}}


def facts_for(**tags):
    gaap = {}
    for tag_rows in tags.values():
        gaap.update(tag_rows)
    return {"cik": 1, "entityName": "Acme", "facts": {"us-gaap": gaap}}


# FY2024 (filed 2025-02-01) and FY2025 (filed 2026-02-01); FY2024 revenue was later RESTATED in the FY2025 10-K
ACME = facts_for(
    rev=flow("Revenues", [
        row("2024-12-31", 100.0, "2025-02-01", "2024-01-01"),
        row("2025-12-31", 120.0, "2026-02-01", "2025-01-01"),
        row("2024-12-31", 96.0, "2026-02-01", "2024-01-01"),  # restated down, filed later
        row("2025-03-31", 30.0, "2025-05-01", "2025-01-01", form="10-Q", fp="Q1"),  # a quarter: must be ignored
        row("2025-06-30", 60.0, "2025-08-01", "2025-01-01", form="10-K", fp="FY"),  # a 6-month "annual": wrong duration
    ]),
    ni=flow("NetIncomeLoss", [row("2024-12-31", 10.0, "2025-02-01", "2024-01-01"), row("2025-12-31", 18.0, "2026-02-01", "2025-01-01")]),
    oi=flow("OperatingIncomeLoss", [row("2025-12-31", 24.0, "2026-02-01", "2025-01-01")]),
    eps=flow("EarningsPerShareDiluted", [row("2025-12-31", 2.0, "2026-02-01", "2025-01-01")], unit="USD/shares"),
    ocf=flow("NetCashProvidedByUsedInOperatingActivities", [row("2025-12-31", 30.0, "2026-02-01", "2025-01-01")]),
    capex=flow("PaymentsToAcquirePropertyPlantAndEquipment", [row("2025-12-31", 6.0, "2026-02-01", "2025-01-01")]),
    eq=flow("StockholdersEquity", [row("2024-12-31", 80.0, "2025-02-01"), row("2025-12-31", 90.0, "2026-02-01")]),
    lia=flow("Liabilities", [row("2025-12-31", 180.0, "2026-02-01")]),
    ltd=flow("LongTermDebtNoncurrent", [row("2025-12-31", 45.0, "2026-02-01")]),
)


# --------------------------------------------------------------- extraction --


def test_extraction_keeps_only_full_fiscal_years_from_annual_filings_with_every_filed_version():
    c = fd.extract_concepts(ACME)
    rev = c["revenue"]
    assert rev["tag"] == "Revenues"
    ends = [(r["end"], r["val"], r["filed"]) for r in rev["series"]]
    assert ("2025-03-31", 30.0, "2025-05-01") not in ends and all(e != "2025-06-30" for e, _v, _f in ends)  # 10-Q and 6-month rows dropped
    assert ("2024-12-31", 100.0, "2025-02-01") in ends and ("2024-12-31", 96.0, "2026-02-01") in ends  # the restatement is a separate, later version
    assert c["eps"]["unit"] == "USD/shares" and "equity" in c and "long_term_debt" in c


def test_when_two_tags_exist_the_one_with_the_more_recent_year_wins():
    f = facts_for(a=flow("SalesRevenueNet", [row("2019-12-31", 5.0, "2020-02-01", "2019-01-01")]), b=flow("Revenues", [row("2025-12-31", 9.0, "2026-02-01", "2025-01-01")]))
    assert fd.extract_concepts(f)["revenue"]["tag"] == "Revenues"


# ------------------------------------------------------------- point in time --


def test_fundamentals_are_computed_from_what_had_been_filed_by_the_date_and_nothing_later():
    c = fd.extract_concepts(ACME)
    now = fd.fundamentals_from_concepts(c, "2026-06-01", price=40.0)
    assert now["fiscal_year_end"] == "2025-12-31" and now["filed"] == "2026-02-01" and now["age_days"] == 120
    assert now["revenue_growth"] == pytest.approx(120 / 96 - 1)  # uses the RESTATED prior year, which had been filed by then
    assert now["net_margin"] == pytest.approx(18 / 120) and now["operating_margin"] == pytest.approx(24 / 120)
    assert now["roe"] == pytest.approx(18 / 90) and now["debt_to_equity"] == pytest.approx(45 / 90)
    assert now["fcf_margin"] == pytest.approx((30 - 6) / 120) and now["eps"] == 2.0 and now["pe"] == pytest.approx(20.0)
    before_restatement = fd.fundamentals_from_concepts(c, "2025-12-15", price=40.0)
    assert before_restatement["fiscal_year_end"] == "2024-12-31" and "revenue_growth" not in before_restatement  # FY2025 does not exist yet
    assert before_restatement["net_margin"] == pytest.approx(10 / 100)  # and the ORIGINAL 100, not the later 96
    assert fd.fundamentals_from_concepts(c, "2024-06-01") is None  # nothing filed yet


def test_a_filer_without_standard_tags_yields_only_what_it_reports_or_nothing():
    only_liabilities = facts_for(l=flow("Liabilities", [row("2025-12-31", 10.0, "2026-02-01")]))
    assert fd.fundamentals_from_concepts(fd.extract_concepts(only_liabilities), "2026-06-01") is None  # too little to say anything
    assert fd.extract_concepts(facts_for()) == {}
    c2 = fd.extract_concepts(facts_for(rev=flow("Revenues", [row("2024-12-31", 100.0, "2025-02-01", "2024-01-01"), row("2025-12-31", 110.0, "2026-02-01", "2025-01-01")]),
                                       ni=flow("NetIncomeLoss", [row("2025-12-31", 11.0, "2026-02-01", "2025-01-01")]),
                                       eq=flow("StockholdersEquity", [row("2025-12-31", 50.0, "2026-02-01")]),
                                       lia=flow("Liabilities", [row("2025-12-31", 200.0, "2026-02-01")])))
    f = fd.fundamentals_from_concepts(c2, "2026-06-01")
    assert "debt_to_equity" not in f and f["liabilities_to_equity"] == pytest.approx(4.0) and "pe" not in f and "operating_margin" not in f


def test_the_fundamentals_line_reads_naturally_and_omits_what_is_missing():
    line = fd.fundamentals_line(fd.fundamentals_from_concepts(fd.extract_concepts(ACME), "2026-06-01", 40.0))
    assert line.startswith("Fundamentals (fiscal year to 2025-12-31, filed 2026-02-01): revenue +25.0% year on year")
    assert "net margin 15.0%" in line and "P/E 20.0 on last fiscal year's earnings" in line and "long-term debt 0.50x equity" in line
    assert fd.fundamentals_line(None) is None


# --------------------------------------------------------------------- events --


FILINGS = [
    {"form": "8-K", "filed": "2026-09-10", "items": ["2.02", "9.01"]},
    {"form": "8-K", "filed": "2026-09-05", "items": ["5.02"]},
    {"form": "8-K", "filed": "2026-09-01", "items": ["9.01"]},  # exhibits only: not news
    {"form": "10-Q", "filed": "2026-08-25", "items": []},
    {"form": "4", "filed": "2026-09-08", "items": []},  # insider form: not parsed
    {"form": "8-K", "filed": "2026-06-01", "items": ["1.01"]},  # too old
    {"form": "8-K", "filed": "2026-09-19", "items": ["8.01"]},  # after the as-of date
]


def test_events_are_windowed_plain_english_flagged_and_never_from_the_future():
    ev = fd.events_from_filings(FILINGS, "2026-09-15", 30)
    assert [e["filed"] for e in ev] == ["2026-09-10", "2026-09-05", "2026-08-25"]
    assert ev[0]["text"] == "reported quarterly results" and ev[0]["flag"] is False
    assert ev[1]["text"] == "changed directors or senior officers" and ev[1]["flag"] is True
    line = fd.events_line(ev)
    assert line.startswith("Recent SEC filings (last 30 days): 8-K 2026-09-10 (reported quarterly results)") and "[worth a look]" in line
    assert fd.events_line([]) is None


def test_filings_are_extracted_from_the_submissions_shape():
    sub = {"filings": {"recent": {"form": ["8-K", "10-Q"], "filingDate": ["2026-09-10", "2026-08-01"], "items": ["2.02,9.01", ""]}}}
    assert fd.extract_filings(sub) == [{"form": "8-K", "filed": "2026-09-10", "items": ["2.02", "9.01"]}, {"form": "10-Q", "filed": "2026-08-01", "items": []}]
    assert fd.extract_filings({}) == []


# ---------------------------------------------------------------------- macro --


TREASURY_CSV = "Date,1 Mo,3 Mo,2 Yr,10 Yr,30 Yr\n06/02/2026,4.3,4.2,3.9,4.0,4.6\n09/15/2026,4.1,4.0,3.7,4.2,4.7\n09/16/2026,4.1,4.0,3.7,4.25,4.7\nbad,row\n"


def test_treasury_csv_parses_and_ignores_junk_rows():
    rows = fd.parse_treasury_csv(TREASURY_CSV)
    assert [r["date"] for r in rows] == ["2026-06-02", "2026-09-15", "2026-09-16"] and rows[-1] == {"date": "2026-09-16", "y3m": 4.0, "y2": 3.7, "y10": 4.25}


def bls(rows):
    return {"Results": {"series": [{"data": [{"year": y, "period": f"M{m:02d}", "value": v} for y, m, v in rows] + [{"year": "2026", "period": "M13", "value": "9"}]}]}}


def test_bls_parses_monthly_rows_only():
    assert fd.parse_bls(bls([(2026, 7, "4.3"), (2026, 6, "4.2")])) == [{"month": "2026-06", "value": 4.2}, {"month": "2026-07", "value": 4.3}]
    assert fd.parse_bls({}) == [] and fd.parse_bls(bls([(2026, 7, "-")])) == []


def macro_cache():
    cpi = [(2025, m, str(300 + m * 0.5)) for m in range(1, 13)] + [(2026, m, str(310 + m * 0.5)) for m in range(1, 9)]
    unemp = [(2026, m, str(4.0 + m * 0.05)) for m in range(1, 9)]
    return {"treasury": fd.parse_treasury_csv(TREASURY_CSV), "bls": {"unemployment": fd.parse_bls(bls(unemp)), "cpi": fd.parse_bls(bls(cpi))}}


def test_macro_uses_only_what_had_been_published_and_computes_changes():
    m = fd.macro_from_cache(macro_cache(), "2026-09-16")
    assert m["treasury_date"] == "2026-09-16" and m["y10"] == 4.25 and m["curve_10y_2y"] == pytest.approx(0.55)
    assert m["y10_change_3m"] == pytest.approx(4.25 - 4.0)  # against the 2026-06-02 row, more than 90 days back
    assert m["unemployment_month"] == "2026-08" and m["unemployment_6m_ago"] == pytest.approx(4.0 + 2 * 0.05)  # August's jobs report is out by mid-September
    assert m["cpi_month"] == "2026-07" and m["cpi_yoy"] == pytest.approx((310 + 7 * 0.5) / (300 + 7 * 0.5) - 1)  # but August CPI (20-day lag) is not yet
    early = fd.macro_from_cache(macro_cache(), "2026-07-05")  # June's jobs figure (ends 06-30, +12 days) is not public yet
    assert early["unemployment_month"] == "2026-05" and "y10" in early
    assert fd.macro_from_cache(macro_cache(), "2026-07-14")["unemployment_month"] == "2026-06"  # now it is
    assert fd.macro_from_cache(macro_cache(), "2026-01-01") is None or "y10" not in fd.macro_from_cache(macro_cache(), "2026-01-01")
    assert fd.macro_from_cache(None, "2026-09-16") is None


def test_macro_line_reads_naturally_and_flags_an_inverted_curve():
    line = fd.macro_line(fd.macro_from_cache(macro_cache(), "2026-09-16"))
    assert line.startswith("Macro backdrop: 10-year Treasury 4.25% (+0.25 pts over 3 months); yield curve (10y minus 2y) +0.55 pts (normal)")
    assert "unemployment 4.4% (2026-08" in line and "consumer prices +" in line
    inv = fd.macro_line({"y10": 3.9, "curve_10y_2y": -0.2})
    assert "(inverted)" in inv and fd.macro_line(None) is None and fd.macro_line({}) is None


# ------------------------------------------------------------------- fetching --


def client(handler, **kw):
    sleeps = []
    f = fd.Fetcher(transport=httpx.MockTransport(handler), sleep=sleeps.append, **kw)
    f.sleeps = sleeps
    return f


def test_the_fetcher_retries_transient_errors_then_succeeds_and_gives_up_after_three():
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"ok": True})

    f = client(flaky)
    assert f.json("https://x.test/a") == {"ok": True} and calls["n"] == 3 and f.sleeps  # backed off between tries
    with pytest.raises(httpx.HTTPStatusError):
        client(lambda r: httpx.Response(429)).get("https://x.test/b")
    with pytest.raises(httpx.HTTPStatusError):
        client(lambda r: httpx.Response(404)).get("https://x.test/c")  # a real 404 is not retried


def test_the_fetcher_spaces_requests_out_to_stay_under_the_sec_limit():
    f = client(lambda r: httpx.Response(200, json={}), min_interval=5.0)
    for _ in range(3):
        f.get("https://x.test/z")
    assert len([s for s in f.sleeps if s > 0]) >= 2  # the 2nd and 3rd calls had to wait


# -------------------------------------------------------------------- refresh --


def fake_sec(fail_for=(), no_facts_for=()):
    seen = {"ua": set(), "urls": []}

    def handler(request):
        seen["urls"].append(str(request.url))
        seen["ua"].add(request.headers.get("user-agent"))
        u = str(request.url)
        if u.endswith("company_tickers.json"):
            return httpx.Response(
                200,
                json={
                    "0": {"cik_str": 1, "ticker": "AAA", "title": "Acme"},
                    "1": {"cik_str": 2, "ticker": "BBB", "title": "Beta"},
                    "2": {"cik_str": 3, "ticker": "TRUST", "title": "A Trust"},
                },
            )
        if "companyfacts" in u:
            cik = int(u.split("CIK")[1][:10])
            if cik in no_facts_for:
                return httpx.Response(404)  # a real CIK with no XBRL facts (fund/trust)
            if cik in fail_for:
                return httpx.Response(500)
            return httpx.Response(200, json=ACME)
        if "submissions" in u:
            return httpx.Response(200, json={"filings": {"recent": {"form": ["8-K"], "filingDate": ["2026-09-10"], "items": ["2.02"]}}})
        return httpx.Response(404)

    c = fd.Fetcher({"User-Agent": "GlassBox test ops@example.com"}, transport=httpx.MockTransport(handler), sleep=lambda s: None)
    return c, seen


def test_sec_refresh_writes_a_cache_that_the_readers_then_serve(cache_dir):
    c, seen = fake_sec()
    status = fd.refresh_sec(["AAA", "BBB", "SPY"], sec=c)
    assert status["sec"]["ok"] and status["sec"]["count"] == 2 and "SPY" in status["sec"]["detail"]  # a fund has no filings: skipped, not failed
    assert seen["ua"] == {"GlassBox test ops@example.com"}
    f = fd.fundamentals_as_of("AAA", "2026-06-01", 40.0)
    assert f["pe"] == pytest.approx(20.0) and fd.events_as_of("AAA", "2026-09-15")[0]["text"] == "reported quarterly results"
    assert fd.fundamentals_as_of("SPY", "2026-06-01") is None and fd.events_as_of("SPY", "2026-09-15") == []
    lines = fd.context_lines("AAA", "2026-09-15", 40.0)
    assert lines[0].startswith("Fundamentals") and lines[1].startswith("Recent SEC filings")


def test_the_ticker_map_and_fresh_fundamentals_are_not_refetched(cache_dir):
    c, seen = fake_sec()
    fd.refresh_sec(["AAA"], sec=c)
    first = len(seen["urls"])
    c2, seen2 = fake_sec()
    fd.refresh_sec(["AAA"], sec=c2)
    assert not any("company_tickers" in u for u in seen2["urls"]) and not any("companyfacts" in u for u in seen2["urls"])  # cached
    assert any("submissions" in u for u in seen2["urls"]) and first > len(seen2["urls"])  # filings still refresh daily
    c3, seen3 = fake_sec()
    fd.refresh_sec(["AAA"], sec=c3, force=True)
    assert any("companyfacts" in u for u in seen3["urls"])


def test_one_company_failing_does_not_stop_the_others_and_is_reported(cache_dir):
    c, _ = fake_sec(fail_for=(2,))
    st = fd.refresh_sec(["AAA", "BBB"], sec=c)["sec"]
    assert st["ok"] is False and "FAILED BBB" in st["detail"] and st["count"] == 1
    assert fd.fundamentals_as_of("AAA", "2026-06-01") is not None and fd.fundamentals_as_of("BBB", "2026-06-01") is None


def test_a_real_filer_with_no_xbrl_facts_still_gets_its_filings_not_marked_failed(cache_dir):
    """A trust like SPY has a real CIK and files 8-Ks, but companyfacts 404s (no XBRL financials) --
    that must not be treated the same as a real failure, and its filings must still be cached."""
    c, _ = fake_sec(no_facts_for=(3,))
    status = fd.refresh_sec(["AAA", "TRUST"], sec=c)["sec"]
    assert status["ok"] and status["count"] == 2 and "no XBRL facts for TRUST" in status["detail"] and "FAILED" not in status["detail"]
    assert fd.fundamentals_as_of("TRUST", "2026-06-01") is None  # no financial concepts
    assert fd.events_as_of("TRUST", "2026-09-15")[0]["text"] == "reported quarterly results"  # but filings are cached


def test_the_sec_part_stays_off_without_a_declared_contact_and_says_why(cache_dir, monkeypatch):
    st = fd.refresh_sec(["AAA"])["sec"]
    assert st["ok"] is False and "SEC_USER_AGENT" in st["detail"]
    monkeypatch.setenv("SEC_USER_AGENT", "GlassBox without an email")  # the SEC wants a contact: refuse to guess one
    assert fd.sec_user_agent() is None and fd.refresh_sec(["AAA"])["sec"]["ok"] is False
    monkeypatch.setenv("SEC_USER_AGENT", "GlassBox research ops@example.com")
    assert fd.sec_user_agent() == "GlassBox research ops@example.com"


def test_macro_refresh_isolates_each_source_and_records_status(cache_dir):
    def handler(request):
        u = str(request.url)
        if "treasury.gov" in u:
            return httpx.Response(200, text=TREASURY_CSV)
        if "LNS14000000" in u:
            return httpx.Response(200, json=bls([(2026, 7, "4.3"), (2026, 6, "4.2")]))
        return httpx.Response(500)  # CPI is down

    st = fd.refresh_macro(client(handler), today=__import__("datetime").date(2026, 9, 16))
    assert st["treasury"]["ok"] and st["bls_unemployment"]["ok"] and st["bls_cpi"]["ok"] is False
    m = fd.macro_as_of("2026-09-16")
    assert m["y10"] == 4.25 and "unemployment" in m and "cpi_yoy" not in m  # the working sources still serve


def test_everything_degrades_to_nothing_when_no_cache_exists(cache_dir):
    assert fd.context_lines("AAA", "2026-09-15", 40.0) == [] and fd.fundamentals_as_of("AAA", "2026-09-15") is None
    snap = fd.snapshot(["AAA"], "2026-09-15", {"AAA": 40.0})
    assert snap["rows"] == [{"symbol": "AAA", "fundamentals": None, "events": []}] and snap["macro"] is None and snap["sec_configured"] is False
