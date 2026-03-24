"""Add user_templates and chat_messages tables

Revision ID: 20260320_000001
Revises: 20260316_000004
Create Date: 2026-03-20
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "20260320_000001"
down_revision = "20260316_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("section_key", sa.String(64), nullable=False),
        sa.Column("template_name", sa.String(128), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_email", "section_key", name="uq_user_section"),
    )
    op.create_index("ix_user_templates_section_key", "user_templates", ["section_key"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_chat_messages_user_created",
        "chat_messages",
        ["user_email", "created_at"],
    )

    # Seed default templates
    _seed_defaults()


def _seed_defaults() -> None:
    templates = [
        (
            "pre_call",
            "Pre-Call Intel (Default)",
            (
                "I'm preparing for a call with {prospect_name} at {account} ({website}).\n\n"
                "Please provide:\n"
                "1. Company overview and recent news for {account}\n"
                "2. LinkedIn background on {prospect_name}: {prospect_linkedin}\n"
                "3. Technology stack signals (database, infrastructure)\n"
                "4. Funding, headcount, and growth trajectory\n"
                "5. Likely pain points relevant to TiDB"
            ),
        ),
        (
            "post_call",
            "Post-Call Analysis (Default)",
            (
                "I just completed a call with {account}. Here are the call details:\n\n"
                "{call_context}\n\n"
                "Please analyze and produce:\n"
                "1. **Call Summary** — key topics discussed, decisions made\n"
                "2. **Next Steps** — agreed actions with owners (Rep, SE, Prospect)\n"
                "3. **Action Items** — broken out per person: Rep / SE / {account} contact\n"
                "4. **MEDDPICC Analysis** — for each element (Metrics, Economic Buyer, Decision Criteria,"
                " Decision Process, Paper Process, Implicate Pain, Champion, Competition):"
                " what was established vs. what is missing\n"
                "5. **Qualification Assessment** — is this deal actually qualified?"
                " What are the top 3 gaps to close?"
            ),
        ),
        (
            "follow_up",
            "Follow-Up Email (Default)",
            (
                "FOLLOW-UP EMAIL REQUEST\n\n"
                "Account: {account}\n"
                "To: {email_to}\n"
                "CC: {email_cc}\n"
                "Tone: {email_tone}\n\n"
                "--- CALL RECORD ---\n"
                "{call_context}\n\n"
                "--- ADDITIONAL NOTES ---\n"
                "{call_notes}\n\n"
                "--- TASK ---\n"
                "Write a specific, deal-advancing follow-up email using the call record, "
                "additional notes, and any retrieved call evidence below. "
                "Do not write a generic email — every sentence should be specific to this account and this call."
            ),
        ),
        (
            "tal",
            "Market Research / TAL (Default)",
            (
                "TARGET ACCOUNT LIST REQUEST\n\n"
                "Reference account (ICP anchor): {account}\n"
                "Territory / Regions: {regions}\n"
                "Industry vertical: {industry}\n"
                "Revenue range: ${revenue_min}M – ${revenue_max}M\n"
                "Top N requested: {top_n}\n"
                "Additional context: {context}\n\n"
                "Return the top {top_n} accounts. For each: account name, ICP score rationale, "
                "top signal (with source), recommended entry point (role + angle), and suggested first action."
            ),
        ),
        (
            "se_poc_plan",
            "SE: POC Plan (Default)",
            (
                "Create a technical POC evaluation roadmap for {account}.\n"
                "Offering: {target_offering}\n"
                "Call context: {call_context}\n\n"
                "Include: POC objectives, success criteria, technical requirements,"
                " 4-week milestone plan, resources needed, risk factors."
            ),
        ),
        (
            "se_arch_fit",
            "SE: Architecture Fit (Default)",
            (
                "Analyze TiDB architecture fit for {account}.\n"
                "Call context: {call_context}\n\n"
                "Cover: current database signals, scalability pain, MySQL/Oracle compatibility needs,"
                " HTAP potential, migration complexity, TiDB placement recommendation."
            ),
        ),
        (
            "se_competitor",
            "SE: Competitor Coach (Default)",
            (
                "Competitor coaching for {account} — primary competitor: {competitor}.\n"
                "Call context: {call_context}\n\n"
                "Provide: competitive positioning vs {competitor}, top 5 objections and TiDB responses,"
                " where TiDB wins and where to be careful, recommended proof points."
            ),
        ),
    ]

    for section_key, template_name, content in templates:
        row_id = str(uuid.uuid4())
        # Escape single quotes in content for safe SQL embedding
        safe_content = content.replace("'", "''")
        safe_name = template_name.replace("'", "''")
        op.execute(
            text(
                f"INSERT INTO user_templates (id, user_email, section_key, template_name, content, is_default)"
                f" VALUES ('{row_id}', 'system', '{section_key}', '{safe_name}', '{safe_content}', TRUE)"
            )
        )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("user_templates")
