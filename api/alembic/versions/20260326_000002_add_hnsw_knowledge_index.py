"""add HNSW vector index to knowledge_index

Revision ID: 20260326_000002
Revises: 20260326_000001
Create Date: 2026-03-26
"""
import sqlalchemy as sa
from alembic import op

revision = "20260326_000002"
down_revision = "20260326_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Skip entirely if not TiDB/MySQL
    if bind.dialect.name != "mysql":
        return

    # Check table exists
    row = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = 'knowledge_index'"
    )).scalar()
    if not row:
        return  # Table absent; model sync will create it with correct schema

    # Check current embedding column type
    col_row = bind.execute(sa.text(
        "SELECT COLUMN_TYPE FROM information_schema.columns "
        "WHERE table_schema = DATABASE() "
        "AND table_name = 'knowledge_index' "
        "AND column_name = 'embedding'"
    )).fetchone()

    if col_row is None:
        # No embedding column at all — add it
        bind.execute(sa.text("ALTER TABLE knowledge_index ADD COLUMN embedding VECTOR(1536);"))
    elif "vector" not in col_row[0].lower():
        # Still JSON — drop and re-add as VECTOR
        bind.execute(sa.text("ALTER TABLE knowledge_index DROP COLUMN embedding;"))
        bind.execute(sa.text("ALTER TABLE knowledge_index ADD COLUMN embedding VECTOR(1536);"))
    # else: already VECTOR, nothing to do

    # Add HNSW index if not already present
    idx_row = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() "
        "AND table_name = 'knowledge_index' "
        "AND index_name = 'idx_ki_embedding'"
    )).scalar()
    if not idx_row:
        bind.execute(sa.text(
            "ALTER TABLE knowledge_index "
            "ADD VECTOR INDEX idx_ki_embedding "
            "((VEC_COSINE_DISTANCE(embedding))) "
            "USING HNSW "
            "ADD_COLUMNAR_REPLICA_ON_DEMAND;"
        ))


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_index DROP INDEX idx_ki_embedding;")
    op.execute("ALTER TABLE knowledge_index DROP COLUMN embedding;")
    op.execute("ALTER TABLE knowledge_index ADD COLUMN embedding JSON;")
