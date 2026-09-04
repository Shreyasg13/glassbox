"""Auth correctness: dev-account precedence, real signup/login via the
users table, password hashing, reserved usernames, and case-insensitive
username lookup. db.get_user_by_username/create_user are monkeypatched
to an in-memory dict here rather than hitting the real DB file -- same
approach as test_llm_call_logging.py's db stubbing, since app/db.py
binds its engine/DB_PATH at import time and can't be redirected per-test."""
from __future__ import annotations

import pytest

from app import auth


@pytest.fixture(autouse=True)
def _fake_user_store(monkeypatch):
    store: dict[str, dict] = {}  # username_lower -> row

    def fake_get_user_by_username(username: str):
        return store.get(username.strip().lower())

    def fake_create_user(data: dict):
        row = dict(data)
        row["id"] = "fake-id"
        store[row["username_lower"]] = row
        return row

    monkeypatch.setattr(auth.db, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(auth.db, "create_user", fake_create_user)
    return store


def test_dev_accounts_still_work():
    assert auth.authenticate("admin", "admin") == auth.TokenPayload(sub="admin", role="admin")
    assert auth.authenticate("user", "user") == auth.TokenPayload(sub="user", role="viewer")


def test_dev_account_wrong_password_rejected():
    assert auth.authenticate("admin", "wrong") is None


def test_unknown_username_rejected():
    assert auth.authenticate("nobody", "whatever") is None


def test_signup_creates_a_real_viewer_account():
    identity = auth.signup("shreyash", "correct-horse")
    assert identity == auth.TokenPayload(sub="shreyash", role="viewer")


def test_signup_then_login_round_trips_with_hashed_password():
    auth.signup("shreyash", "correct-horse")
    identity = auth.authenticate("shreyash", "correct-horse")
    assert identity == auth.TokenPayload(sub="shreyash", role="viewer")


def test_signup_then_login_wrong_password_rejected():
    auth.signup("shreyash", "correct-horse")
    assert auth.authenticate("shreyash", "wrong-password") is None


def test_password_is_actually_hashed_not_stored_plain(_fake_user_store):
    auth.signup("shreyash", "correct-horse")
    stored = _fake_user_store["shreyash"]
    assert stored["password_hash"] != "correct-horse"
    assert stored["password_hash"].startswith("$2b$")  # bcrypt hash prefix


@pytest.mark.parametrize("reserved", ["admin", "Admin", "ADMIN", "user", "User"])
def test_reserved_usernames_rejected_case_insensitively(reserved):
    with pytest.raises(auth.SignupError, match="reserved"):
        auth.signup(reserved, "correct-horse")


def test_duplicate_username_rejected():
    auth.signup("shreyash", "correct-horse")
    with pytest.raises(auth.SignupError, match="already taken"):
        auth.signup("shreyash", "different-password")


def test_duplicate_username_rejected_case_insensitively():
    auth.signup("shreyash", "correct-horse")
    with pytest.raises(auth.SignupError, match="already taken"):
        auth.signup("SHREYASH", "different-password")


def test_username_too_short_rejected():
    with pytest.raises(auth.SignupError, match="Username"):
        auth.signup("ab", "correct-horse")


def test_password_too_short_rejected():
    with pytest.raises(auth.SignupError, match="Password"):
        auth.signup("shreyash", "abc")


def test_signed_up_account_can_get_a_real_jwt():
    identity = auth.signup("shreyash", "correct-horse")
    token = auth.create_access_token(identity)
    decoded = auth.decode_token(token)
    assert decoded == identity


def test_login_via_db_user_can_get_a_real_jwt():
    auth.signup("shreyash", "correct-horse")
    identity = auth.authenticate("shreyash", "correct-horse")
    assert identity is not None
    token = auth.create_access_token(identity)
    decoded = auth.decode_token(token)
    assert decoded.sub == "shreyash"
    assert decoded.role == "viewer"
