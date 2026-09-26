"""verification_results (S3 T4)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=True),
        sa.Column("check_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),  # pass | fail | warn
        sa.Column("expected", sa.String(), nullable=True),
        sa.Column("observed", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_verification_results_run_id", "verification_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_verification_results_run_id", table_name="verification_results")
    op.drop_table("verification_results")