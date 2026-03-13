"""add gtm copilot v2 models

Revision ID: 20260312_000006
Revises: 20260302_000005
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260312_000006"
down_revision = "20260302_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("google_id", sa.String(128), unique=True, nullable=False),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="sales_rep"),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("openai_api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("connected_accounts", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # --- accounts ---
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(256), nullable=True),
        sa.Column("crm_source", sa.String(16), server_default="salesforce"),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("industry", sa.String(256), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("revenue_range", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_accounts_org_id", "accounts", ["org_id"])
    op.create_index("idx_external", "accounts", ["external_id", "crm_source"])

    # --- deals ---
    op.create_table(
        "deals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(256), nullable=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("stage", sa.String(128), nullable=True),
        sa.Column("amount", sa.DECIMAL(15, 2), nullable=True),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(8), server_default="open"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_deals_account_id", "deals", ["account_id"])
    op.create_index("ix_deals_owner_user_id", "deals", ["owner_user_id"])
    op.create_index("idx_org_status", "deals", ["org_id", "status"])

    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(256), nullable=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("linkedin_url", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_contacts_account_id", "contacts", ["account_id"])
    op.create_index("ix_contacts_org_id", "contacts", ["org_id"])

    # --- source_registry ---
    op.create_table(
        "source_registry",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("scope", sa.String(16), server_default="global"),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true" if is_pg else "1")),
    )
    op.create_index("ix_source_registry_account_id", "source_registry", ["account_id"])
    op.create_index("idx_org_active", "source_registry", ["org_id", "active"])

    # --- system_config ---
    op.create_table(
        "system_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("config_key", sa.String(128), unique=True, nullable=False),
        sa.Column("config_value_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("config_value_plain", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_org_key", "system_config", ["org_id", "config_key"])

    # --- api_usage_log ---
    op.create_table(
        "api_usage_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.DECIMAL(10, 6), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_org_source", "api_usage_log", ["org_id", "source", "created_at"])
    op.create_index("idx_created", "api_usage_log", ["created_at"])

    # --- competitor_intel ---
    op.create_table(
        "competitor_intel",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("competitor_name", sa.String(256), nullable=False),
        sa.Column("intel_type", sa.String(32), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("is_notable", sa.Boolean(), server_default=sa.text("false" if is_pg else "0")),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_org_competitor", "competitor_intel", ["org_id", "competitor_name", "created_at"])
    op.create_index("idx_notable", "competitor_intel", ["org_id", "is_notable", "created_at"])

    # --- tracked_competitors ---
    op.create_table(
        "tracked_competitors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("monitoring_config", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true" if is_pg else "1")),
    )
    op.create_index("idx_org_active_comp", "tracked_competitors", ["org_id", "active"])

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_account_id", "conversations", ["account_id"])

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("conversation_id", sa.BigInteger(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_results", sa.JSON(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_conversation", "messages", ["conversation_id", "created_at"])

    # --- research_reports ---
    op.create_table(
        "research_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("report_type", sa.String(16), nullable=False),
        sa.Column("meeting_id", sa.String(256), nullable=True),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("raw_sources", sa.JSON(), nullable=True),
        sa.Column("follow_up_email", sa.Text(), nullable=True),
        sa.Column("generated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_research_reports_account_id", "research_reports", ["account_id"])
    op.create_index("ix_research_reports_meeting_id", "research_reports", ["meeting_id"])
    op.create_index("idx_org_type", "research_reports", ["org_id", "report_type", "status"])

    # --- ai_refinements ---
    op.create_table(
        "ai_refinements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("output_type", sa.String(64), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("context_filter", sa.JSON(), nullable=True),
        sa.Column("scope", sa.String(16), server_default="personal"),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true" if is_pg else "1")),
        sa.Column("effectiveness", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_user_type", "ai_refinements", ["user_id", "output_type"])
    op.create_index("idx_scope", "ai_refinements", ["scope", "output_type"])

    # --- knowledge_index ---
    op.create_table(
        "knowledge_index",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(512), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(64), server_default="text-embedding-3-small"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("idx_source", "knowledge_index", ["source_type", "org_id"])

    # --- sync_status ---
    op.create_table(
        "sync_status",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("docs_indexed", sa.Integer(), server_default="0"),
        sa.Column("chunks_indexed", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(16), server_default="idle"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("idx_source_org", "sync_status", ["source_type", "org_id"], unique=True)

    # --- notification_preferences ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true" if is_pg else "1")),
        sa.Column("timing", sa.String(64), nullable=True),
        sa.Column("channel", sa.String(128), nullable=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.create_index("idx_user_notif", "notification_preferences", ["user_id", "notification_type"], unique=True)


def downgrade() -> None:
    tables = [
        "notification_preferences",
        "sync_status",
        "knowledge_index",
        "ai_refinements",
        "research_reports",
        "messages",
        "conversations",
        "tracked_competitors",
        "competitor_intel",
        "api_usage_log",
        "system_config",
        "source_registry",
        "contacts",
        "deals",
        "accounts",
        "users",
    ]
    for table in tables:
        op.drop_table(table)
