"""Alembic environment. Uses the application's own engine (so it works for SQLite and Postgres exactly as the app does) and only
ever looks at the tables in app/migrated_tables.py."""
from __future__ import annotations

from alembic import context

from app import db
from app.migrated_tables import include_object, migrated_metadata

target_metadata = migrated_metadata


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite can't ALTER most things in place
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = context.config.attributes.get("connection")  # tests hand in a throwaway database's connection
    if supplied is not None:
        _run(supplied)
        return
    with db.engine.connect() as connection:
        _run(connection)


run_migrations_online()
