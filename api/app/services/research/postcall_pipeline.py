from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import (
    ChorusCall,
    ReportStatus,
    ReportType,
    ResearchReport,
    User,
)
from app.services.llm_provider.openai_provider import OpenAIProvider
from app.services.research.refinement_service import RefinementService

logger = logging.getLogger(__name__)

_POSTCALL_SYSTEM_PROMPT = """\
You are a post-call analyst for enterprise B2B sales. Given a call transcript,
produce a structured analysis and a follow-up email draft.

Analysis sections:
1. What We Heard – Key points, concerns, and requirements expressed by the prospect
2. What It Means – Interpretation of the prospect's situation, buying signals, risks
3. Next Steps – Concrete action items with owners and timelines

Follow-up email should include:
- Pain summary (what we understood from the call)
- How TiDB helps (mapped to their specific pains)
- Next steps with owners and timeline

Respond with valid JSON:
{
  "analysis": {
    "what_we_heard": [],
    "what_it_means": [],
    "next_steps": [{"action": "", "owner": "", "due": ""}]
  },
  "follow_up_email": {
    "subject": "",
    "body": ""
  }
}
"""


class PostCallPipeline:
    """Processes call transcripts to generate post-call analysis and follow-up emails."""

    def __init__(self, db: Session, llm: OpenAIProvider | None = None) -> None:
        self._db = db
        settings = get_settings()
        self._llm = llm or OpenAIProvider(
            api_key=settings.openai_api_key or "",
            default_model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
        self._refinement_service = RefinementService(db)

    async def process_call(
        self, chorus_call_id: str, org_id: int
    ) -> ResearchReport:
        """Analyze a call transcript and generate post-call report with follow-up email.

        Steps:
        1. Fetch transcript from chorus_calls table
        2. Fetch user's AI refinements for "post_call" output type
        3. LLM analysis: What we heard / What it means / Next steps
        4. Generate follow-up email draft
        5. Store as research_report with report_type='post_call'
        """
        call = (
            self._db.query(ChorusCall)
            .filter_by(chorus_call_id=chorus_call_id)
            .first()
        )
        if not call:
            raise ValueError(f"Chorus call not found: {chorus_call_id}")

        transcript = self._fetch_transcript(call)

        rep_user = self._db.query(User).filter_by(email=call.rep_email).first()
        user_id = rep_user.id if rep_user else None

        refinements = []
        if user_id:
            refinements = self._refinement_service.get_refinements(
                user_id=user_id, output_type="post_call", org_id=org_id
            )
        refinement_prompt = self._refinement_service.format_refinements_prompt(refinements)

        system_prompt = _POSTCALL_SYSTEM_PROMPT
        if refinement_prompt:
            system_prompt += f"\n\nAdditional coaching instructions:\n{refinement_prompt}"

        user_content = (
            f"Account: {call.account}\n"
            f"Opportunity: {call.opportunity or 'N/A'}\n"
            f"Stage: {call.stage or 'N/A'}\n"
            f"Date: {call.date}\n"
            f"Rep: {call.rep_email}\n"
            f"SE: {call.se_email or 'N/A'}\n"
            f"Participants: {json.dumps(call.participants, default=str)}\n\n"
            f"--- Transcript ---\n{transcript}"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await self._llm.chat(messages)
            parsed = json.loads(response.content)
        except Exception:
            logger.exception("Post-call analysis failed for call %s", chorus_call_id)
            parsed = {
                "analysis": {"error": "Analysis failed"},
                "follow_up_email": {"subject": "", "body": ""},
            }

        from app.models.entities import Account

        account = (
            self._db.query(Account)
            .filter(Account.name.ilike(f"%{call.account}%"), Account.org_id == org_id)
            .first()
        )
        account_id = account.id if account else 0

        follow_up_email_text = ""
        if "follow_up_email" in parsed:
            email = parsed["follow_up_email"]
            follow_up_email_text = f"Subject: {email.get('subject', '')}\n\n{email.get('body', '')}"

        report = ResearchReport(
            account_id=account_id,
            report_type=ReportType.post_call,
            status=ReportStatus.ready,
            sections=parsed.get("analysis", parsed),
            raw_sources={"chorus_call_id": chorus_call_id, "transcript_length": len(transcript)},
            follow_up_email=follow_up_email_text or None,
            generated_by_user_id=user_id,
            org_id=org_id,
        )
        self._db.add(report)
        self._db.commit()
        self._db.refresh(report)
        return report

    def _fetch_transcript(self, call: ChorusCall) -> str:
        """Retrieve the transcript text for a call.

        Checks the call_artifacts table first, then falls back to the
        transcript_url if available.
        """
        from app.models.entities import CallArtifact

        artifact = (
            self._db.query(CallArtifact)
            .filter_by(chorus_call_id=call.chorus_call_id)
            .first()
        )
        if artifact and artifact.summary:
            return artifact.summary

        if call.transcript_url:
            return f"[Transcript available at: {call.transcript_url}]"

        return "[No transcript available]"
