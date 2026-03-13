"""initial schema

Revision ID: 20260218_000001
Revises:
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260218_000001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_type(is_pg: bool):
    """Return UUID column type appropriate for the dialect."""
    if is_pg:
        from sqlalchemy.dialects.postgresql import UUID
        return UUID(as_uuid=True)
    return sa.String(36)


def _json_type(is_pg: bool):
    """Return JSON column type appropriate for the dialect."""
    if is_pg:
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB(astext_type=sa.Text())
    return sa.JSON()


def _json_default(value: str, is_pg: bool):
    """Return a server_default for a JSON column."""
    if is_pg:
        return sa.text(f"'{value}'::jsonb")
    return sa.text(f"'{value}'")


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        from pgvector.sqlalchemy import Vector
        from sqlalchemy.dialects import postgresql

        source_type_enum = postgresql.ENUM("google_drive", "chorus", name="source_type", create_type=False)
        message_mode_enum = postgresql.ENUM("draft", "sent", "blocked", name="message_mode", create_type=False)
        message_channel_enum = postgresql.ENUM("email", "slack", name="message_channel", create_type=False)
        audit_status_enum = postgresql.ENUM("ok", "error", name="audit_status", create_type=False)

        source_type_enum.create(bind, checkfirst=True)
        message_mode_enum.create(bind, checkfirst=True)
        message_channel_enum.create(bind, checkfirst=True)
        audit_status_enum.create(bind, checkfirst=True)

        source_type_type = source_type_enum
        message_mode_type = message_mode_enum
        message_channel_type = message_channel_enum
        audit_status_type = audit_status_enum
        embedding_type = Vector(1536)
    else:
        source_type_type = sa.String(32)
        message_mode_type = sa.String(16)
        message_channel_type = sa.String(16)
        audit_status_type = sa.String(16)
        embedding_type = sa.Text()

    uuid_type = _uuid_type(is_pg)
    json_type = _json_type(is_pg)

    op.create_table(
        "kb_documents",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("source_type", source_type_type, nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("modified_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("permissions_hash", sa.String(length=128), nullable=False),
        sa.Column("tags", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_document_source"),
    )
    op.create_index("ix_kb_documents_source_id", "kb_documents", ["source_id"])
    op.create_index("ix_kb_documents_source_type", "kb_documents", ["source_type"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("metadata", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
    )
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    op.create_index("ix_kb_chunks_content_hash", "kb_chunks", ["content_hash"])
    if is_pg:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_kb_chunks_embedding_ivfflat "
            "ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )

    op.create_table(
        "chorus_calls",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("chorus_call_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("opportunity", sa.String(length=512), nullable=True),
        sa.Column("stage", sa.String(length=255), nullable=True),
        sa.Column("rep_email", sa.String(length=255), nullable=False),
        sa.Column("se_email", sa.String(length=255), nullable=True),
        sa.Column("participants", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("transcript_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_chorus_calls_chorus_call_id", "chorus_calls", ["chorus_call_id"])
    op.create_index("ix_chorus_calls_account", "chorus_calls", ["account"])
    op.create_index("ix_chorus_calls_date", "chorus_calls", ["date"])

    op.create_table(
        "call_artifacts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("chorus_call_id", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("objections", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("competitors_mentioned", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("risks", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("next_steps", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("recommended_collateral", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("follow_up_questions", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("model_info", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_call_artifacts_chorus_call_id", "call_artifacts", ["chorus_call_id"])

    op.create_table(
        "outbound_messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("mode", message_mode_type, nullable=False),
        sa.Column("channel", message_channel_type, nullable=False),
        sa.Column("to", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("cc", json_type, nullable=False, server_default=_json_default("[]", is_pg)),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reason_blocked", sa.Text(), nullable=True),
        sa.Column("chorus_call_id", sa.String(length=255), nullable=True),
        sa.Column("artifact_id", uuid_type, sa.ForeignKey("call_artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_outbound_messages_mode", "outbound_messages", ["mode"])
    op.create_index("ix_outbound_messages_content_hash", "outbound_messages", ["content_hash"])
    op.create_index("ix_outbound_messages_chorus_call_id", "outbound_messages", ["chorus_call_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("input", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("retrieval", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("output", json_type, nullable=False, server_default=_json_default("{}", is_pg)),
        sa.Column("status", audit_status_type, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("outbound_messages")
    op.drop_table("call_artifacts")
    op.drop_table("chorus_calls")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        audit_status = sa.Enum("ok", "error", name="audit_status")
        message_channel = sa.Enum("email", "slack", name="message_channel")
        message_mode = sa.Enum("draft", "sent", "blocked", name="message_mode")
        source_type = sa.Enum("google_drive", "chorus", name="source_type")

        audit_status.drop(bind, checkfirst=True)
        message_channel.drop(bind, checkfirst=True)
        message_mode.drop(bind, checkfirst=True)
        source_type.drop(bind, checkfirst=True)
