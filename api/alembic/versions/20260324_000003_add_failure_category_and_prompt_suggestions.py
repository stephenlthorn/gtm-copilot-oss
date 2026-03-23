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

    # prompt_suggestions table added in Task 2 after model exists


def downgrade() -> None:
    # prompt_suggestions drop added in Task 2
    op.drop_column("ai_feedback", "failure_category")
