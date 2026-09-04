"""Seeds 5 demo viewer accounts with distinct watchlists, for QA/demo
purposes -- so dashboard behavior (Portfolio Overview, agent
performance, stress test) can actually be eyeballed differently per
"user" rather than every login showing the identical shared 15-symbol
universe (which is what every account saw before routers/data.py's
api_holdings gained the tickers-filter this seed script exists to
exercise).

Run via: python -m app.scripts.seed_demo_users

Real accounts in the same `users` table real signups use -- bcrypt-
hashed passwords, same as auth.signup, just created directly via db.py
rather than through the rate-limited public endpoint (this is a trusted
server-side seed, not a public-facing flow). Idempotent: checks
existing usernames before creating, so running this twice creates
nothing new.

Passwords are intentionally simple and documented here, the same
convention this codebase already uses for the hardcoded admin/admin and
user/user dev accounts (auth.py) -- these are demo/QA accounts, not
real user data, and hiding a "secret" that's printed in this file's own
source would be theater, not security.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from app import auth, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_demo_users")

DEMO_USERS = [
    {
        "username": "demo_growth",
        "password": "demo-pass-1",
        "tickers": ["AAPL", "NVDA", "TSLA"],
        "note": "Aggressive tech growth",
    },
    {
        "username": "demo_income",
        "password": "demo-pass-2",
        "tickers": ["JNJ", "V", "TLT"],
        "note": "Defensive / income-oriented",
    },
    {
        "username": "demo_index",
        "password": "demo-pass-3",
        "tickers": ["SPY", "QQQ", "IWM"],
        "note": "Broad index / ETF core",
    },
    {
        "username": "demo_finance",
        "password": "demo-pass-4",
        "tickers": ["JPM", "V", "GOOGL"],
        "note": "Financials + mega-cap tilt",
    },
    {
        "username": "demo_diversified",
        "password": "demo-pass-5",
        "tickers": ["AAPL", "JPM", "JNJ", "GLD", "TLT"],
        "note": "Multi-sector diversified (5 symbols)",
    },
]


def _seed_users() -> None:
    existing = {row["username_lower"] for row in db.list_users()}
    for entry in DEMO_USERS:
        username_lower = entry["username"].lower()
        if username_lower in existing:
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
            }
        )
        log.info("[user] created %r -- %s: %s", entry["username"], entry["note"], ", ".join(entry["tickers"]))


def main() -> int:
    _seed_users()
    log.info("Done. Log in as any demo_* user (see this file's DEMO_USERS for passwords) to see a personalized dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
