from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import (
    Account,
    AIRefinement,
    Contact,
    ReportStatus,
    ReportType,
    ResearchReport,
    User,
)
from app.services.llm_provider.openai_provider import OpenAIProvider
from app.services.research.refinement_service import RefinementService

logger = logging.getLogger(__name__)

_PRECALL_SYSTEM_PROMPT = """\
You are a world-class pre-call research analyst for enterprise B2B sales.
Generate a structured 7-section pre-call research report.

Sections:
1. Prospect Information – Name, role/title, time at company, relevant previous role
2. Company Context – Employee count, revenue, industry, product/service, key competitors
3. Current Architecture Hypothesis – Databases, apps/microservices, cloud/infrastructure
4. Pain Hypothesis – At least 2 potential pains with evidence
5. Relevant TiDB Value Propositions – Pain-to-value-prop matching
6. Meeting Goal – Desired outcome of this meeting
7. Meeting Flow Agreement – Who does what, time allocation

Respond with valid JSON:
{
  "sections": {
    "prospect_information": {"name": "", "title": "", "time_at_company": "", "previous_role": ""},
    "company_context": {"employee_count": null, "revenue": "", "industry": "", "product_service": "", "competitors": []},
    "architecture_hypothesis": {"databases": [], "apps_microservices": "", "cloud_infrastructure": ""},
    "pain_hypothesis": [{"pain": "", "evidence": ""}],
    "tidb_value_propositions": [{"pain": "", "value_prop": ""}],
    "meeting_goal": "",
    "meeting_flow": {"agenda": [], "time_allocation": {}}
  }
}

Use all available source data to fill in details. Where data is unavailable,
make reasonable inferences and mark them as hypotheses.
"""


class PreCallReportGenerator:
    """Generates a 7-section pre-call research report using LLM synthesis."""

    def __init__(self, db: Session, llm: OpenAIProvider | None = None) -> None:
        self._db = db
        settings = get_settings()
        self._llm = llm or OpenAIProvider(
            api_key=settings.openai_api_key or "",
            default_model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
        self._refinement_service = RefinementService(db)

    async def generate(
        self,
        sources_data: dict[str, Any],
        account: Account,
        contact: Contact | None,
        user: User,
        org_id: int,
    ) -> ResearchReport:
        """Build the 7-section report from source data and store it."""
        refinements = self._refinement_service.get_refinements(
            user_id=user.id, output_type="pre_call", org_id=org_id
        )
        refinement_prompt = self._refinement_service.format_refinements_prompt(refinements)

        system_prompt = _PRECALL_SYSTEM_PROMPT
        if refinement_prompt:
            system_prompt += f"\n\nAdditional coaching instructions:\n{refinement_prompt}"

        user_content = self._build_user_prompt(sources_data, account, contact)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await self._llm.chat(messages)
            sections = json.loads(response.content)
        except Exception:
            logger.exception("Pre-call report generation failed for account %s", account.name)
            sections = {"error": "Report generation failed", "raw_response": ""}

        report = ResearchReport(
            account_id=account.id,
            contact_id=contact.id if contact else None,
            report_type=ReportType.pre_call,
            status=ReportStatus.ready,
            sections=sections.get("sections", sections),
            raw_sources=self._sanitize_sources(sources_data),
            generated_by_user_id=user.id,
            org_id=org_id,
        )
        self._db.add(report)
        self._db.commit()
        self._db.refresh(report)
        return report

    def _build_user_prompt(
        self,
        sources_data: dict[str, Any],
        account: Account,
        contact: Contact | None,
    ) -> str:
        parts: list[str] = [
            f"Account: {account.name}",
            f"Industry: {account.industry or 'Unknown'}",
            f"Website: {account.website or 'Unknown'}",
            f"Employee Count: {account.employee_count or 'Unknown'}",
        ]
        if contact:
            parts.extend([
                f"\nContact: {contact.name or 'Unknown'}",
                f"Title: {contact.title or 'Unknown'}",
                f"Email: {contact.email or 'Unknown'}",
                f"LinkedIn: {contact.linkedin_url or 'N/A'}",
            ])
        parts.append("\n--- Source Data ---")
        for source_name, source_result in sources_data.items():
            if hasattr(source_result, "data"):
                parts.append(f"\n[{source_name}]: {json.dumps(source_result.data, default=str)[:3000]}")
            elif isinstance(source_result, dict):
                parts.append(f"\n[{source_name}]: {json.dumps(source_result, default=str)[:3000]}")
        return "\n".join(parts)

    @staticmethod
    def _sanitize_sources(sources_data: dict[str, Any]) -> dict[str, Any]:
        """Convert SourceResult objects to serializable dicts for storage."""
        sanitized: dict[str, Any] = {}
        for key, val in sources_data.items():
            if hasattr(val, "status"):
                sanitized[key] = {
                    "status": val.status,
                    "data": val.data if hasattr(val, "data") else {},
                    "error": val.error if hasattr(val, "error") else None,
                }
            else:
                sanitized[key] = val
        return sanitized
