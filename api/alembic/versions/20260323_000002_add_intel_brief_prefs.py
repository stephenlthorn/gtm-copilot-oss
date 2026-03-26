"""Add intel_brief preference columns to user_preferences

Revision ID: 20260323_000002
Revises: 20260323_000001
Create Date: 2026-03-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

revision = "20260323_000002"
down_revision = "20260323_000001"
branch_labels = None
depends_on = None


def _safe_add_column(table, col):
    try:
        op.add_column(table, col)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1060:
            raise


def upgrade() -> None:
    _safe_add_column("user_preferences", sa.Column(
        "intel_brief_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
    ))
    _safe_add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_model", sa.String(64), nullable=True, server_default="gpt-5.4-mini"
    ))
    _safe_add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_effort", sa.String(16), nullable=True
    ))
    _safe_add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_model", sa.String(64), nullable=True, server_default="gpt-5.4"
    ))
    _safe_add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_effort", sa.String(16), nullable=False, server_default="medium"
    ))


def downgrade() -> None:
    op.drop_column("user_preferences", "intel_brief_synthesis_effort")
    op.drop_column("user_preferences", "intel_brief_synthesis_model")
    op.drop_column("user_preferences", "intel_brief_summarizer_effort")
    op.drop_column("user_preferences", "intel_brief_summarizer_model")
    op.drop_column("user_preferences", "intel_brief_enabled")
