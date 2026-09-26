"""S3 T2: the baseline discrepancy audit. The important test builds a context with the REAL production builder
(committee_daily.build_context) and checks that the audit's independent recomputation agrees with it, then tampers with it."""
from __future__ import annotations

import json

import pytest

from app import committee_daily, risk
from app.scripts import baseline_discrepancy as bd
from tests.test_paper_tax_committee import D, book_with

SYM, DAY = "AAPL", D[550]
LIVE = {"ma_cross": "BULLISH", "fast_ma": 30, "slow_ma": 200, "volume_ratio": 0.81, "test_sharpe": -1.02, "win_rate": 24}


@pytest.fixture(scope="module")
def book():
    prices = {SYM: {0: 100.0, 100: 112.0, 250: 95.0, 400: 130.0, 480: 121.0, 520: 140.0, 545: 133.0, 550: 137.5}}
    signals = {SYM: {i: "BUY" for i in range(5, 590)}}
    return book_with(prices, signals)


@pytest.fixture(scope="module")
def context(book):
    return committee_daily.build_context(SYM, DAY, book, LIVE, risk=risk.risk_at(book, SYM, DAY), ask=False, extra=["Macro backdrop: 10-year Treasury 4.96% (+0.46 pts over 3 months)."])


def run_for(context, **extra):
    return {"symbol": SYM, "date": DAY, "context": context, "ceo": {"consensus": 0.72, "headline": "HOLD - majority (72% of the vote weight); 2 dissent"}, "agents": [], **extra}


def checks(run, book, macro=None):
    return {c["check"]: c for c in bd.context_checks(run, book, risk.risk_at, lambda d: macro)}


# ------------------------------------------------------------------ number parsing --


def test_numbers_are_parsed_with_sign_percent_ordinal_commas_and_dates_removed():
    ns = bd.numbers("Sharpe -1.02, win rate 24%, at the 64th percentile; $1,234.50 on 2026-09-25 (was 4.4% in 2026-08); volume 0.81x")
    vals = [(n.value, n.pct) for n in ns]
    assert (-1.02, False) in vals and (24.0, True) in vals and (64.0, False) in vals and (1234.5, False) in vals and (4.4, True) in vals and (0.81, False) in vals
    assert not any(n.value in (2026.0, 9.0, 25.0) for n in ns)  # the dates are gone


def test_whole_numbers_up_to_ten_and_years_are_wording_not_claims():
    ns = {n.text: n for n in bd.numbers("7 analysts, 2 dissent, 2026, 47%, 227, 1.8, 10")}
    assert ns["7"].wording and ns["2"].wording and ns["2026"].wording and ns["10"].wording
    assert not ns["47%"].wording and not ns["227"].wording and not ns["1.8"].wording


@pytest.mark.parametrize(
    "claim,source,expected",
    [
        ("1.80", "1.8", True),  # formatting
        ("1.2%", "-1.2%", True),  # "1.2% below" vs "-1.2% from its high": the sign is wording
        ("$367", "367.38", True),  # rounded to a whole number
        ("4.96%", "4.96%", True),
        ("+7.8%", "7.8%", True),
        ("3.5%", "3.2%", False),  # a different figure
        ("48", "47", False),
        ("5,000", "5000", True),
    ],
)
def test_same_figure_rules(claim, source, expected):
    assert bd.same_figure(bd.numbers(claim)[0], bd.numbers(source)[0]) is expected


def test_unsupported_finds_invented_or_derived_numbers_and_ignores_restated_ones():
    ctx = "Last price 227.38. 5-day +7.8%; -1.2% from its 60-day high; beta 1.8; volatility at the 64th percentile."
    prose = "A 5-day gain of 7.8%, just 1.2% below its high, beta 1.80, 64th percentile, with a 15% upside to $262 and a 3.1% dividend yield."
    assert [n.text for n in bd.unsupported(prose, ctx)] == ["15%", "$262", "3.1%"]


# --------------------------------------------------- part A against the real builder --


def test_the_independent_recomputation_agrees_with_the_production_context_builder(book, context):
    got = checks(run_for(context), book, macro="Macro backdrop: 10-year Treasury 4.96% (+0.46 pts over 3 months).")
    assert {"last price", "1-day move %", "5-day move %", "20-day move %", "distance from 60-day high %", "20-day volatility %", "RSI",
            "engine signal", "risk score", "risk level", "macro line (verbatim)"} <= set(got)
    bad = {k: v for k, v in got.items() if v["status"] == "mismatch"}
    assert bad == {}, f"the audit disagrees with the production builder: {bad}"
    assert sum(v["status"] == "verified" for v in got.values()) >= 12
    assert got["Sharpe (not independently checked)"]["status"] == "not_checked"  # honest: not counted as passed
    assert got["win rate (not independently checked)"]["status"] == "not_checked"


def test_tampered_numbers_are_reported_as_mismatches(book, context):
    for old, new, check in [
        ("Last price 137.50", "Last price 139.99", "last price"),
        ("5-day", "5-day +99.0%; 5-day", "5-day move %"),
        ("Quant engine signal: BUY", "Quant engine signal: SELL", "engine signal"),
    ]:
        assert old in context, old
        tampered = context.replace(old, new, 1)
        assert checks(run_for(tampered), book)[check]["status"] == "mismatch", check


def test_a_drifted_macro_line_is_a_mismatch_and_a_missing_figure_is_not_found(book, context):
    got = checks(run_for(context), book, macro="Macro backdrop: 10-year Treasury 9.99%")
    assert got["macro line (verbatim)"]["status"] == "mismatch"
    empty = checks(run_for("AAPL — Apple\nno figures here"), book)
    assert empty["last price"]["status"] == "not_found"


def test_a_run_dated_outside_the_price_data_is_flagged(book, context):
    r = run_for(context)
    r["date"] = "1999-01-04"
    assert bd.context_checks(r, book, risk.risk_at, lambda d: None)[0]["status"] == "mismatch"


# -------------------------------------------------------------- part B and the audit --


def test_headline_vote_weight_must_equal_the_stored_consensus():
    assert bd.headline_check({"ceo": {"consensus": 0.72, "headline": "HOLD - majority (72% of the vote weight)"}})["status"] == "verified"
    assert bd.headline_check({"ceo": {"consensus": 0.72, "headline": "HOLD - majority (81% of the vote weight)"}})["status"] == "mismatch"
    assert bd.headline_check({"ceo": {"consensus": None, "headline": "x"}}) is None


def analyst(name, summary, **kw):
    return {"agent": name, "type": "llm", "ok": True, "model": "m1", "summary": summary, **kw}


def test_audit_counts_supported_and_unsupported_prose_numbers_and_skips_deterministic_and_failed_agents(book, context):
    run = run_for(
        context,
        agents=[
            analyst("Quant", "A 5-day move and RSI are in line; the price is 137.50 with 20-day volatility supporting a 12% upside."),
            analyst("Risk", "Risk score is fine.", ok=False),  # failed: not audited
            {"agent": "Engine", "type": "deterministic", "ok": True, "summary": "engine BUY (99%)"},  # deterministic: not audited
            analyst("Macro", "Yields at 4.96% are up 0.46 points; inflation of 8.7% is a worry."),
        ],
    )
    out = bd.audit([run], book, risk.risk_at, lambda d: None)
    c = [r for r in out["rows"] if r["part"] == "C"]
    unsup = sorted(r["detail"] for r in c if r["status"] == "unsupported")
    assert unsup == ["12%", "8.7%"] and any(r["status"] == "supported" and r["detail"] == "4.96%" for r in c)
    assert {r["source"].split("|")[0] for r in c} == {"analyst:Quant", "analyst:Macro"}
    s = out["summary"]
    assert s["C_llm_prose"]["bad"] == 2 and s["C_llm_prose"]["analyst_rows"] == 2 and s["A_context"]["bad"] == 0
    assert s["C_by_agent"]["Quant"]["unsupported"] == 1 and s["C_by_model"]["m1"]["numbers"] == s["C_llm_prose"]["checked"]


def test_summary_of_no_runs_is_valid_and_renders(book):
    out = bd.audit([], book, risk.risk_at, lambda d: None)
    assert out["summary"]["runs"] == 0 and out["summary"]["C_llm_prose"]["rate"] is None
    assert "No committee runs" in bd.render_markdown(out["summary"])


def test_markdown_states_the_headline_numbers_and_the_limits(book, context, tmp_path):
    run = run_for(context, agents=[analyst("Quant", "Price 137.50 and a 12% upside.")])
    summary = bd.audit([run], book, risk.risk_at, lambda d: None)["summary"]
    md = bd.render_markdown(summary)
    assert "50.0% unsupported" in md and "(1 of 2 numbers" in md and "not independently checked" in md.lower() and "no new model calls" in md.lower()
    path = tmp_path / "s.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    out = tmp_path / "b.md"
    assert bd.main(["--from-json", str(path), "--markdown", str(out)]) == 0 and "S3 baseline" in out.read_text(encoding="utf-8")  # renders with no database


# ---------------------------------------------- older context format, materiality, by day --


def test_a_context_from_the_older_format_reports_not_found_not_mismatch(book):
    """The committee's first day (2026-09-18) used a shorter context with no signal, risk or macro lines."""
    old = f"{SYM} — Apple (Technology)\nData through the close of {DAY}. Last price 137.50.\nRecent moves: 1-day +1.0%."
    got = checks(run_for(old), book, macro="Macro backdrop: 10-year Treasury 4.96%")
    for name in ("engine signal", "risk level", "macro line (verbatim)"):
        assert got[name]["status"] == "not_found", name
    assert not [c for c in got.values() if c["status"] == "mismatch" and c["check"] not in ("1-day move %",)]


def test_a_small_gap_is_rounding_level_and_a_large_one_is_material(book, context):
    rows = []
    for old, new in [("Last price 137.50", "Last price 137.51"), ("Last price 137.50", "Last price 140.00")]:
        run = run_for(context.replace(old, new, 1), agents=[])
        rows += [{**c, "date": DAY, "symbol": SYM, "part": "A", "detail": c["check"], "source": "context"} for c in bd.context_checks(run, book, risk.risk_at, lambda d: None)]
    s = bd.summarise(rows, [run_for(context)])
    mism = sorted((m for m in s["mismatches"] if m["check"] == "last price"), key=lambda m: m["gap"])
    assert [m["material"] for m in mism] == [False, True] and mism[0]["gap"] == pytest.approx(0.01) and mism[1]["gap"] == pytest.approx(2.5)
    assert s["A_context"]["bad"] == 2 and s["A_context"]["bad_material"] == 1 and s["A_context"]["bad_rounding_level"] == 1


def test_results_are_broken_out_by_day_so_one_bad_day_cannot_hide(book, context):
    early = run_for(context, date=D[549], agents=[analyst("Quant", "A 777.7% gain and a 555.5% jump.")])
    late = run_for(context, agents=[analyst("Quant", "Price 137.50 and RSI in line.")])
    s = bd.audit([early, late], book, risk.risk_at, lambda d: None)["summary"]
    assert s["C_by_date"][D[549]]["rate"] == 1.0 and s["C_by_date"][DAY]["unsupported"] == 0
    md = bd.render_markdown(s)
    assert "By day" in md and D[549] in md and DAY in md and "more than rounding" in md
