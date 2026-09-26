"""source_snapshots: point-in-time record of every external data fetch (S3 T10)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False, server_default=""),
        sa.Column("as_of", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_source_snapshots_source_ticker_fetched", "source_snapshots", ["source", "ticker", "fetched_at"])
    # Use batch mode for unique constraint (SQLite doesn't support ALTER TABLE ADD CONSTRAINT)
    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.create_unique_constraint("uq_source_snapshots_source_ticker_hash", ["source", "ticker", "payload_hash"])


def downgrade() -> None:
    # Use batch mode for dropping unique constraint
    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.drop_constraint("uq_source_snapshots_source_ticker_hash", type_="unique")
    op.drop_index("ix_source_snapshots_source_ticker_fetched", "source_snapshots")
    op.drop_table("source_snapshots")
