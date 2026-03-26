from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, JSON, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DEFAULT_EMBEDDING_DIMENSIONS
from app.db.base import Base
from app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride  # noqa: F401
from app.db.tidb_vector import TiDBVector

UUID_TYPE = Uuid(as_uuid=True)
JSON_TYPE = JSON
# TiDB Cloud Serverless is the only supported vector backend.
# SQLite is kept for local unit tests (stores vectors as JSON text).
VECTOR_TYPE = (
    TiDBVector(DEFAULT_EMBEDDING_DIMENSIONS)
    .with_variant(JSON, "sqlite")
)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class SourceType(str, enum.Enum):
    GOOGLE_DRIVE = "google_drive"
    FEISHU = "feishu"
    CHORUS = "chorus"
    OFFICIAL_DOCS_ONLINE = "official_docs_online"
    MEMORY = "memory"


class SyncSourceType(str, enum.Enum):
    feishu = "feishu"
    google_drive = "google_drive"
    chorus = "chorus"
    tidb_docs = "tidb_docs"
    github = "github"


class SyncStatusEnum(str, enum.Enum):
    idle = "idle"
    syncing = "syncing"
    error = "error"


class MessageMode(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    BLOCKED = "blocked"


class MessageChannel(str, enum.Enum):
    EMAIL = "email"
    SLACK = "slack"


class AuditStatus(str, enum.Enum):
    OK = "ok"
    ERROR = "error"


def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class KBDocument(Base):
    __tablename__ = "kb_documents"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_document_source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", values_callable=_enum_values), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    modified_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[str | None] = mapped_column(String(255))
    path: Mapped[str | None] = mapped_column(String(1024))
    permissions_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    tags: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chunks: Mapped[list[KBChunk]] = relationship("KBChunk", back_populates="document", cascade="all, delete-orphan")


class KBChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
        Index("ix_kb_chunks_document_id", "document_id"),
        Index("ix_kb_chunks_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR_TYPE, nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document: Mapped[KBDocument] = relationship("KBDocument", back_populates="chunks")


class SyncStatus(Base):
    __tablename__ = "sync_status"
    __table_args__ = (Index("idx_source_org", "source_type", "org_id", unique=True),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    org_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    docs_indexed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="idle", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class KnowledgeIndex(Base):
    __tablename__ = "knowledge_index"
    __table_args__ = (Index("idx_source", "source_type", "org_id"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(String(512))
    chunk_text: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[dict | None] = mapped_column(JSON_TYPE)
    embedding_model: Mapped[str | None] = mapped_column(String(64), server_default="text-embedding-3-small")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON_TYPE)
    org_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now())


class ChorusCall(Base):
    __tablename__ = "chorus_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chorus_call_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="chorus", server_default="chorus")
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    opportunity: Mapped[str | None] = mapped_column(String(512))
    stage: Mapped[str | None] = mapped_column(String(255))
    rep_email: Mapped[str] = mapped_column(String(255), nullable=False)
    se_email: Mapped[str | None] = mapped_column(String(255))
    call_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    participants: Mapped[list[dict]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    engagement_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="call", index=True)
    meeting_summary: Mapped[str | None] = mapped_column(Text)
    action_items: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    recording_url: Mapped[str | None] = mapped_column(Text)
    transcript_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("source_type", "chorus")
        super().__init__(**kwargs)


class CallArtifact(Base):
    __tablename__ = "call_artifacts"
    __table_args__ = (Index("ix_call_artifacts_chorus_call_id", "chorus_call_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chorus_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    objections: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    competitors_mentioned: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    next_steps: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    recommended_collateral: Mapped[list[dict]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    model_info: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    mode: Mapped[MessageMode] = mapped_column(
        Enum(MessageMode, name="message_mode", values_callable=_enum_values), nullable=False, index=True
    )
    channel: Mapped[MessageChannel] = mapped_column(
        Enum(MessageChannel, name="message_channel", values_callable=_enum_values), nullable=False
    )
    to_recipients: Mapped[list[str]] = mapped_column("to", JSON_TYPE, default=list, nullable=False)
    cc_recipients: Mapped[list[str]] = mapped_column("cc", JSON_TYPE, default=list, nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    reason_blocked: Mapped[str | None] = mapped_column(Text)
    chorus_call_id: Mapped[str | None] = mapped_column(String(255), index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, ForeignKey("call_artifacts.id", ondelete="SET NULL"), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    input_json: Mapped[dict] = mapped_column("input", JSON_TYPE, default=dict, nullable=False)
    retrieval_json: Mapped[dict] = mapped_column("retrieval", JSON_TYPE, default=dict, nullable=False)
    output_json: Mapped[dict] = mapped_column("output", JSON_TYPE, default=dict, nullable=False)
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status", values_callable=_enum_values), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text)

class KBConfig(Base):
    __tablename__ = "kb_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    google_drive_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    google_drive_folder_ids: Mapped[str | None] = mapped_column(Text)
    feishu_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    feishu_root_tokens: Mapped[str | None] = mapped_column(Text)
    feishu_oauth_enabled: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
    feishu_folder_token: Mapped[str | None] = mapped_column(String(255))
    feishu_app_id: Mapped[str | None] = mapped_column(String(255))
    feishu_app_secret: Mapped[str | None] = mapped_column(String(255))
    chorus_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-5.3-codex", nullable=False, server_default="gpt-5.3-codex")
    reasoning_effort: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False, server_default="medium"
    )
    web_search_enabled: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
    code_interpreter_enabled: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
    persona_name: Mapped[str] = mapped_column(
        String(64),
        default="sales_representative",
        nullable=False,
        server_default="sales_representative",
    )
    persona_prompt: Mapped[str | None] = mapped_column(Text)
    se_poc_kit_url: Mapped[str | None] = mapped_column(Text)
    feature_flags_json: Mapped[dict] = mapped_column(
        JSON_TYPE,
        default=dict,
        nullable=False,
        server_default="{}",
    )
    source_profiles_json: Mapped[dict] = mapped_column(
        JSON_TYPE,
        default=dict,
        nullable=False,
        server_default="{}",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GoogleDriveUserCredential(Base):
    __tablename__ = "google_drive_user_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FeishuUserCredential(Base):
    __tablename__ = "feishu_user_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GTMModuleRun(Base):
    __tablename__ = "gtm_module_runs"
    __table_args__ = (
        Index("ix_gtm_module_runs_module_created", "module_name", "created_at"),
        Index("ix_gtm_module_runs_actor_created", "actor", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    module_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    input_json: Mapped[dict] = mapped_column("input", JSON_TYPE, default=dict, nullable=False)
    retrieval_json: Mapped[dict] = mapped_column(
        "retrieval",
        JSON_TYPE,
        default=dict,
        nullable=False,
    )
    output_json: Mapped[dict] = mapped_column("output", JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=AuditStatus.OK.value)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GTMAccountProfile(Base):
    __tablename__ = "gtm_account_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    territory: Mapped[str | None] = mapped_column(String(128))
    segment: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    owner_email: Mapped[str | None] = mapped_column(String(255))
    se_email: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GTMRiskSignal(Base):
    __tablename__ = "gtm_risk_signals"
    __table_args__ = (
        Index("ix_gtm_risk_signals_account_created", "account", "created_at"),
        Index("ix_gtm_risk_signals_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_email: Mapped[str | None] = mapped_column(String(255))
    source_call_id: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GTMPOCPlan(Base):
    __tablename__ = "gtm_poc_plans"
    __table_args__ = (
        Index("ix_gtm_poc_plans_account_created", "account", "created_at"),
        Index("ix_gtm_poc_plans_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    readiness_summary: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    poc_kit_url: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GTMGeneratedAsset(Base):
    __tablename__ = "gtm_generated_assets"
    __table_args__ = (
        Index("ix_gtm_generated_assets_account_created", "account", "created_at"),
        Index("ix_gtm_generated_assets_module", "module_name"),
        Index("ix_gtm_generated_assets_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GTMTrendInsight(Base):
    __tablename__ = "gtm_trend_insights"
    __table_args__ = (
        Index("ix_gtm_trend_insights_created", "created_at"),
        Index("ix_gtm_trend_insights_region_vertical", "region", "vertical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    region: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    vertical: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    top_signals: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    recommended_plays: Mapped[list[str]] = mapped_column(
        JSON_TYPE,
        default=list,
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_email: Mapped[str] = mapped_column(String(255), primary_key=True)
    llm_model: Mapped[str | None] = mapped_column(String(64))
    reasoning_effort: Mapped[str | None] = mapped_column(String(16))
    retrieval_top_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intel_brief_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true())
    intel_brief_summarizer_model: Mapped[str | None] = mapped_column(String(64), nullable=True, server_default="gpt-5.4-mini")
    intel_brief_summarizer_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    intel_brief_synthesis_model: Mapped[str | None] = mapped_column(String(64), nullable=True, server_default="gpt-5.4")
    intel_brief_synthesis_effort: Mapped[str] = mapped_column(String(16), nullable=False, server_default="medium")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserTemplate(Base):
    __tablename__ = "user_templates"
    __table_args__ = (UniqueConstraint("user_email", "section_key", name="uq_user_section"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountDealMemory(Base):
    __tablename__ = "account_deal_memory"

    account: Mapped[str] = mapped_column(String(255), primary_key=True)
    deal_stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_new_business: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    meddpicc: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True, default=None)
    key_contacts: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True, default=None)
    tech_stack: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True, default=None)
    open_items: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True, default=None)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    last_call_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    pending_review: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    pending_delta: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("is_new_business", True)
        kwargs.setdefault("status", "active")
        kwargs.setdefault("pending_review", False)
        kwargs.setdefault("call_count", 0)
        super().__init__(**kwargs)
