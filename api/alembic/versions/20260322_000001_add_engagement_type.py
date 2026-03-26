"""Add engagement_type to chorus_calls

Revision ID: 20260322_000001
Revises: 20260320_000001
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

revision = "20260322_000001"
down_revision = "20260320_000001"
branch_labels = None
depends_on = None


def _safe_add_column(table, col):
    try:
        op.add_column(table, col)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1060:
            raise


def _safe_create_index(name, table, cols, **kwargs):
    try:
        op.create_index(name, table, cols, **kwargs)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1061:
            raise


def upgrade() -> None:
    _safe_add_column(
        "chorus_calls",
        sa.Column("engagement_type", sa.String(64), nullable=False, server_default="call"),
    )
    _safe_create_index("ix_chorus_calls_engagement_type", "chorus_calls", ["engagement_type"])


def downgrade() -> None:
    op.drop_index("ix_chorus_calls_engagement_type", table_name="chorus_calls")
    op.drop_column("chorus_calls", "engagement_type")
