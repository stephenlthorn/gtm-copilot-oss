from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromptRegistry(Base):
    __tablename__ = "prompt_registry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_content: Mapped[str] = mapped_column(Text, nullable=False)
    current_content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("prompt_registry.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str] = mapped_column(String(255), nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptUserOverride(Base):
    __tablename__ = "prompt_user_overrides"
    __table_args__ = (UniqueConstraint("prompt_id", "user_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("prompt_registry.id"), nullable=False
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
