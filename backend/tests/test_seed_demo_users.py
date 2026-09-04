"""seed_demo_users correctness: creates all 5 accounts with real bcrypt
hashes and the right watchlists, and is idempotent on a second run --
same db stubbing approach as test_auth.py (app/db.py binds its engine
at import time and can't be redirected per-test)."""
from __future__ import annotations

from app import auth
from app.scripts import seed_demo_users


def _fake_store(monkeypatch):
    store: dict[str, dict] = {}

    def fake_list_users():
        return list(store.values())

    def fake_create_user(data: dict):
        row = dict(data)
        row["id"] = f"fake-{len(store)}"
        store[row["username_lower"]] = row
        return row

    monkeypatch.setattr(seed_demo_users.db, "list_users", fake_list_users)
    monkeypatch.setattr(seed_demo_users.db, "create_user", fake_create_user)
    return store


def test_seeds_all_five_demo_users(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    assert len(store) == 5
    assert {row["username"] for row in store.values()} == {e["username"] for e in seed_demo_users.DEMO_USERS}


def test_each_user_gets_its_own_watchlist(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    for entry in seed_demo_users.DEMO_USERS:
        assert store[entry["username"].lower()]["tickers"] == entry["tickers"]


def test_passwords_are_really_bcrypt_hashed(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    for entry in seed_demo_users.DEMO_USERS:
        row = store[entry["username"].lower()]
        assert row["password_hash"] != entry["password"]
        assert row["password_hash"].startswith("$2b$")
        assert auth._verify_password(entry["password"], row["password_hash"])


def test_running_twice_creates_nothing_new(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    seed_demo_users._seed_users()
    assert len(store) == 5
