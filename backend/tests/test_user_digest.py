"""Per-user digests: opt-in, verified addresses only, watchlist-scoped content, one bad recipient
never blocks the rest, no double sends. No real SMTP; the sender is injected."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import digest, user_digest as ud

CFG = {"host": "h", "port": 587, "user": "bot@example.com", "password": "x", "to": "admin@example.com"}
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    monkeypatch.setenv("DIGEST_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("DIGEST_SMTP_APP_PASSWORD", "x")
    monkeypatch.setenv("DIGEST_TO_EMAIL", "admin@example.com")


def make_user(real_db, name="ann", **extra):
    row = {"username": name, "username_lower": name, "password_hash": "h", "role": "viewer", "tickers": ["AAPL", "NVDA"]}
    row.update(extra)
    return real_db.create_user(row)


def reload(real_db, row):
    return next(r for r in real_db.list_users() if r["id"] == row["id"])


class Book:
    def __init__(self, latest="2026-09-24", gaps=()):
        self.latest_date, self._gaps = latest, list(gaps)

    def gaps(self):
        return self._gaps


STANCE_ROWS = [
    {"symbol": "AAPL", "name": "Apple", "attention": True, "watch": False, "engine": {"signal": "BUY"}, "committee": {"action": "BUY", "headline": "Strong quarter"}, "risk": {"level": "LOW"}, "summary": "engine says BUY (70% confidence)"},
    {"symbol": "NVDA", "name": "Nvidia", "attention": False, "watch": False, "engine": {"signal": "HOLD"}, "committee": None, "risk": None, "summary": "No action suggested: hold what you have."},
]


@pytest.fixture
def stance(monkeypatch):
    calls = []

    def fake(book, tickers=None):
        calls.append(tickers)
        rows = [r for r in STANCE_ROWS if not tickers or r["symbol"] in tickers]
        return {"as_of": book.latest_date, "rows": rows, "macro_line": "Rates steady."}

    monkeypatch.setattr("app.strategy.stance", fake)
    return calls


class Outbox:
    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], set(fail_for)

    def __call__(self, subject, html, cfg, headers=None):
        if cfg["to"] in self.fail_for:
            raise RuntimeError("smtp down")
        self.sent.append({"subject": subject, "html": html, "to": cfg["to"], "headers": headers or {}})


# ------------------------------------------------------------------ settings --


def test_enabling_with_an_unverified_address_needs_confirmation_and_sends_nothing_yet(real_db):
    row = make_user(real_db)
    out = ud.apply_prefs(row, True, "Ann@Example.com", "daily", NOW)
    assert out["email"] == "ann@example.com" and out["verified"] is False and out["confirmation_needed"] is True
    assert ud.deliverable_address(reload(real_db, row)) is None  # not confirmed, so never a recipient


def test_confirmation_link_verifies_only_the_address_it_was_issued_for(real_db):
    row = make_user(real_db)
    ud.apply_prefs(row, True, "ann@example.com", "daily", NOW)
    row = reload(real_db, row)
    old_token = ud.make_token("confirm", row["id"], "ann@example.com")
    ud.apply_prefs(row, True, "other@example.com", "daily", NOW)  # address changed before clicking
    assert ud.confirm_pending(reload(real_db, row), old_token) is False
    row = reload(real_db, row)
    assert ud.confirm_pending(row, ud.make_token("confirm", row["id"], "other@example.com")) is True
    assert ud.deliverable_address(reload(real_db, row)) == "other@example.com"


def test_a_forged_or_empty_token_is_rejected(real_db):
    row = make_user(real_db)
    ud.apply_prefs(row, True, "ann@example.com", "daily", NOW)
    row = reload(real_db, row)
    assert ud.confirm_pending(row, "") is False and ud.confirm_pending(row, "0" * 32) is False
    assert not ud.check_token("unsubscribe", row["id"], ud.make_token("confirm", row["id"]))  # purposes don't cross


def test_google_account_email_counts_as_verified(real_db):
    row = make_user(real_db, "g@example.com", oauth_provider="google", oauth_subject="1", email="g@example.com")
    out = ud.apply_prefs(row, True, None, "daily", NOW)
    assert out["verified"] is True and out["confirmation_needed"] is False
    assert ud.deliverable_address(reload(real_db, row)) == "g@example.com"


def test_validation(real_db):
    row = make_user(real_db)
    with pytest.raises(ValueError):
        ud.apply_prefs(row, True, "not-an-email", "daily", NOW)
    with pytest.raises(ValueError):
        ud.apply_prefs(row, True, None, "daily", NOW)  # password account with no address
    with pytest.raises(ValueError):
        ud.apply_prefs(row, True, "a@b.co", "hourly", NOW)
    with pytest.raises(ValueError):
        ud.apply_prefs(row, True, "a@b.co\nBcc: x@y.com", "daily", NOW)  # header injection


def test_confirmation_email_is_rate_limited(real_db):
    row = make_user(real_db)
    assert ud.apply_prefs(row, True, "ann@example.com", "daily", NOW)["confirmation_needed"] is True
    row = reload(real_db, row)
    assert ud.apply_prefs(row, True, "ann@example.com", "daily", NOW + timedelta(minutes=1))["confirmation_needed"] is False
    assert ud.apply_prefs(reload(real_db, row), True, "ann@example.com", "daily", NOW + timedelta(minutes=11))["confirmation_needed"] is True


# ------------------------------------------------------------------- content --


def test_content_is_scoped_to_the_users_watchlist_and_escaped(real_db, stance):
    row = make_user(real_db, tickers=["AAPL"])
    d = ud.build_user_digest(ud._stance_for(Book(), ["AAPL"], {}))
    assert [r["symbol"] for r in d["attention"]] == ["AAPL"] and d["quiet"] == [] and d["n"] == 1
    assert "1 of your 1" in ud.subject_for(d)
    html = ud.render_html(d, "https://x/unsub")
    assert "Strong quarter" in html and "not investment advice" in html and "https://x/unsub" in html
    evil = ud.build_user_digest({"as_of": "d", "rows": [dict(STANCE_ROWS[0], summary="<script>alert(1)</script>")]})
    assert "<script>" not in ud.render_html(evil, "u")


# ----------------------------------------------------------------------- run --


def enable(real_db, row, addr="ann@example.com", freq="daily"):
    ud.apply_prefs(row, True, addr, freq, NOW)
    r = reload(real_db, row)
    ud.confirm_pending(r, ud.make_token("confirm", r["id"], addr))
    return reload(real_db, row)


def test_run_sends_only_to_opted_in_verified_users_with_unsubscribe_headers(real_db, stance):
    a = enable(real_db, make_user(real_db, "ann"), "ann@example.com")
    make_user(real_db, "bob")  # never opted in
    c = make_user(real_db, "cy")
    ud.apply_prefs(c, True, "cy@example.com", "daily", NOW)  # opted in but never confirmed
    box = Outbox()
    out = ud.run(Book(), box, real_db.list_users())
    assert out["sent"] == 1 and out["failed"] == 0 and [m["to"] for m in box.sent] == ["ann@example.com"]
    assert "List-Unsubscribe" in box.sent[0]["headers"] and "/api/digest/unsubscribe?u=" + a["id"] in box.sent[0]["headers"]["List-Unsubscribe"]
    assert reload(real_db, a)["digest"]["last_sent"] == "2026-09-24"


def test_run_is_idempotent_for_the_same_day(real_db, stance):
    enable(real_db, make_user(real_db, "ann"))
    box = Outbox()
    ud.run(Book(), box, real_db.list_users())
    ud.run(Book(), box, real_db.list_users())
    assert len(box.sent) == 1


def test_one_failing_recipient_does_not_block_the_others(real_db, stance):
    a = enable(real_db, make_user(real_db, "ann"), "ann@example.com")
    b = enable(real_db, make_user(real_db, "bea"), "bea@example.com")
    box = Outbox(fail_for={"ann@example.com"})
    out = ud.run(Book(), box, real_db.list_users())
    assert out["sent"] == 1 and out["failed"] == 1 and out["ok"] is True
    assert [m["to"] for m in box.sent] == ["bea@example.com"]
    assert "RuntimeError" in reload(real_db, a)["digest"]["last_error"] and reload(real_db, b)["digest"]["last_error"] is None


def test_weekly_users_only_get_friday(real_db, stance):
    enable(real_db, make_user(real_db, "ann"), freq="weekly")
    box = Outbox()
    ud.run(Book("2026-09-24"), box, real_db.list_users())  # Thursday
    assert box.sent == []
    ud.run(Book("2026-09-25"), box, real_db.list_users())  # Friday
    assert len(box.sent) == 1


def test_users_with_the_same_watchlist_share_one_stance_computation(real_db, stance):
    enable(real_db, make_user(real_db, "ann"), "ann@example.com")
    enable(real_db, make_user(real_db, "bea"), "bea@example.com")
    ud.run(Book(), Outbox(), real_db.list_users())
    assert len(stance) == 1


def test_unsubscribe_turns_it_off_and_run_skips(real_db, stance):
    row = enable(real_db, make_user(real_db, "ann"))
    ud.unsubscribe(row)
    box = Outbox()
    assert ud.run(Book(), box, real_db.list_users())["sent"] == 0 and box.sent == []


def test_not_configured_is_not_a_failure(real_db, monkeypatch):
    monkeypatch.delenv("DIGEST_SMTP_USER")
    out = ud.run(Book(), Outbox(), [])
    assert out["ok"] is True and out["sent"] == 0 and "not configured" in out["detail"]


def test_a_broken_book_is_reported_not_raised(real_db):
    class Bad:
        latest_date = "2026-09-24"

        def gaps(self):
            raise RuntimeError("boom")

    out = ud.run(Bad(), Outbox(), [])
    assert out["ok"] is False and "boom" in out["detail"]


def test_preview_needs_a_verified_address_and_is_rate_limited(real_db, stance):
    row = make_user(real_db)
    ud.apply_prefs(row, False, "ann@example.com", "daily", NOW)
    assert ud.send_preview(reload(real_db, row), Book(), Outbox(), NOW)["ok"] is False  # unverified
    row = enable(real_db, row)
    box = Outbox()
    assert ud.send_preview(row, Book(), box, NOW)["ok"] is True and len(box.sent) == 1
    assert ud.send_preview(reload(real_db, row), Book(), box, NOW + timedelta(seconds=30))["ok"] is False


# ------------------------------------------------------------------- routes --


def test_public_confirm_and_unsubscribe_links_over_http(real_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import user_digest as routes

    app = FastAPI()
    app.include_router(routes.public_router)
    c = TestClient(app)
    row = make_user(real_db)
    ud.apply_prefs(row, True, "ann@example.com", "daily", NOW)
    uid = row["id"]
    assert c.get("/api/digest/confirm", params={"u": uid, "t": "bad"}).status_code == 400
    ok = c.get("/api/digest/confirm", params={"u": uid, "t": ud.make_token("confirm", uid, "ann@example.com")})
    assert ok.status_code == 200 and ud.deliverable_address(reload(real_db, row)) == "ann@example.com"
    assert c.post("/api/digest/unsubscribe", params={"u": uid, "t": "bad"}).status_code == 400
    assert c.post("/api/digest/unsubscribe", params={"u": uid, "t": ud.make_token("unsubscribe", uid)}).status_code == 200
    assert ud.deliverable_address(reload(real_db, row)) is None
    assert c.get("/api/digest/confirm", params={"u": "nope", "t": "x"}).status_code == 400
