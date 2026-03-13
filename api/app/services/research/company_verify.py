from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services.llm_provider.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompanyVerification:
    name: str
    industry: str
    website: str
    employee_count_estimate: int | None
    confidence: float
    alternatives: list[dict[str, Any]] = field(default_factory=list)


_VERIFY_SYSTEM_PROMPT = (
    "You are a company research assistant. Given a company name, propose the most "
    "likely match with structured details. If the name is ambiguous, provide alternatives. "
    "Respond ONLY with valid JSON matching this schema:\n"
    "{\n"
    '  "name": "Official Company Name",\n'
    '  "industry": "Industry sector",\n'
    '  "website": "https://example.com",\n'
    '  "employee_count_estimate": 1000,\n'
    '  "confidence": 0.95,\n'
    '  "alternatives": [\n'
    '    {"name": "...", "industry": "...", "website": "...", "employee_count_estimate": null, "confidence": 0.3}\n'
    "  ]\n"
    "}"
)


class CompanyVerifyService:
    """Uses an LLM to propose structured company info for user confirmation."""

    def __init__(self, db: Session, llm: OpenAIProvider | None = None) -> None:
        self._db = db
        settings = get_settings()
        self._llm = llm or OpenAIProvider(
            api_key=settings.openai_api_key or "",
            default_model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    async def verify_company(
        self, company_name: str, org_id: int
    ) -> CompanyVerification:
        """Propose company information based on name using LLM reasoning.

        The caller should present these results for user confirmation before
        proceeding with research.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _VERIFY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Company name: {company_name}\n"
                    f"Organization ID: {org_id}\n"
                    "Please identify this company and provide structured details."
                ),
            },
        ]

        try:
            response = await self._llm.chat(messages)
            import json

            parsed = json.loads(response.content)
            return CompanyVerification(
                name=parsed.get("name", company_name),
                industry=parsed.get("industry", "Unknown"),
                website=parsed.get("website", ""),
                employee_count_estimate=parsed.get("employee_count_estimate"),
                confidence=float(parsed.get("confidence", 0.5)),
                alternatives=parsed.get("alternatives", []),
            )
        except Exception:
            logger.exception("Company verification failed for %s", company_name)
            return CompanyVerification(
                name=company_name,
                industry="Unknown",
                website="",
                employee_count_estimate=None,
                confidence=0.0,
                alternatives=[],
            )
