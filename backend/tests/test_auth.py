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

    def fake_get_user_by_oauth(provider: str, subject: str):
        for row in store.values():
            if row.get("oauth_provider") == provider and row.get("oauth_subject") == subject:
                return row
        return None

    monkeypatch.setattr(auth.db, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(auth.db, "create_user", fake_create_user)
    monkeypatch.setattr(auth.db, "get_user_by_oauth", fake_get_user_by_oauth)
    return store


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    for name in ("GLASSBOX_ENABLE_DEV_USERS", "GLASSBOX_ENV", "GLASSBOX_ADMIN_PASSWORD", "GLASSBOX_ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(name, raising=False)


def test_hardcoded_admin_admin_no_longer_works_by_default():
    # The old built-in admin/admin was a live admin login on the public
    # deployment. It must not exist unless explicitly opted into.
    assert auth.authenticate("admin", "admin") is None
    assert auth.authenticate("user", "user") is None


def test_dev_accounts_work_only_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ENABLE_DEV_USERS", "1")
    assert auth.authenticate("admin", "admin") == auth.TokenPayload(sub="admin", role="admin")
    assert auth.authenticate("user", "user") == auth.TokenPayload(sub="user", role="viewer")


def test_dev_accounts_never_work_in_production(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ENABLE_DEV_USERS", "1")
    monkeypatch.setenv("GLASSBOX_ENV", "production")
    assert auth.authenticate("admin", "admin") is None
    assert auth.authenticate("user", "user") is None


def test_dev_account_wrong_password_rejected(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ENABLE_DEV_USERS", "1")
    assert auth.authenticate("admin", "wrong") is None


def test_bootstrap_admin_from_plain_env_password(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ADMIN_PASSWORD", "a-long-real-admin-password")
    assert auth.authenticate("admin", "a-long-real-admin-password") == auth.TokenPayload(sub="admin", role="admin")
    assert auth.authenticate("admin", "a-long-real-admin-passwor") is None
    assert auth.authenticate("admin", "admin") is None


def test_bootstrap_admin_from_bcrypt_hash_env(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ADMIN_PASSWORD_HASH", auth._hash_password("another-long-admin-pass"))
    assert auth.authenticate("admin", "another-long-admin-pass") == auth.TokenPayload(sub="admin", role="admin")
    assert auth.authenticate("admin", "wrong-password-here") is None


def test_hash_takes_precedence_over_plain_password(monkeypatch):
    monkeypatch.setenv("GLASSBOX_ADMIN_PASSWORD_HASH", auth._hash_password("the-hashed-admin-pw"))
    monkeypatch.setenv("GLASSBOX_ADMIN_PASSWORD", "the-plain-admin-password")
    assert auth.authenticate("admin", "the-hashed-admin-pw") is not None
    assert auth.authenticate("admin", "the-plain-admin-password") is None


def test_weak_plain_admin_password_is_refused(monkeypatch):
    # Under MIN_ADMIN_PASSWORD_LEN: rather than accept a guessable admin
    # password from a typo'd .env, admin login is simply disabled.
    monkeypatch.setenv("GLASSBOX_ADMIN_PASSWORD", "short")
    assert auth.authenticate("admin", "short") is None


def test_no_admin_configured_means_no_admin_login():
    assert auth.authenticate("admin", "") is None
    assert auth.authenticate("admin", "anything-at-all") is None


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


def test_oauth_login_creates_a_viewer_account_keyed_by_email():
    identity = auth.oauth_login("google", "sub-123", "shreyash@example.com")
    assert identity == auth.TokenPayload(sub="shreyash@example.com", role="viewer")


def test_oauth_login_is_idempotent_on_provider_and_subject():
    """Second login from the same Google account must return the same
    user, not create a duplicate row -- identity is keyed on
    (provider, subject), not on username/email, since email can change."""
    first = auth.oauth_login("google", "sub-123", "shreyash@example.com")
    second = auth.oauth_login("google", "sub-123", "shreyash@example.com")
    assert first == second


def test_oauth_login_stores_no_password_hash(_fake_user_store):
    auth.oauth_login("google", "sub-123", "shreyash@example.com")
    stored = _fake_user_store["shreyash@example.com"]
    assert stored["password_hash"] is None
    assert stored["oauth_provider"] == "google"
    assert stored["oauth_subject"] == "sub-123"


def test_oauth_account_cannot_log_in_with_a_password():
    """Regression test: password_hash=None on OAuth-only accounts must
    be rejected cleanly by authenticate(), not crash bcrypt.checkpw()
    with a None argument."""
    auth.oauth_login("google", "sub-123", "shreyash@example.com")
    assert auth.authenticate("shreyash@example.com", "anything") is None


def test_oauth_login_disambiguates_username_collision_with_password_account():
    """Extremely unlikely edge case (a password-signup account already
    claimed the exact email an OAuth login wants as a username) --
    must disambiguate rather than silently take over the existing
    account or crash."""
    auth.signup("taken@example.com", "correct-horse")
    identity = auth.oauth_login("google", "sub-456", "taken@example.com")
    assert identity.sub == "taken@example.com+google"


async def test_get_current_user_optional_returns_none_when_no_token():
    assert await auth.get_current_user_optional(token=None) is None


async def test_get_current_user_optional_returns_none_on_invalid_token():
    """Regression guard: /api/holdings (the caller of this dependency)
    must keep serving the shared/global view rather than 401ing when a
    stale/malformed token happens to be sent by an otherwise-anonymous
    request."""
    assert await auth.get_current_user_optional(token="not-a-real-jwt") is None


async def test_get_current_user_optional_returns_identity_for_valid_token():
    identity = auth.signup("shreyash", "correct-horse")
    token = auth.create_access_token(identity)
    result = await auth.get_current_user_optional(token=token)
    assert result == identity
