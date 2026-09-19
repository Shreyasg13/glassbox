"""Seeds demo viewer accounts -- one per portfolio archetype -- with distinct
watchlists and an investor profile, for QA/demo purposes and as the test set
for agent evaluation: dashboard behavior (Portfolio Overview, agent
performance, stress test) can be eyeballed differently per "user" rather than
every login showing the identical shared 15-symbol universe (routers/data.py's
api_holdings filters to the caller's `tickers`, which this seed exercises).

The archetypes are deliberately spread across risk level, horizon and asset mix
(growth, income, index, financials, diversified, 60/40, all-weather, quality,
momentum, cyclical, capital preservation) so that when per-profile paper
tracking exists, an agent that only works on one kind of portfolio shows up.
The profiles themselves live in app/paper_profiles.py (also used by the
paper-trading cycle, which does NOT need these logins to exist). Every ticker must
be inside data_source.STOCK_INFO -- tests enforce that.

Run via: python -m app.scripts.seed_demo_users

Real accounts in the same `users` table real signups use -- bcrypt-
hashed passwords, same as auth.signup, just created directly via db.py
rather than through the rate-limited public endpoint (this is a trusted
server-side seed, not a public-facing flow). Idempotent: existing accounts are
never recreated (their password and watchlist are left alone); an existing demo
account that predates the `profile` field just gets it filled in.

Passwords are intentionally simple and documented here -- these are demo/QA
accounts, not real user data, and hiding a "secret" that's printed in this
file's own source would be theater, not security. That is exactly why this
script REFUSES to run when GLASSBOX_ENV=production unless --allow-production is
passed: on a public deployment these are known-credential accounts (viewer role
only, and still subject to the per-user rate limits, but real logins nonetheless).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from app import auth, db, paper_profiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_demo_users")

# One login per profile in the shared registry (app/paper_profiles.py, which is
# also what the paper-trading cycle simulates -- with or without these logins).
# Passwords are demo-pass-1 .. demo-pass-N in registry order.
DEMO_USERS = [
    {**entry, "password": f"demo-pass-{i}"}
    for i, entry in enumerate(paper_profiles.DEMO_PROFILES, start=1)
]


def _seed_users() -> None:
    existing = {row["username_lower"]: row for row in db.list_users()}
    for entry in DEMO_USERS:
        username_lower = entry["username"].lower()
        row = existing.get(username_lower)
        if row is not None:
            if not row.get("profile"):
                # Demo account seeded before profiles existed: add only the
                # profile, leaving its password and watchlist untouched.
                db.update_user(row["id"], {"profile": entry["profile"]})
                log.info("[user] %r already exists, added its profile", entry["username"])
            else:
                log.info("[user] %r already exists, skipping", entry["username"])
            continue
        db.create_user(
            {
                "username": entry["username"],
                "username_lower": username_lower,
                "password_hash": auth._hash_password(entry["password"]),
                "role": "viewer",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tickers": entry["tickers"],
                "profile": entry["profile"],
            }
        )
        log.info("[user] created %r -- %s: %s", entry["username"], entry["note"], ", ".join(entry["tickers"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the demo viewer accounts.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="required when GLASSBOX_ENV=production: these accounts have publicly documented passwords",
    )
    args = parser.parse_args(argv)
    if os.environ.get("GLASSBOX_ENV", "").strip().lower() == "production" and not args.allow_production:
        log.error(
            "Refusing to seed known-password demo accounts into a production deployment. "
            "Re-run with --allow-production if that is really what you want."
        )
        return 2
    _seed_users()
    log.info("Done. Log in as any demo_* user (see this file's DEMO_USERS for passwords) to see a personalized dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
