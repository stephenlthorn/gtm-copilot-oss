from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON, BigInteger, Boolean, Column, DECIMAL, Date, DateTime, Enum,
    ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint,
    Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DEFAULT_EMBEDDING_DIMENSIONS
from app.db.base import Base

UUID_TYPE = Uuid(as_uuid=True)
JSON_TYPE = JSON
VECTOR_TYPE = (
    Vector(DEFAULT_EMBEDDING_DIMENSIONS)
    .with_variant(JSON, "sqlite")
    .with_variant(JSON, "mysql")
    .with_variant(JSON, "mariadb")
)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class SourceType(str, enum.Enum):
    GOOGLE_DRIVE = "google_drive"
    FEISHU = "feishu"
    CHORUS = "chorus"
    OFFICIAL_DOCS_ONLINE = "official_docs_online"
    MEMORY = "memory"


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


class ChorusCall(Base):
    __tablename__ = "chorus_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chorus_call_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    opportunity: Mapped[str | None] = mapped_column(String(512))
    stage: Mapped[str | None] = mapped_column(String(255))
    rep_email: Mapped[str] = mapped_column(String(255), nullable=False)
    se_email: Mapped[str | None] = mapped_column(String(255))
    participants: Mapped[list[dict]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    recording_url: Mapped[str | None] = mapped_column(Text)
    transcript_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4.1", nullable=False, server_default="gpt-4.1")
    reasoning_effort: Mapped[str | None] = mapped_column(String(20))
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


# ---------------------------------------------------------------------------
# GTM Copilot v2 enums
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    sales_rep = "sales_rep"
    se = "se"
    marketing = "marketing"
    admin = "admin"


class SourceScope(str, enum.Enum):
    global_ = "global"
    account = "account"


class SourceRegistryType(str, enum.Enum):
    builtin = "builtin"
    internal = "internal"
    custom = "custom"


class ReportType(str, enum.Enum):
    pre_call = "pre_call"
    post_call = "post_call"


class ReportStatus(str, enum.Enum):
    pending = "pending"
    researching = "researching"
    ready = "ready"
    error = "error"


class DealStatus(str, enum.Enum):
    open = "open"
    won = "won"
    lost = "lost"


class CRMSource(str, enum.Enum):
    salesforce = "salesforce"
    custom = "custom"


class RefinementScope(str, enum.Enum):
    personal = "personal"
    team = "team"


class APIUsageStatus(str, enum.Enum):
    success = "success"
    error = "error"
    rate_limited = "rate_limited"


class IntelType(str, enum.Enum):
    news = "news"
    product_launch = "product_launch"
    pricing_change = "pricing_change"
    review = "review"
    release = "release"
    other = "other"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class SyncSourceType(str, enum.Enum):
    google_drive = "google_drive"
    feishu = "feishu"
    tidb_docs = "tidb_docs"
    tidb_github = "tidb_github"


class SyncStatusEnum(str, enum.Enum):
    idle = "idle"
    syncing = "syncing"
    error = "error"


# ---------------------------------------------------------------------------
# GTM Copilot v2 models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    google_id = Column(String(128), unique=True, nullable=False)
    email = Column(String(256), nullable=False, index=True)
    name = Column(String(256))
    role = Column(Enum(UserRole), nullable=False, default=UserRole.sales_rep)
    team_id = Column(BigInteger, nullable=True)
    org_id = Column(BigInteger, nullable=False, index=True)
    openai_api_key_encrypted = Column(LargeBinary, nullable=True)
    preferences = Column(JSON, nullable=True)
    connected_accounts = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (Index("idx_external", "external_id", "crm_source"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    external_id = Column(String(256), nullable=True)
    crm_source = Column(Enum(CRMSource), default=CRMSource.salesforce)
    name = Column(String(512), nullable=False)
    industry = Column(String(256))
    website = Column(String(512))
    employee_count = Column(Integer)
    revenue_range = Column(String(64))
    description = Column(Text)
    metadata_ = Column("metadata", JSON)
    org_id = Column(BigInteger, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (Index("idx_org_status", "org_id", "status"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    external_id = Column(String(256))
    account_id = Column(BigInteger, ForeignKey("accounts.id"), nullable=False, index=True)
    name = Column(String(512))
    stage = Column(String(128))
    amount = Column(DECIMAL(15, 2))
    close_date = Column(Date)
    owner_user_id = Column(BigInteger, ForeignKey("users.id"), index=True)
    status = Column(Enum(DealStatus), default=DealStatus.open)
    metadata_ = Column("metadata", JSON)
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    external_id = Column(String(256))
    account_id = Column(BigInteger, ForeignKey("accounts.id"), nullable=False, index=True)
    name = Column(String(256))
    title = Column(String(256))
    email = Column(String(256))
    linkedin_url = Column(String(512))
    metadata_ = Column("metadata", JSON)
    org_id = Column(BigInteger, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SourceRegistry(Base):
    __tablename__ = "source_registry"
    __table_args__ = (Index("idx_org_active", "org_id", "active"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(Enum(SourceRegistryType), nullable=False)
    provider = Column(String(64))
    config = Column(JSON)
    scope = Column(Enum(SourceScope), default=SourceScope.global_)
    account_id = Column(BigInteger, ForeignKey("accounts.id"), nullable=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    org_id = Column(BigInteger, nullable=False)
    active = Column(Boolean, default=True)


class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = (Index("idx_org_key", "org_id", "config_key"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(128), unique=True, nullable=False)
    config_value_encrypted = Column(LargeBinary, nullable=True)
    config_value_plain = Column(JSON, nullable=True)
    org_id = Column(BigInteger, nullable=False)
    updated_by_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APIUsageLog(Base):
    __tablename__ = "api_usage_log"
    __table_args__ = (
        Index("idx_org_source", "org_id", "source", "created_at"),
        Index("idx_created", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False)
    endpoint = Column(String(256))
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    estimated_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    status = Column(Enum(APIUsageStatus), nullable=False)
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompetitorIntel(Base):
    __tablename__ = "competitor_intel"
    __table_args__ = (
        Index("idx_org_competitor", "org_id", "competitor_name", "created_at"),
        Index("idx_notable", "org_id", "is_notable", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    competitor_name = Column(String(256), nullable=False)
    intel_type = Column(Enum(IntelType))
    title = Column(String(512))
    summary = Column(Text)
    source_url = Column(String(512))
    raw_content = Column(Text)
    is_notable = Column(Boolean, default=False)
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrackedCompetitor(Base):
    __tablename__ = "tracked_competitors"
    __table_args__ = (Index("idx_org_active_comp", "org_id", "active"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    website = Column(String(512))
    monitoring_config = Column(JSON)
    org_id = Column(BigInteger, nullable=False)
    active = Column(Boolean, default=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(BigInteger, ForeignKey("accounts.id"), nullable=True, index=True)
    title = Column(String(512))
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("idx_conversation", "conversation_id", "created_at"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text)
    tool_calls = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResearchReport(Base):
    __tablename__ = "research_reports"
    __table_args__ = (Index("idx_org_type", "org_id", "report_type", "status"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(BigInteger, ForeignKey("accounts.id"), nullable=False, index=True)
    contact_id = Column(BigInteger, ForeignKey("contacts.id"), nullable=True)
    report_type = Column(Enum(ReportType), nullable=False)
    meeting_id = Column(String(256), nullable=True, index=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.pending)
    sections = Column(JSON, nullable=False)
    raw_sources = Column(JSON)
    follow_up_email = Column(Text, nullable=True)
    generated_by_user_id = Column(BigInteger, ForeignKey("users.id"))
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIRefinement(Base):
    __tablename__ = "ai_refinements"
    __table_args__ = (
        Index("idx_user_type", "user_id", "output_type"),
        Index("idx_scope", "scope", "output_type"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    output_type = Column(String(64))
    feedback_text = Column(Text)
    context_filter = Column(JSON)
    scope = Column(Enum(RefinementScope), default=RefinementScope.personal)
    active = Column(Boolean, default=True)
    effectiveness = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeIndex(Base):
    __tablename__ = "knowledge_index"
    __table_args__ = (Index("idx_source", "source_type", "org_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(Enum(SyncSourceType), nullable=False)
    source_ref = Column(String(512))
    title = Column(String(512))
    chunk_text = Column(Text)
    chunk_index = Column(Integer)
    embedding = Column(JSON)  # JSON array for TiDB compat; native vector when available
    embedding_model = Column(String(64), default="text-embedding-3-small")
    metadata_ = Column("metadata", JSON)
    org_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncStatus(Base):
    __tablename__ = "sync_status"
    __table_args__ = (Index("idx_source_org", "source_type", "org_id", unique=True),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(Enum(SyncSourceType), nullable=False)
    org_id = Column(BigInteger, nullable=False)
    last_sync_at = Column(DateTime)
    docs_indexed = Column(Integer, default=0)
    chunks_indexed = Column(Integer, default=0)
    status = Column(Enum(SyncStatusEnum), default=SyncStatusEnum.idle)
    error_message = Column(Text)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (Index("idx_user_notif", "user_id", "notification_type", unique=True),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    notification_type = Column(String(64), nullable=False)
    enabled = Column(Boolean, default=True)
    timing = Column(String(64))
    channel = Column(String(128))
    org_id = Column(BigInteger, nullable=False)
