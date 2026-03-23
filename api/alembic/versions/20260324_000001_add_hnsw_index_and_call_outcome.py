"""Add call_outcome column to chorus_calls and HNSW index to kb_chunks.

Revision ID: 20260324_000001
Revises: 20260323_000002
Create Date: 2026-03-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260324_000001"
down_revision = "20260323_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # call_outcome column — all dialects
    op.add_column("chorus_calls", sa.Column("call_outcome", sa.String(64), nullable=True))

    # HNSW vector index — TiDB only
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        try:
            op.execute(
                "ALTER TABLE kb_chunks "
                "ADD VECTOR INDEX idx_kb_chunks_embedding_hnsw "
                "((VEC_COSINE_DISTANCE(embedding))) "
                "USING HNSW COMMENT 'tidb_vector_index'"
            )
        except Exception:
            pass  # Swallows duplicate-index and transient errors; verify with SHOW INDEXES


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        try:
            op.execute("ALTER TABLE kb_chunks DROP INDEX idx_kb_chunks_embedding_hnsw")
        except Exception:
            pass
    op.drop_column("chorus_calls", "call_outcome")
