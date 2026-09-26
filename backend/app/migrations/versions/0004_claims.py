"""claims + committee_narratives (S3 T3)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _sqlite_triggers_claims():
    """Create SQLite BEFORE UPDATE/DELETE triggers to enforce append-only for claims."""
    op.execute(
        """
        CREATE TRIGGER claims_no_update
        BEFORE UPDATE ON claims
        BEGIN
            SELECT RAISE(ABORT, 'claims is append-only');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER claims_no_delete
        BEFORE DELETE ON claims
        BEGIN
            SELECT RAISE(ABORT, 'claims is append-only');
        END;
        """
    )


def _postgres_trigger_claims():
    """Create Postgres trigger function and triggers to enforce append-only for claims."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION claims_enforce_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'claims is append-only';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER claims_no_update
        BEFORE UPDATE ON claims
        FOR EACH ROW EXECUTE FUNCTION claims_enforce_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER claims_no_delete
        BEFORE DELETE ON claims
        FOR EACH ROW EXECUTE FUNCTION claims_enforce_append_only();
        """
    )


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_snapshot_id", sa.String(), nullable=True),
        sa.Column("source_path", sa.String(), nullable=True),
        sa.Column("text_span", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_claims_run_id", "claims", ["run_id"])

    op.create_table(
        "committee_narratives",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_requested", sa.String(), nullable=True),
        sa.Column("model_requested", sa.String(), nullable=True),
        sa.Column("provider_answered", sa.String(), nullable=True),
        sa.Column("model_answered", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        _sqlite_triggers_claims()
    elif dialect == "postgresql":
        _postgres_trigger_claims()


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS claims_no_update;")
        op.execute("DROP TRIGGER IF EXISTS claims_no_delete;")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS claims_no_update ON claims;")
        op.execute("DROP TRIGGER IF EXISTS claims_no_delete ON claims;")
        op.execute("DROP FUNCTION IF EXISTS claims_enforce_append_only();")

    op.drop_table("committee_narratives")
    op.drop_table("claims")