"""Add account_deal_memory table and chorus_calls.source_type column.

Revision ID: 20260325_000001
Revises: 20260324_000003
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import OperationalError

revision = "20260325_000001"
down_revision = "20260324_000003"
branch_labels = None
depends_on = None


def _safe_add_column(table, col):
    try:
        op.add_column(table, col)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1060:
            raise


def _safe_create_table(name, *args, **kwargs):
    try:
        op.create_table(name, *args, **kwargs)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1050:
            raise


def _safe_create_index(name, table, cols, **kwargs):
    try:
        op.create_index(name, table, cols, **kwargs)
    except OperationalError as e:
        if getattr(e.orig, "args", (None,))[0] != 1061:
            raise


def upgrade() -> None:
    _safe_create_table(
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
    _safe_create_index("ix_account_deal_memory_status", "account_deal_memory", ["status"])

    _safe_add_column(
        "chorus_calls",
        sa.Column("source_type", sa.String(32), nullable=False, server_default="chorus"),
    )
    # Make chorus_call_id nullable — wrap in try/except since MODIFY may fail if already nullable
    try:
        op.alter_column(
            "chorus_calls",
            "chorus_call_id",
            existing_type=sa.String(255),
            nullable=True,
        )
    except OperationalError:
        pass


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
