"""Apply database migrations:  python -m app.migrate            (upgrade to the latest)
                             python -m app.migrate --down 0001  (roll back to a revision; "base" = everything)
                             python -m app.migrate --current    (print the revision the database is at)

Runs once at container start, BEFORE the web workers (see the Dockerfile), so two gunicorn workers never race to migrate.
A failed migration is logged loudly but does not stop the site from starting: every reader of a migrated table (see app/flags.py)
falls back to a safe default when the table is missing. Only the tables in app/migrated_tables.py are managed here; the older
tables in app/db.py are still created by db.init_schema().
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext

log = logging.getLogger("glassbox.migrate")


def make_config(connection=None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    if connection is not None:
        cfg.attributes["connection"] = connection  # tests migrate a throwaway database
    return cfg


def upgrade(connection=None, revision: str = "head") -> None:
    command.upgrade(make_config(connection), revision)


def downgrade(revision: str, connection=None) -> None:
    command.downgrade(make_config(connection), revision)


def current_revision() -> str | None:
    from . import db

    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser(description="Apply or roll back database migrations.")
    p.add_argument("--down", metavar="REVISION", help="roll back to this revision ('base' undoes everything)")
    p.add_argument("--current", action="store_true", help="print the current revision and exit")
    args = p.parse_args(argv)
    try:
        if args.current:
            print(current_revision() or "(none)")
        elif args.down:
            downgrade(args.down)
            print(f"rolled back to {args.down}")
        else:
            upgrade()
            print(f"database is at revision {current_revision()}")
        return 0
    except Exception as exc:  # noqa: BLE001 -- see the module docstring: loud, but never take the site down
        log.error("migration failed: %s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
