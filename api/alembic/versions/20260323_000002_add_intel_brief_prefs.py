"""Add intel_brief preference columns to user_preferences

Revision ID: 20260323_000002
Revises: 20260323_000001
Create Date: 2026-03-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260323_000002"
down_revision = "20260323_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_preferences", sa.Column(
        "intel_brief_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_model", sa.String(64), nullable=True, server_default="gpt-5.4-mini"
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_effort", sa.String(16), nullable=True
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_model", sa.String(64), nullable=True, server_default="gpt-5.4"
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_effort", sa.String(16), nullable=False, server_default="medium"
    ))


def downgrade() -> None:
    op.drop_column("user_preferences", "intel_brief_synthesis_effort")
    op.drop_column("user_preferences", "intel_brief_synthesis_model")
    op.drop_column("user_preferences", "intel_brief_summarizer_effort")
    op.drop_column("user_preferences", "intel_brief_summarizer_model")
    op.drop_column("user_preferences", "intel_brief_enabled")
