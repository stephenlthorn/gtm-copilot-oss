"""Add chunk_quality_signals table for chunk-level feedback tracking.

Revision ID: 20260324_000002
Revises: 20260324_000001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260324_000002"
down_revision = "20260324_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    # UUID column type: String(36) for MySQL/TiDB (matches kb_chunks.id), Text for others
    if dialect == "mysql":
        uuid_col = sa.String(36)
    else:
        uuid_col = sa.Text()

    op.create_table(
        "chunk_quality_signals",
        sa.Column("id", uuid_col, primary_key=True),
        sa.Column("chunk_id", uuid_col, sa.ForeignKey("kb_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal", sa.String(32), nullable=False),
        sa.Column("query_mode", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunk_quality_signals_chunk_id", "chunk_quality_signals", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_chunk_quality_signals_chunk_id", table_name="chunk_quality_signals")
    op.drop_table("chunk_quality_signals")
