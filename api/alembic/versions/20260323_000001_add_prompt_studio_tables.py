"""Add prompt_registry, prompt_versions, prompt_user_overrides tables

Revision ID: 20260323_000001
Revises: 20260322_000002
Create Date: 2026-03-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260323_000001"
down_revision = "20260322_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_registry",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_content", sa.Text, nullable=False),
        sa.Column("current_content", sa.Text, nullable=False),
        sa.Column("variables", sa.Text, nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "prompt_id",
            sa.String(64),
            sa.ForeignKey("prompt_registry.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("edited_by", sa.String(255), nullable=False),
        sa.Column(
            "edited_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("note", sa.Text, nullable=True),
    )

    op.create_table(
        "prompt_user_overrides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "prompt_id",
            sa.String(64),
            sa.ForeignKey("prompt_registry.id"),
            nullable=False,
        ),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("prompt_id", "user_email"),
    )


def downgrade() -> None:
    op.drop_table("prompt_user_overrides")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_registry")
