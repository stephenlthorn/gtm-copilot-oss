"""add reasoning_effort to kb_config

Revision ID: 20260313_000007
Revises: 20260312_000006
Create Date: 2026-03-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260313_000007"
down_revision = "20260312_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_config", sa.Column("reasoning_effort", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_config", "reasoning_effort")
