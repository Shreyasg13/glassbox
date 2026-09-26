"""Verification configuration (S3 T4).

Staleness windows for each source type. Marked as pending owner confirmation
(decision D9) so the values can be adjusted without code changes once the
product owner reviews them.

Trading days: skip Saturday/Sunday (no holiday calendar).
"""
from __future__ import annotations

from datetime import timedelta

# Staleness windows: maximum age of data (as_of vs run_date) before a WARN.
# Source -> maximum age. Beyond this window, the check returns 'warn' (not 'fail').
# These are the plan's starting values; marked PENDING OWNER CONFIRMATION (decision D9).
DEFAULT_WINDOWS: dict[str, timedelta] = {
    "prices": timedelta(days=1),      # 1 trading day
    "sec_facts": timedelta(days=120), # ~4 months
    "sec_filings": timedelta(days=120),
    "sec_insiders": timedelta(days=14),
    "treasury": timedelta(days=35),
    "bls": timedelta(days=35),
}

# Sources that use trading-day calendar (skip weekends)
TRADING_DAY_SOURCES = {"prices"}