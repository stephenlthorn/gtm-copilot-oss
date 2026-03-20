"""TiDB compatibility - vector indexes and type adjustments

Revision ID: 20260316_000004
Revises: 20260316_000003
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_000004"
down_revision = "20260316_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        # TiDB vector index uses HNSW
        try:
            op.execute(
                "ALTER TABLE kb_chunks ADD VECTOR INDEX idx_kb_chunks_embedding "
                "((VEC_COSINE_DISTANCE(embedding))) "
                "USING HNSW COMMENT 'tidb_vector_index'"
            )
        except Exception:
            pass  # Index may already exist or column may not support it yet

        try:
            op.execute(
                "ALTER TABLE ai_feedback ADD VECTOR INDEX idx_ai_feedback_embedding "
                "((VEC_COSINE_DISTANCE(embedding))) "
                "USING HNSW COMMENT 'tidb_vector_index'"
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        try:
            op.execute("ALTER TABLE kb_chunks DROP INDEX idx_kb_chunks_embedding")
        except Exception:
            pass
        try:
            op.execute("ALTER TABLE ai_feedback DROP INDEX idx_ai_feedback_embedding")
        except Exception:
            pass
