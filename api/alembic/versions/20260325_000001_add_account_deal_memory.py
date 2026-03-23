"""Add account_deal_memory table and chorus_calls.source_type column.

Revision ID: 20260325_000001
Revises: 20260324_000003
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "20260325_000001"
down_revision = "20260324_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_deal_memory",
        sa.Column("account", sa.String(255), primary_key=True),
        sa.Column("deal_stage", sa.String(128), nullable=True),
        sa.Column("is_new_business", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("meddpicc", sa.JSON(), nullable=True),
        sa.Column("key_contacts", sa.JSON(), nullable=True),
        sa.Column("tech_stack", sa.JSON(), nullable=True),
        sa.Column("open_items", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_call_date", sa.Date(), nullable=True),
        sa.Column("pending_review", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("pending_delta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_account_deal_memory_status", "account_deal_memory", ["status"])

    # Add source_type to chorus_calls
    op.add_column(
        "chorus_calls",
        sa.Column("source_type", sa.String(32), nullable=False, server_default="chorus"),
    )
    # Make chorus_call_id nullable (MySQL allows multiple NULLs in UNIQUE columns)
    op.alter_column(
        "chorus_calls",
        "chorus_call_id",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "chorus_calls",
        "chorus_call_id",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.drop_column("chorus_calls", "source_type")
    op.drop_index("ix_account_deal_memory_status", table_name="account_deal_memory")
    op.drop_table("account_deal_memory")
