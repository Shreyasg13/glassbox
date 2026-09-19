"""seed_demo_users correctness: creates every demo account with real bcrypt
hashes, the right watchlists and profiles, is idempotent on a second run,
backfills profiles onto pre-existing accounts without touching their
credentials, and refuses to run against production without an explicit flag --
same db stubbing approach as test_auth.py (app/db.py binds its engine at
import time and can't be redirected per-test)."""
from __future__ import annotations

import pytest

from app import auth
from app import data_source as ds
from app import paper_profiles
from app.scripts import seed_demo_users

RISK_LEVELS = {"conservative", "moderate", "aggressive"}


def _fake_store(monkeypatch):
    store: dict[str, dict] = {}

    def fake_list_users():
        return list(store.values())

    def fake_create_user(data: dict):
        row = dict(data)
        row["id"] = f"fake-{len(store)}"
        store[row["username_lower"]] = row
        return row

    def fake_update_user(user_id: str, patch: dict):
        for row in store.values():
            if row["id"] == user_id:
                row.update(patch)
                return row
        return None

    monkeypatch.setattr(seed_demo_users.db, "list_users", fake_list_users)
    monkeypatch.setattr(seed_demo_users.db, "create_user", fake_create_user)
    monkeypatch.setattr(seed_demo_users.db, "update_user", fake_update_user)
    return store


@pytest.fixture(autouse=True)
def _not_production(monkeypatch):
    monkeypatch.delenv("GLASSBOX_ENV", raising=False)


def test_seeds_all_demo_users(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    assert len(store) == len(seed_demo_users.DEMO_USERS) == 11
    assert {row["username"] for row in store.values()} == {e["username"] for e in seed_demo_users.DEMO_USERS}


def test_each_user_gets_its_own_watchlist(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    for entry in seed_demo_users.DEMO_USERS:
        assert store[entry["username"].lower()]["tickers"] == entry["tickers"]


def test_every_ticker_is_a_symbol_with_real_price_history():
    universe = set(ds.STOCK_INFO)
    for entry in seed_demo_users.DEMO_USERS:
        assert entry["tickers"], entry["username"]
        assert set(entry["tickers"]) <= universe, f"{entry['username']} uses a symbol we have no data for"
        assert len(set(entry["tickers"])) == len(entry["tickers"]), f"{entry['username']} lists a symbol twice"


def test_strategic_weights_cover_only_the_profiles_own_tickers_and_sum_to_one():
    seen = 0
    for entry in seed_demo_users.DEMO_USERS:
        w = entry["profile"].get("strategic_weights")
        if w is None:
            continue
        seen += 1
        assert set(w) == set(entry["tickers"]), entry["username"]
        assert sum(w.values()) == pytest.approx(1.0)
    assert seen >= 2  # the 60/40 and all-weather profiles


def test_logins_mirror_the_shared_registry_exactly():
    # The paper-trading cohort and the demo logins must never drift apart.
    assert [(e["username"], e["tickers"], e["profile"]) for e in seed_demo_users.DEMO_USERS] == [
        (p["username"], p["tickers"], p["profile"]) for p in paper_profiles.DEMO_PROFILES
    ]
    assert [e["password"] for e in seed_demo_users.DEMO_USERS] == [f"demo-pass-{i}" for i in range(1, 12)]


def test_usernames_and_passwords_are_unique():
    users = [e["username"].lower() for e in seed_demo_users.DEMO_USERS]
    passwords = [e["password"] for e in seed_demo_users.DEMO_USERS]
    assert len(set(users)) == len(users)
    assert len(set(passwords)) == len(passwords)
    assert not (set(users) & auth.RESERVED_USERNAMES)


def test_profiles_are_complete_and_spread_across_risk_levels(monkeypatch):
    store = _fake_store(monkeypatch)
    seed_demo_users._seed_users()
    for entry in seed_demo_users.DEMO_USERS:
        p = store[entry["username"].lower()]["profile"]
        assert p["risk_level"] in RISK_LEVELS
        assert p["horizon_years"] > 0 and p["starting_cash"] > 0 and p["archetype"]
    # The point of the cohort is coverage: no risk band may be missing.
    assert {store[e["username"].lower()]["profile"]["risk_level"] for e in seed_demo_users.DEMO_USERS} == RISK_LEVELS
    assert len({e["profile"]["archetype"] for e in seed_demo_users.DEMO_USERS}) == len(seed_demo_users.DEMO_USERS)


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
    before = {k: dict(v) for k, v in store.items()}
    seed_demo_users._seed_users()
    assert store == before


def test_existing_account_without_a_profile_only_gains_the_profile(monkeypatch):
    store = _fake_store(monkeypatch)
    store["demo_growth"] = {
        "id": "old-1", "username": "demo_growth", "username_lower": "demo_growth",
        "password_hash": "$2b$12$keep-this-exact-hash", "tickers": ["AAPL"], "role": "viewer",
    }
    seed_demo_users._seed_users()
    row = store["demo_growth"]
    assert row["profile"]["archetype"] == "growth"
    assert row["password_hash"] == "$2b$12$keep-this-exact-hash"  # credentials untouched
    assert row["tickers"] == ["AAPL"]  # a customised watchlist is not overwritten
    assert len(store) == 11


def test_refuses_to_seed_production_without_the_flag(monkeypatch):
    store = _fake_store(monkeypatch)
    monkeypatch.setenv("GLASSBOX_ENV", "production")
    assert seed_demo_users.main([]) == 2
    assert store == {}


def test_production_seed_works_with_the_explicit_flag(monkeypatch):
    store = _fake_store(monkeypatch)
    monkeypatch.setenv("GLASSBOX_ENV", "production")
    assert seed_demo_users.main(["--allow-production"]) == 0
    assert len(store) == 11
