"""add gtm module storage and kb config fields

Revision ID: 20260301_000004
Revises: 20260227_000003
Create Date: 2026-03-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260301_000004"
down_revision = "20260227_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        from sqlalchemy.dialects.postgresql import UUID, JSONB
        uuid_type = UUID(as_uuid=True)
        json_type = JSONB(astext_type=sa.Text())
        def json_default(v): return sa.text(f"'{v}'::jsonb")
        def json_col(v): return {"nullable": False, "server_default": json_default(v)}
    else:
        uuid_type = sa.String(36)
        json_type = sa.JSON()
        # TiDB/MySQL: ALTER TABLE ADD COLUMN rejects expression defaults (error 1674).
        # Use nullable=True with no server_default; application supplies values.
        def json_default(v): return None
        def json_col(v): return {"nullable": True}

    op.add_column("kb_config", sa.Column("se_poc_kit_url", sa.Text(), nullable=True))
    # TiDB: ALTER TABLE ADD COLUMN rejects expression defaults (error 1674); use nullable.
    op.add_column("kb_config", sa.Column("feature_flags_json", json_type, **json_col("{}")))

    op.create_table(
        "gtm_module_runs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("module_name", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("input", json_type, **json_col("{}")),
        sa.Column("retrieval", json_type, **json_col("{}")),
        sa.Column("output", json_type, **json_col("{}")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_module_runs_module_name", "gtm_module_runs", ["module_name"])
    op.create_index("ix_gtm_module_runs_actor", "gtm_module_runs", ["actor"])
    op.create_index("ix_gtm_module_runs_module_created", "gtm_module_runs", ["module_name", "created_at"])
    op.create_index("ix_gtm_module_runs_actor_created", "gtm_module_runs", ["actor", "created_at"])

    op.create_table(
        "gtm_account_profiles",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("territory", sa.String(length=128), nullable=True),
        sa.Column("segment", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("owner_email", sa.String(length=255), nullable=True),
        sa.Column("se_email", sa.String(length=255), nullable=True),
        sa.Column("metadata", json_type, **json_col("{}")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_account_profiles_account", "gtm_account_profiles", ["account"])

    op.create_table(
        "gtm_risk_signals",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_email", sa.String(length=255), nullable=True),
        sa.Column("source_call_id", sa.String(length=255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("metadata", json_type, **json_col("{}")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_risk_signals_account", "gtm_risk_signals", ["account"])
    op.create_index("ix_gtm_risk_signals_source_call_id", "gtm_risk_signals", ["source_call_id"])
    op.create_index("ix_gtm_risk_signals_severity", "gtm_risk_signals", ["severity"])
    op.create_index("ix_gtm_risk_signals_account_created", "gtm_risk_signals", ["account", "created_at"])

    op.create_table(
        "gtm_poc_plans",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=False),
        sa.Column("readiness_summary", sa.Text(), nullable=False),
        sa.Column("plan_json", json_type, **json_col("{}")),
        sa.Column("poc_kit_url", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_poc_plans_account", "gtm_poc_plans", ["account"])
    op.create_index("ix_gtm_poc_plans_status", "gtm_poc_plans", ["status"])
    op.create_index("ix_gtm_poc_plans_account_created", "gtm_poc_plans", ["account", "created_at"])

    op.create_table(
        "gtm_generated_assets",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("module_name", sa.String(length=128), nullable=False),
        sa.Column("asset_type", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", json_type, **json_col("{}")),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_generated_assets_account", "gtm_generated_assets", ["account"])
    op.create_index("ix_gtm_generated_assets_module", "gtm_generated_assets", ["module_name"])
    op.create_index("ix_gtm_generated_assets_content_hash", "gtm_generated_assets", ["content_hash"])
    op.create_index("ix_gtm_generated_assets_account_created", "gtm_generated_assets", ["account", "created_at"])

    op.create_table(
        "gtm_trend_insights",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("vertical", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("top_signals", json_type, **json_col("[]")),
        sa.Column("recommended_plays", json_type, **json_col("[]")),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_gtm_trend_insights_region", "gtm_trend_insights", ["region"])
    op.create_index("ix_gtm_trend_insights_vertical", "gtm_trend_insights", ["vertical"])
    op.create_index("ix_gtm_trend_insights_created", "gtm_trend_insights", ["created_at"])
    op.create_index("ix_gtm_trend_insights_region_vertical", "gtm_trend_insights", ["region", "vertical"])


def downgrade() -> None:
    op.drop_index("ix_gtm_trend_insights_region_vertical", table_name="gtm_trend_insights")
    op.drop_index("ix_gtm_trend_insights_created", table_name="gtm_trend_insights")
    op.drop_index("ix_gtm_trend_insights_vertical", table_name="gtm_trend_insights")
    op.drop_index("ix_gtm_trend_insights_region", table_name="gtm_trend_insights")
    op.drop_table("gtm_trend_insights")

    op.drop_index("ix_gtm_generated_assets_account_created", table_name="gtm_generated_assets")
    op.drop_index("ix_gtm_generated_assets_content_hash", table_name="gtm_generated_assets")
    op.drop_index("ix_gtm_generated_assets_module", table_name="gtm_generated_assets")
    op.drop_index("ix_gtm_generated_assets_account", table_name="gtm_generated_assets")
    op.drop_table("gtm_generated_assets")

    op.drop_index("ix_gtm_poc_plans_account_created", table_name="gtm_poc_plans")
    op.drop_index("ix_gtm_poc_plans_status", table_name="gtm_poc_plans")
    op.drop_index("ix_gtm_poc_plans_account", table_name="gtm_poc_plans")
    op.drop_table("gtm_poc_plans")

    op.drop_index("ix_gtm_risk_signals_account_created", table_name="gtm_risk_signals")
    op.drop_index("ix_gtm_risk_signals_severity", table_name="gtm_risk_signals")
    op.drop_index("ix_gtm_risk_signals_source_call_id", table_name="gtm_risk_signals")
    op.drop_index("ix_gtm_risk_signals_account", table_name="gtm_risk_signals")
    op.drop_table("gtm_risk_signals")

    op.drop_index("ix_gtm_account_profiles_account", table_name="gtm_account_profiles")
    op.drop_table("gtm_account_profiles")

    op.drop_index("ix_gtm_module_runs_actor_created", table_name="gtm_module_runs")
    op.drop_index("ix_gtm_module_runs_module_created", table_name="gtm_module_runs")
    op.drop_index("ix_gtm_module_runs_actor", table_name="gtm_module_runs")
    op.drop_index("ix_gtm_module_runs_module_name", table_name="gtm_module_runs")
    op.drop_table("gtm_module_runs")

    op.drop_column("kb_config", "feature_flags_json")
    op.drop_column("kb_config", "se_poc_kit_url")
