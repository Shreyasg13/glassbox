"""One-time copy of the existing SQLite database into a Postgres/Neon
database, for the app/db.py -> Neon cutover.

Run via: python -m app.scripts.migrate_to_postgres postgresql+psycopg://...

Reads from the SQLite file at GLASSBOX_DB_PATH (same env var app.db uses),
writes to the Postgres URL given on the command line -- deliberately a CLI
arg, not DATABASE_URL, so this script can run once against the live SQLite
data BEFORE the app itself is cut over to reading DATABASE_URL (otherwise
there'd be nothing left to read from). Creates the destination schema via
metadata.create_all() (same call app.db already makes for SQLite), then
copies every row, table by table, in metadata.sorted_tables order.

Not idempotent against a partially-migrated destination -- rerunning
against a destination that already has rows will fail on the primary-key
conflict rather than silently duplicating or overwriting. Point it at an
empty database, or pass --truncate-dest to clear the destination tables
first (only real use case: redoing a migration after fixing a mistake,
since this app's writes stop hitting SQLite the moment the cutover happens
-- there's no ongoing sync to reconcile).
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, insert, select

from .. import db


def migrate(dest_url: str, truncate_dest: bool) -> None:
    print(f"Source (SQLite): {db.DB_PATH}")
    print(f"Destination: {dest_url.split('@')[-1] if '@' in dest_url else dest_url}")

    source_engine = create_engine(f"sqlite:///{db.DB_PATH}", connect_args={"check_same_thread": False})
    dest_engine = create_engine(dest_url)

    db.metadata.create_all(dest_engine)

    with source_engine.connect() as src_conn, dest_engine.begin() as dest_conn:
        if truncate_dest:
            for table in reversed(db.metadata.sorted_tables):
                dest_conn.execute(table.delete())

        for table in db.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in src_conn.execute(select(table))]
            if not rows:
                print(f"  {table.name}: 0 rows (nothing to copy)")
                continue
            dest_conn.execute(insert(table), rows)
            print(f"  {table.name}: {len(rows)} rows copied")

    print("Done. Verify row counts above match the source before switching DATABASE_URL live.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dest_url", help="Destination Postgres URL, e.g. postgresql+psycopg://user:pass@host/db?sslmode=require")
    parser.add_argument("--truncate-dest", action="store_true", help="Delete existing rows in the destination tables first")
    args = parser.parse_args()

    if not args.dest_url.startswith("postgresql"):
        print("Refusing to migrate: dest_url doesn't look like a Postgres URL.", file=sys.stderr)
        sys.exit(1)

    migrate(args.dest_url, args.truncate_dest)
