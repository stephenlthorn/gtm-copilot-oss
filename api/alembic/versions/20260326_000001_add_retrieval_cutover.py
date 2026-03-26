"""add retrieval_cutover to kb_config

Revision ID: 20260326_000001
Revises: 20260325_000001
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

revision = "20260326_000001"
down_revision = "20260325_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.add_column(
            "kb_config",
            sa.Column("retrieval_cutover", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1060:
            raise


def downgrade() -> None:
    op.drop_column("kb_config", "retrieval_cutover")
