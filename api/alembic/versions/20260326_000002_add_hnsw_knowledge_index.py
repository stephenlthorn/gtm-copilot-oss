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
    # The column was created as JSON in the original migration.
    # TiDB requires VECTOR(N) column type before a VECTOR INDEX can be added.
    op.execute(
        "ALTER TABLE knowledge_index MODIFY COLUMN embedding VECTOR(1536);"
    )
    # TiDB-specific HNSW index on the embedding column using cosine distance.
    # This is raw DDL — SQLAlchemy has no ORM equivalent for TiDB vector indexes.
    op.execute(
        "ALTER TABLE knowledge_index "
        "ADD VECTOR INDEX idx_ki_embedding "
        "((VEC_COSINE_DISTANCE(embedding))) "
        "USING HNSW;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_index DROP INDEX idx_ki_embedding;")
    op.execute("ALTER TABLE knowledge_index MODIFY COLUMN embedding JSON;")
