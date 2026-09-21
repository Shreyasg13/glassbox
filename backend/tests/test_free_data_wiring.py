"""Free data reaches the committee prompt, the user's stance and the admin panel, from the cache only."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import committee_daily, free_data as fd, strategy
from app.main import app
from tests.test_committee_daily import LAST, NOW, agents_result, make_book as committee_book
from tests.test_free_data import ACME, facts_for, flow, row
from tests.test_paper_cycle import fake  # noqa: F401  (fixture the api fixture depends on)
from tests.test_strategy import ADMIN, VIEWER, api  # noqa: F401  (api is a fixture)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FREE_DATA_DIR", str(tmp_path / "free_data"))
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    return tmp_path / "free_data"


def seed_cache(symbol="AAPL", filed="2024-04-10", items=("5.02",)):
    fd._write(f"fundamentals/{symbol}.json", {"cik": 1, "fetched_at": "2026-01-01T00:00:00+00:00", "concepts": fd.extract_concepts(ACME)})
    fd._write(f"filings/{symbol}.json", {"cik": 1, "fetched_at": "2026-01-01T00:00:00+00:00", "filings": [{"form": "8-K", "filed": filed, "items": list(items)}]})


EARLY = facts_for(  # FY2023 filed 2024-02-01: known by the April 2024 test market
    rev=flow("Revenues", [row("2022-12-31", 100.0, "2023-02-01", "2022-01-01"), row("2023-12-31", 110.0, "2024-02-01", "2023-01-01")]),
    ni=flow("NetIncomeLoss", [row("2023-12-31", 16.5, "2024-02-01", "2023-01-01")]),
    oi=flow("OperatingIncomeLoss", [row("2023-12-31", 22.0, "2024-02-01", "2023-01-01")]),
    eps=flow("EarningsPerShareDiluted", [row("2023-12-31", 2.0, "2024-02-01", "2023-01-01")], unit="USD/shares"),
    eq=flow("StockholdersEquity", [row("2023-12-31", 60.0, "2024-02-01")]),
)


def seed_early(symbol):
    fd._write(f"fundamentals/{symbol}.json", {"cik": 1, "fetched_at": "2026-01-01T00:00:00+00:00", "concepts": fd.extract_concepts(EARLY)})


def test_the_context_carries_the_extra_public_data_lines_after_the_technical_facts():
    book = committee_book()
    ctx = committee_daily.build_context("AAPL", LAST, book, None, ask=False, extra=["Fundamentals (fiscal year to 2025-12-31): revenue +25.0% year on year.", "Macro backdrop: 10-year Treasury 4.25%."])
    assert "Fundamentals (fiscal year to 2025-12-31)" in ctx and "Macro backdrop" in ctx
    assert ctx.index("Recent moves") < ctx.index("Fundamentals")  # the numbers first, then the public context
    assert "Fundamentals" not in committee_daily.build_context("AAPL", LAST, book, None, ask=False)


async def test_a_review_reads_the_cache_for_that_symbol_and_date_never_the_network(monkeypatch):
    """ACME's filings are dated 2025-2026 but the test market is early 2024: NOTHING may leak in from the future."""
    seed_cache("AAPL", filed="2024-04-10")
    seen = {}

    async def runner(orch, ctx, **kw):
        seen[ctx.split(" ")[0]] = ctx
        return agents_result()

    from tests.test_committee_daily import FakeDB
    import pytest as _pt

    mp = _pt.MonkeyPatch()
    FakeDB().install(mp)
    mp.setattr(committee_daily.ds, "get_live_signals", lambda: {"signals": []})
    try:
        await committee_daily.run_daily(symbols=["AAPL"], book=committee_book(), now=NOW, runner=runner, live_rows={})
    finally:
        mp.undo()
    ctx = seen["AAPL"]
    assert "Recent SEC filings" in ctx and "changed directors or senior officers" in ctx  # the 8-K filed 2024-04-10 is inside the window
    assert "Fundamentals" not in ctx  # FY2025 filings (2026) had not been filed by 2024-04-22: no lookahead


def test_stance_raises_a_flagged_recent_filing_as_a_reason_and_shows_macro_and_fundamentals(monkeypatch):
    book = committee_book()
    monkeypatch.setattr(strategy.db, "list_all_committee_runs", lambda: [])
    seed_cache("JPM", filed="2024-04-10", items=("5.02",))
    seed_early("JPM")
    fd._write("macro.json", {"fetched_at": "2026-01-01T00:00:00+00:00", "treasury": [{"date": "2024-04-19", "y3m": 5.3, "y2": 4.9, "y10": 4.6}], "bls": {}})
    out = strategy.stance(book)
    jpm = next(r for r in out["rows"] if r["symbol"] == "JPM")
    assert jpm["attention"] and "SEC filing worth a look (2024-04-10): changed directors or senior officers" in jpm["summary"]
    assert jpm["fundamentals"]["net_margin"] == pytest.approx(0.15) and jpm["fundamentals"]["revenue_growth"] == pytest.approx(0.10) and jpm["fundamentals"]["pe"] is not None
    assert out["macro_line"].startswith("Macro backdrop: 10-year Treasury 4.60%")
    amzn = next(r for r in out["rows"] if r["symbol"] == "AMZN")
    assert not amzn["attention"] and amzn["fundamentals"] is None  # no filings cached for it


def test_an_unflagged_filing_alone_does_not_shout(monkeypatch):
    monkeypatch.setattr(strategy.db, "list_all_committee_runs", lambda: [])
    seed_cache("JPM", filed="2024-04-10", items=("2.02",))  # routine results
    jpm = next(r for r in strategy.stance(committee_book())["rows"] if r["symbol"] == "JPM")
    assert not jpm["attention"]


def test_the_data_sources_endpoint_is_admin_only_and_reports_status_and_rows(api):
    assert api.get("/api/admin/strategy/data-sources").status_code == 401
    assert api.get("/api/admin/strategy/data-sources", headers=VIEWER).status_code == 403
    fd._write("status.json", {"treasury": {"ok": True, "detail": "through 2026-09-16", "count": 300, "at": "2026-09-17T00:00:00+00:00"}})
    body = api.get("/api/admin/strategy/data-sources", headers=ADMIN).json()
    assert body["status"]["treasury"]["ok"] and body["sec_configured"] is False and len(body["rows"]) == 3 and body["as_of"]
