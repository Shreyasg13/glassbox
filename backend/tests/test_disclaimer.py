"""Tests for the single-source-of-truth disclaimer module and its integration points."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import disclaimer, digest, user_digest as ud
from app import committee_daily
from app.routers import public as public_routes
from app.routers import inbox as inbox_routes
from tests.test_paper_tax_committee import D, book_with


# ------------------------------------------------------------------ unit tests --


def test_file_present_returns_text_and_marker_detected(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW: placeholder wording, not approved by counsel -->\nCustom disclaimer text.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        assert disclaimer.text() == "Custom disclaimer text."
        assert disclaimer.pending_legal_review() is True


def test_file_missing_falls_back_to_default_and_logs_warning(monkeypatch, caplog):
    monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", "/nonexistent/path/disclaimer.md")
    disclaimer.clear_cache()

    with caplog.at_level("WARNING", logger="glassbox.disclaimer"):
        assert disclaimer.text() == "Simulated research, not investment advice."
    assert "disclaimer file missing or empty" in caplog.text
    # pending_legal_review should still be True (assume pending if unreadable)
    assert disclaimer.pending_legal_review() is True


def test_file_empty_falls_back_to_default(monkeypatch, caplog):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()
        # Reset the warned flag since it's global state
        import app.disclaimer as disc
        disc._warned = False

        with caplog.at_level("WARNING", logger="glassbox.disclaimer"):
            assert disclaimer.text() == "Simulated research, not investment advice."
        assert "disclaimer file missing or empty" in caplog.text


def test_env_override_works(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "custom.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nEnv override works.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        assert disclaimer.text() == "Env override works."
        assert disclaimer.pending_legal_review() is True


def test_changing_file_changes_output_after_cache_clear(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nFirst version.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        assert disclaimer.text() == "First version."

        path.write_text("<!-- PENDING LEGAL REVIEW -->\nSecond version.\n", encoding="utf-8")
        disclaimer.clear_cache()

        assert disclaimer.text() == "Second version."


# ----------------------------------------------------------------- integration --


def _make_book():
    prices = {"AAA": {0: 100.0, 551: 110.0, 555: 90.0}, "BBB": {0: 100.0, 300: 120.0}}
    signals = {"AAA": {i: "BUY" for i in range(5, 590)}, "BBB": {}}
    return book_with(prices, signals)


REVIEW = D[550]
RUNS = [
    {"date": REVIEW, "symbol": "AAA", "decision": "SELL", "action": "SELL", "engine_signal": "BUY", "quorum_ok": True, "gate": None,
     "ceo": {"label": "strong consensus", "headline": "Valuation stretched"}, "answered": 10, "total": 10, "agents": []},
]


def test_user_digest_html_uses_disclaimer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nDigest custom disclaimer.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        d = ud.build_user_digest({"as_of": "2026-09-24", "rows": [], "macro_line": "Rates steady.", "data_quality": {"ok": True, "gaps": []}, "n": 0, "attention": [], "watch": [], "quiet": []})
        html = ud.render_html(d, "https://x/unsub")
        assert "Digest custom disclaimer" in html


def test_daily_digest_html_uses_disclaimer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nDaily digest custom.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        ov = {"data_date": "2026-09-22", "latest_review_date": "2026-09-22", "pipeline": {"status": "ok", "stages": {}}, "data_quality": {"ok": True, "gaps": []}, "capital": []}
        d = digest.build_digest(ov, {}, {"agents": []}, [])
        html = digest.render_html(d)
        assert "Daily digest custom" in html


def test_committee_report_text_uses_disclaimer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nCommittee custom disclaimer.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        book = _make_book()
        report = committee_daily.build_report(REVIEW, [{"symbol": "AAA", "decision": "SELL", "engine_signal": "BUY", "votes": {}, "agents": []}])
        assert "Committee custom disclaimer" in report


def test_inbox_payload_uses_disclaimer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nInbox custom disclaimer.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        # We test the disclaimer.text() is used by checking the fallback_answer path
        # since the /api/me/ask endpoint would require full mocking
        from app import assistant
        facts = assistant.build_facts(
            {"as_of": REVIEW, "rows": [], "committee_started": REVIEW, "note": None, "first_date": "2020-01-01", "latest_date": REVIEW},
            None,
            {"reviews": 0, "reliable_reviews": 0, "agrees_with_engine": None, "by_decision_5d": {}, "note": "Small samples"}
        )
        fallback = assistant.fallback_answer(facts)
        assert "Inbox custom disclaimer" in fallback


def test_public_disclaimer_endpoint_returns_200_without_auth(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nPublic endpoint test.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        app = FastAPI()
        app.include_router(public_routes.router)
        client = TestClient(app)

        resp = client.get("/api/public/disclaimer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Public endpoint test."
        assert data["pending_legal_review"] is True


def test_public_disclaimer_endpoint_without_marker(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("Approved by legal.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        app = FastAPI()
        app.include_router(public_routes.router)
        client = TestClient(app)

        resp = client.get("/api/public/disclaimer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Approved by legal."
        assert data["pending_legal_review"] is False


def test_admin_digest_html_escapes_disclaimer(monkeypatch):
    """A disclaimer containing HTML special chars must be escaped in the admin digest HTML."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "disclaimer.md"
        path.write_text("<!-- PENDING LEGAL REVIEW -->\nBold <b> and & ampersand.\n", encoding="utf-8")
        monkeypatch.setenv("GLASSBOX_DISCLAIMER_PATH", str(path))
        disclaimer.clear_cache()

        ov = {"data_date": "2026-09-22", "latest_review_date": "2026-09-22", "pipeline": {"status": "ok", "stages": {}}, "data_quality": {"ok": True, "gaps": []}, "capital": []}
        d = digest.build_digest(ov, {}, {"agents": []}, [])
        html = digest.render_html(d)
        # The disclaimer text should appear escaped in the HTML
        assert 'Bold &lt;b&gt; and &amp; ampersand.' in html
        # And the raw HTML should NOT appear (unescaped version should not be present)
        assert "Bold <b> and & ampersand." not in html
