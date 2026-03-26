"""add HNSW vector index to knowledge_index

Revision ID: 20260326_000002
Revises: 20260326_000001
Create Date: 2026-03-26
"""
from alembic import op

revision = "20260326_000002"
down_revision = "20260326_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TiDB does not support MODIFY COLUMN from JSON to VECTOR.
    # Drop and re-add to get the correct VECTOR(1536) type.
    # Existing embedding values are lost but will be re-indexed on next sync.
    op.execute("ALTER TABLE knowledge_index DROP COLUMN embedding;")
    op.execute("ALTER TABLE knowledge_index ADD COLUMN embedding VECTOR(1536);")
    # TiDB-specific HNSW index using cosine distance.
    op.execute(
        "ALTER TABLE knowledge_index "
        "ADD VECTOR INDEX idx_ki_embedding "
        "((VEC_COSINE_DISTANCE(embedding))) "
        "USING HNSW;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_index DROP INDEX idx_ki_embedding;")
    op.execute("ALTER TABLE knowledge_index DROP COLUMN embedding;")
    op.execute("ALTER TABLE knowledge_index ADD COLUMN embedding JSON;")
