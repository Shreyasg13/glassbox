"""Engine-construction correctness for app/db.py's SQLite/Postgres
dialect branch (build_engine). This is deliberately narrow -- app.db
binds its module-level `engine` once at import time (see test_auth.py's
docstring for why the rest of db.py isn't unit-tested this way), so
build_engine() is the one piece of that logic extracted to be callable
directly against arbitrary URLs without needing a real database or a
module reload.

Regression coverage for a real bug hit in production: the first Google
OAuth callback after this app's Neon cutover 500'd with
`psycopg.OperationalError: consuming input failed: SSL connection has
been closed unexpectedly` -- Neon's pooled endpoint had silently closed
an idle backend connection that SQLAlchemy's pool still considered
valid. pool_pre_ping/pool_recycle are the fix; these tests assert they
are actually set on the Postgres branch, not just described in a
comment.
"""
from __future__ import annotations

from app import db


def test_sqlite_url_gets_check_same_thread_and_no_pool_pre_ping():
    engine = db.build_engine("sqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
    assert engine.pool._pre_ping is False


def test_postgres_url_gets_pre_ping_and_recycle():
    engine = db.build_engine("postgresql+psycopg://user:pass@example.com/db")
    assert engine.dialect.name == "postgresql"
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 280


def test_postgres_url_gets_sslmode_require_when_absent():
    engine = db.build_engine("postgresql+psycopg://user:pass@example.com/db")
    assert engine.url.query.get("sslmode") == "require"


def test_postgres_url_keeps_existing_sslmode():
    """Neon's own connection strings already carry sslmode=require (and
    sometimes channel_binding=require) -- must not be overwritten with a
    different value if the caller already specified one."""
    engine = db.build_engine("postgresql+psycopg://user:pass@example.com/db?sslmode=verify-full")
    assert engine.url.query.get("sslmode") == "verify-full"
