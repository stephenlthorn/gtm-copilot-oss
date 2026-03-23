"""Add failure_category to ai_feedback and create prompt_suggestions table.

Revision ID: 20260324_000003
Revises: 20260324_000002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260324_000003"
down_revision = "20260324_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        uuid_col = sa.BINARY(16)
    else:
        uuid_col = sa.Text()

    op.add_column(
        "ai_feedback",
        sa.Column("failure_category", sa.String(64), nullable=True),
    )

    op.create_table(
        "prompt_suggestions",
        sa.Column("id", uuid_col, primary_key=True),
        sa.Column("mode", sa.String(64), nullable=False),
        sa.Column("failure_category", sa.String(64), nullable=False),
        sa.Column("prompt_type", sa.String(16), nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("current_prompt", sa.Text, nullable=False),
        sa.Column("suggested_prompt", sa.Text, nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_prompt_suggestions_mode_category",
        "prompt_suggestions",
        ["mode", "failure_category"],
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_suggestions_mode_category", table_name="prompt_suggestions")
    op.drop_table("prompt_suggestions")
    op.drop_column("ai_feedback", "failure_category")
