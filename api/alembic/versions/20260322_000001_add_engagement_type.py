"""Add engagement_type to chorus_calls

Revision ID: 20260322_000001
Revises: 20260320_000001
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260322_000001"
down_revision = "20260320_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chorus_calls",
        sa.Column("engagement_type", sa.String(64), nullable=False, server_default="call"),
    )
    op.create_index("ix_chorus_calls_engagement_type", "chorus_calls", ["engagement_type"])


def downgrade() -> None:
    op.drop_index("ix_chorus_calls_engagement_type", table_name="chorus_calls")
    op.drop_column("chorus_calls", "engagement_type")
