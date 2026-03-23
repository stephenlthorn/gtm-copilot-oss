from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import UUID_TYPE, VECTOR_TYPE, _uuid


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        Index("ix_ai_feedback_user_email", "user_email"),
        Index("ix_ai_feedback_mode", "mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_response: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    correction: Mapped[str | None] = mapped_column(Text)
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChunkQualitySignal(Base):
    __tablename__ = "chunk_quality_signals"
    __table_args__ = (
        Index("ix_chunk_quality_signals_chunk_id", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("kb_chunks.id", ondelete="CASCADE"), nullable=False)
    signal: Mapped[str] = mapped_column(String(32), nullable=False)  # "cited_positive" | "cited_negative" | "retrieved_unused"
    query_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PromptSuggestion(Base):
    __tablename__ = "prompt_suggestions"
    __table_args__ = (
        Index("ix_prompt_suggestions_mode_category", "mode", "failure_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_category: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "persona" | "builtin"
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    current_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
