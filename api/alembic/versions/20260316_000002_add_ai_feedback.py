"""Add ai_feedback table for user feedback and RAG injection.

Revision ID: 20260316_000002
Revises: 20260316_000001
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260316_000002"
down_revision = "20260316_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("original_response", sa.Text, nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("correction", sa.Text, nullable=True),
        sa.Column("embedding", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ai_feedback_user_email", "ai_feedback", ["user_email"])
    op.create_index("ix_ai_feedback_mode", "ai_feedback", ["mode"])


def downgrade() -> None:
    op.drop_index("ix_ai_feedback_mode", table_name="ai_feedback")
    op.drop_index("ix_ai_feedback_user_email", table_name="ai_feedback")
    op.drop_table("ai_feedback")
