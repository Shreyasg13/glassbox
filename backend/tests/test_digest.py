"""The daily admin digest: content curation (pure), HTML rendering (pure), and the never-fatal
send path. No real SMTP, no real DB -- see app/digest.py's own docstring for the design rules
this is checking."""
from __future__ import annotations

import pytest

from app import digest


def overview(**over):
    base = {
        "data_date": "2026-09-22",
        "latest_review_date": "2026-09-22",
        "pipeline": {
            "status": "ok",
            "message": "",
            "stages": {"free_data": {"ok": True}, "committee": {"ok": True}, "paper_cycle": {"ok": True}},
            "sync": {"coverage": 1.0},
        },
        "data_quality": {"ok": True, "gaps": []},
        "capital": [
            {"id": "ctl_engine", "name": "Signal engine", "total_return": 0.135, "live_return": 0.02, "sharpe": 1.1, "max_drawdown": -0.08, "live_days": 3},
        ],
    }
    base.update(over)
    return base


def run_row(symbol="AAPL", decision="BUY", gate=None, engine="BUY"):
    return {"date": "2026-09-22", "symbol": symbol, "decision": decision, "action": decision if not gate else "HOLD", "engine_signal": engine, "gate": gate, "ceo": {"label": "strong consensus"}, "answered": 10, "total": 10}


FREE_STATUS = {"treasury": {"ok": True, "detail": "through 2026-09-22"}, "sec": {"ok": False, "detail": "not configured: set SEC_USER_AGENT"}}
BOARD_INSUFFICIENT = {"agents": [{"agent": "Analyst0", "ranked": False}], "note": "An agent is ranked only after 30 scored BUY/SELL calls."}


# ------------------------------------------------------------------ build_digest --


def test_build_digest_curates_the_overview_without_recomputing_anything():
    d = digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, [run_row(), run_row("NVDA", "SELL", engine="SELL")])
    assert d["date"] == "2026-09-22" and d["pipeline"]["status"] == "ok" and d["pipeline"]["sync_coverage"] == 1.0
    assert d["pipeline"]["stages"] == {"free_data": True, "committee": True, "paper_cycle": True}
    assert [x["symbol"] for x in d["decisions"]] == ["AAPL", "NVDA"]  # sorted
    assert d["capital"][0]["name"] == "Signal engine" and d["capital"][0]["total_return"] == 0.135
    assert d["ranked_agents"] == [] and "30 scored" in d["leaderboard_note"]
    assert d["free_data"]["sec"]["ok"] is False


def test_a_risk_gated_buy_is_flagged_in_the_curated_decisions():
    d = digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, [run_row("TSLA", "BUY", gate="risk regime is HIGH")])
    assert d["decisions"][0]["gated"] is True and d["decisions"][0]["action"] == "HOLD"


def test_missing_data_quality_and_pipeline_never_crash_the_curation():
    d = digest.build_digest({"data_date": None}, {}, {"agents": []}, [])
    assert d["data_quality"] == {"ok": True, "gaps": []} and d["pipeline"]["stages"] == {} and d["decisions"] == []


# ------------------------------------------------------------------------ HTML --


def test_render_html_is_self_contained_and_covers_every_section():
    d = digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, [run_row()])
    html = digest.render_html(d)
    assert html.startswith("<!doctype html>") and "<style" not in html  # inline styles only: safest across mail clients
    assert "2026-09-22" in html and "simulated research, not investment advice" in html
    assert "AAPL" in html and "Signal engine" in html and "sec" in html
    assert "30 scored" in html  # the leaderboard's own gate note, not a fabricated verdict
    assert digest.LIVE_SITE in html


def test_render_html_flags_a_data_quality_gap():
    d = digest.build_digest(overview(data_quality={"ok": False, "gaps": [{"from": "2025-12-29", "to": "2026-08-20", "days": 234}]}), FREE_STATUS, BOARD_INSUFFICIENT, [])
    html = digest.render_html(d)
    assert "Data quality warning" in html and "234d" in html


def test_render_html_shows_a_ranked_agent_once_the_gate_opens():
    board = {"agents": [{"agent": "Analyst0", "ranked": True, "hit_rate": 0.6, "mean_edge": 0.011, "directional_calls": 34}], "note": "..."}
    d = digest.build_digest(overview(), FREE_STATUS, board, [])
    html = digest.render_html(d)
    assert "Analyst0" in html and "60%" in html and "34" in html


# ----------------------------------------------------------------- smtp config --


def test_smtp_config_needs_all_three_values(monkeypatch):
    for k in ("DIGEST_SMTP_USER", "DIGEST_SMTP_APP_PASSWORD", "DIGEST_TO_EMAIL", "DIGEST_SMTP_HOST", "DIGEST_SMTP_PORT"):
        monkeypatch.delenv(k, raising=False)
    assert digest.smtp_config() is None
    monkeypatch.setenv("DIGEST_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("DIGEST_SMTP_APP_PASSWORD", "x" * 16)
    assert digest.smtp_config() is None  # still missing the recipient
    monkeypatch.setenv("DIGEST_TO_EMAIL", "admin@example.com")
    cfg = digest.smtp_config()
    assert cfg == {"host": "smtp.gmail.com", "port": 587, "user": "bot@example.com", "password": "x" * 16, "to": "admin@example.com"}


# --------------------------------------------------------------------------- run --


def test_run_reports_not_configured_but_is_not_a_failure(monkeypatch):
    """Not-yet-turned-on is the same convention as SEC/insiders without SEC_USER_AGENT: it must never
    mark the whole pipeline day 'partial' just because nobody added a credential yet."""
    monkeypatch.setattr(digest, "gather", lambda book=None: digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, []))
    monkeypatch.delenv("DIGEST_SMTP_USER", raising=False)
    out = digest.run()
    assert out["ok"] is True and out["sent"] is False and "not configured" in out["detail"]


def test_run_sends_through_the_injected_runner_and_reports_success(monkeypatch):
    monkeypatch.setattr(digest, "gather", lambda book=None: digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, []))
    monkeypatch.setenv("DIGEST_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("DIGEST_SMTP_APP_PASSWORD", "x" * 16)
    monkeypatch.setenv("DIGEST_TO_EMAIL", "admin@example.com")
    seen = {}

    def fake_send(subject, html, cfg):
        seen.update(subject=subject, html=html, cfg=cfg)

    out = digest.run(runner=fake_send)
    assert out == {"ok": True, "sent": True, "detail": "sent to admin@example.com"}
    assert "2026-09-22" in seen["subject"] and seen["cfg"]["to"] == "admin@example.com" and "<!doctype html>" in seen["html"]


def test_run_never_raises_when_sending_fails(monkeypatch):
    monkeypatch.setattr(digest, "gather", lambda book=None: digest.build_digest(overview(), FREE_STATUS, BOARD_INSUFFICIENT, []))
    monkeypatch.setenv("DIGEST_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("DIGEST_SMTP_APP_PASSWORD", "x" * 16)
    monkeypatch.setenv("DIGEST_TO_EMAIL", "admin@example.com")

    def boom(subject, html, cfg):
        raise ConnectionError("smtp.gmail.com refused the connection")

    out = digest.run(runner=boom)
    assert out["ok"] is False and out["sent"] is False and "ConnectionError" in out["detail"]


def test_run_never_raises_when_gathering_fails(monkeypatch):
    def boom(book=None):
        raise RuntimeError("no price data")

    monkeypatch.setattr(digest, "gather", boom)
    out = digest.run()
    assert out["ok"] is False and "build failed" in out["detail"]
