"""Add source_profiles_json to kb_config.

Revision ID: 20260316_000003
Revises: 20260316_000002
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260316_000003"
down_revision = "20260316_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_config",
        sa.Column("source_profiles_json", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kb_config", "source_profiles_json")
