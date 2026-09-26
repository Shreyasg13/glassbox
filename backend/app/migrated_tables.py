"""Tables created and changed ONLY by Alembic migrations (app/migrations), starting with the S3 work.

Why a separate MetaData: the older tables in app/db.py are created by `metadata.create_all` at import time, which can only
ADD tables. Everything from S3 onward needs real, reversible migrations (renames, new columns, rollbacks). Keeping these tables
out of db.metadata means `create_all` never creates them behind Alembic's back, so the two mechanisms cannot fight.

Rules for adding a table here:
  1. define it below, 2. write a revision under app/migrations/versions with BOTH upgrade() and downgrade(),
  3. never hand-edit a deployed schema. Autogenerate is fenced by `include_object` in migrations/env.py so it can only ever
     see these tables and can never propose dropping one of the older ones.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, MetaData, String, Table

migrated_metadata = MetaData()

feature_flags_table = Table(
    "feature_flags",
    migrated_metadata,
    Column("key", String, primary_key=True),
    Column("enabled", Boolean, nullable=False),
    Column("updated_by", String, nullable=False, default=""),
    Column("updated_at", String, nullable=False, default=""),
)


def include_object(obj, name, type_, reflected, compare_to):
    """Autogenerate fence (used by migrations/env.py): it may only see the migration-managed tables above, so it can never
    propose dropping or altering an older table that lives in app/db.py."""
    if type_ == "table":
        return name in migrated_metadata.tables
    return True
