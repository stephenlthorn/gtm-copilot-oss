"""Add reasoning_effort to kb_config and create user_preferences table.

Revision ID: 20260316_000001
Revises: 20260302_000005
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

revision = "20260316_000001"
down_revision = "20260302_000005"
branch_labels = None
depends_on = None


def _safe_add_column(table: str, col: sa.Column) -> None:
    try:
        op.add_column(table, col)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1060:
            raise


def _safe_create_table(name: str, *args, **kwargs) -> None:
    try:
        op.create_table(name, *args, **kwargs)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1050:  # 1050 = Table already exists
            raise


def upgrade() -> None:
    _safe_add_column(
        "kb_config",
        sa.Column("reasoning_effort", sa.String(16), nullable=False, server_default="medium"),
    )

    _safe_create_table(
        "user_preferences",
        sa.Column("user_email", sa.String(255), primary_key=True),
        sa.Column("llm_model", sa.String(64), nullable=True),
        sa.Column("reasoning_effort", sa.String(16), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_column("kb_config", "reasoning_effort")
