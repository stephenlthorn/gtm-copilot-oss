"""Add meeting_summary and action_items to chorus_calls

Revision ID: 20260322_000002
Revises: 20260322_000001
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260322_000002"
down_revision = "20260322_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chorus_calls", sa.Column("meeting_summary", sa.Text, nullable=True))
    op.add_column("chorus_calls", sa.Column("action_items", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("chorus_calls", "action_items")
    op.drop_column("chorus_calls", "meeting_summary")
