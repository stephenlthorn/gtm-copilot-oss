from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import (
    Account,
    Contact,
    ReportStatus,
    ReportType,
    ResearchReport,
    User,
)
from app.services.research.postcall_pipeline import PostCallPipeline
from app.services.research.precall_report import PreCallReportGenerator
from app.services.research.sources import ResearchSourceRunner

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """Main entry point that ties the research pipeline together.

    Coordinates company lookup, source fan-out, and report generation for
    both pre-call and post-call workflows.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()
        self._source_runner = ResearchSourceRunner(db)
        self._precall_generator = PreCallReportGenerator(db)
        self._postcall_pipeline = PostCallPipeline(db)

    async def trigger_precall_research(
        self,
        company_name: str,
        user_id: int,
        org_id: int,
        meeting_id: str | None = None,
        contact_id: int | None = None,
    ) -> ResearchReport:
        """Orchestrate the full pre-call research pipeline.

        Steps:
        1. Create or find account
        2. Create research_report with status='pending'
        3. Update status to 'researching'
        4. Run all sources (fan-out)
        5. Generate 7-section report
        6. Update status to 'ready'
        7. Return report
        """
        user = self._db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        account = self._find_or_create_account(company_name, org_id)

        contact: Contact | None = None
        if contact_id:
            contact = self._db.query(Contact).get(contact_id)

        pending_report = ResearchReport(
            account_id=account.id,
            contact_id=contact.id if contact else None,
            report_type=ReportType.pre_call,
            meeting_id=meeting_id,
            status=ReportStatus.pending,
            sections={},
            generated_by_user_id=user.id,
            org_id=org_id,
        )
        self._db.add(pending_report)
        self._db.commit()
        self._db.refresh(pending_report)

        try:
            pending_report.status = ReportStatus.researching
            self._db.commit()

            sources_data = await self._source_runner.run_all_sources(
                account_name=account.name,
                website=account.website or "",
                org_id=org_id,
                account_id=account.id,
            )

            report = await self._precall_generator.generate(
                sources_data=sources_data,
                account=account,
                contact=contact,
                user=user,
                org_id=org_id,
            )

            self._db.delete(pending_report)
            self._db.commit()

            if meeting_id:
                report.meeting_id = meeting_id
                self._db.commit()
                self._db.refresh(report)

            return report

        except Exception:
            logger.exception("Pre-call research failed for %s", company_name)
            pending_report.status = ReportStatus.error
            pending_report.sections = {"error": "Research pipeline failed"}
            self._db.commit()
            self._db.refresh(pending_report)
            return pending_report

    async def trigger_postcall_research(
        self, chorus_call_id: str, org_id: int
    ) -> ResearchReport:
        """Orchestrate post-call analysis pipeline.

        Delegates to PostCallPipeline for transcript analysis and follow-up
        email generation.
        """
        return await self._postcall_pipeline.process_call(chorus_call_id, org_id)

    def _find_or_create_account(self, company_name: str, org_id: int) -> Account:
        """Find an existing account or create a new one."""
        account = (
            self._db.query(Account)
            .filter(
                Account.name.ilike(f"%{company_name}%"),
                Account.org_id == org_id,
            )
            .first()
        )
        if account:
            return account

        account = Account(
            name=company_name,
            org_id=org_id,
        )
        self._db.add(account)
        self._db.commit()
        self._db.refresh(account)
        return account
