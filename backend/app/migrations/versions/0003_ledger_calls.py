"""ledger_calls: append-only hash-chained call ledger (S3 T11)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _sqlite_triggers():
    """Create SQLite BEFORE UPDATE/DELETE triggers to enforce append-only."""
    op.execute(
        """
        CREATE TRIGGER ledger_calls_no_update
        BEFORE UPDATE ON ledger_calls
        BEGIN
            SELECT RAISE(ABORT, 'ledger_calls is append-only');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_calls_no_delete
        BEFORE DELETE ON ledger_calls
        BEGIN
            SELECT RAISE(ABORT, 'ledger_calls is append-only');
        END;
        """
    )


def _postgres_trigger():
    """Create Postgres trigger function and triggers to enforce append-only."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ledger_calls_enforce_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'ledger_calls is append-only';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_calls_no_update
        BEFORE UPDATE ON ledger_calls
        FOR EACH ROW EXECUTE FUNCTION ledger_calls_enforce_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_calls_no_delete
        BEFORE DELETE ON ledger_calls
        FOR EACH ROW EXECUTE FUNCTION ledger_calls_enforce_append_only();
        """
    )


def upgrade() -> None:
    op.create_table(
        "ledger_calls",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("call_id", sa.String(), nullable=False, unique=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("call_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("input_snapshot_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("committee_config_id", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.String(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        _sqlite_triggers()
    elif dialect == "postgresql":
        _postgres_trigger()


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS ledger_calls_no_update;")
        op.execute("DROP TRIGGER IF EXISTS ledger_calls_no_delete;")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS ledger_calls_no_update ON ledger_calls;")
        op.execute("DROP TRIGGER IF EXISTS ledger_calls_no_delete ON ledger_calls;")
        op.execute("DROP FUNCTION IF EXISTS ledger_calls_enforce_append_only();")

    op.drop_table("ledger_calls")