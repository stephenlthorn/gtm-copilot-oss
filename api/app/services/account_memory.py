from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountDealMemory, ChorusCall

if TYPE_CHECKING:
    from app.services.llm import LLMService

logger = logging.getLogger(__name__)

EMPTY_MEDDPICC = {
    "metrics":           {"score": 0, "evidence": "", "missing": ""},
    "economic_buyer":    {"score": 0, "evidence": "", "missing": ""},
    "decision_criteria": {"score": 0, "evidence": "", "missing": ""},
    "decision_process":  {"score": 0, "evidence": "", "missing": ""},
    "identify_pain":     {"score": 0, "evidence": "", "missing": ""},
    "champion":          {"score": 0, "evidence": "", "missing": ""},
    "competition":       {"score": 0, "evidence": "", "missing": ""},
}

DELTA_EXTRACTION_PROMPT = """You are a sales intelligence assistant. Given a call transcript or notes and the current MEDDPICC state for this account, extract a structured delta.

Current MEDDPICC state:
{current_meddpicc}

Call transcript / notes:
{transcript}

Return ONLY valid JSON matching this schema (omit keys you have no updates for):
{{
  "meddpicc_updates": {{
    "<element>": {{"score": <1-5>, "evidence": "<exact quote>", "missing": "<what is still unknown>"}}
  }},
  "key_contacts_add": [{{"name": "", "title": "", "role": "champion|evaluator|blocker|economic_buyer", "linkedin": ""}}],
  "tech_stack_updates": {{"likely": [], "possible": [], "confirmed": [], "unknown": []}},
  "open_items_add": [{{"item": "", "owner": "rep|se|prospect", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low"}}],
  "deal_stage": "<stage or omit>",
  "is_new_business": "<true|false or omit>",
  "summary": "<3-5 sentence rolling account narrative>"
}}

Scores: 1=mentioned vaguely, 2=discussed but unqualified, 3=qualified with evidence, 4=documented, 5=confirmed by multiple sources.
Return only JSON, no markdown fences."""


def canonicalize_account(account: str) -> str:
    return account.strip().lower()


class AccountMemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, account: str) -> AccountDealMemory:
        key = canonicalize_account(account)
        existing = self.db.get(AccountDealMemory, key)
        if existing:
            return existing
        row = AccountDealMemory(
            account=key,
            meddpicc=dict(EMPTY_MEDDPICC),
            key_contacts=[],
            tech_stack={"likely": [], "possible": [], "confirmed": [], "unknown": []},
            open_items=[],
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _detect_is_new_business(self, account: str, call: ChorusCall) -> bool:
        # Priority 1: Chorus stage populated
        if call.stage:
            return False
        # Priority 2: Existing account_deal_memory row
        key = canonicalize_account(account)
        if self.db.get(AccountDealMemory, key) is not None:
            return False
        # Priority 3: Prior calls exist for this account
        prior = self.db.execute(
            select(ChorusCall)
            .where(ChorusCall.account.ilike(key))
            .where(ChorusCall.id != call.id)
            .limit(1)
        ).scalar_one_or_none()
        return prior is None

    def _apply_approved_delta(self, memory: AccountDealMemory, delta: dict) -> None:
        """Merge a delta dict into the live fields of an AccountDealMemory row."""
        if "meddpicc_updates" in delta:
            current = dict(memory.meddpicc or EMPTY_MEDDPICC)
            for element, update in delta["meddpicc_updates"].items():
                if element in current:
                    current[element] = {**current[element], **update}
                else:
                    current[element] = update
            memory.meddpicc = current

        if "key_contacts_add" in delta:
            existing = list(memory.key_contacts or [])
            existing.extend(delta["key_contacts_add"])
            memory.key_contacts = existing

        if "tech_stack_updates" in delta:
            ts = dict(memory.tech_stack or {"likely": [], "possible": [], "confirmed": [], "unknown": []})
            for tier, items in delta["tech_stack_updates"].items():
                existing_tier = list(ts.get(tier, []))
                for item in items:
                    if item not in existing_tier:
                        existing_tier.append(item)
                ts[tier] = existing_tier
            memory.tech_stack = ts

        if "open_items_add" in delta:
            existing = list(memory.open_items or [])
            existing.extend(delta["open_items_add"])
            memory.open_items = existing

        if "deal_stage" in delta:
            memory.deal_stage = delta["deal_stage"]

        if "is_new_business" in delta:
            memory.is_new_business = delta["is_new_business"]

        if "summary" in delta:
            memory.summary = delta["summary"]

    def run_delta_pipeline(self, call: ChorusCall, transcript_or_notes: str, llm: "LLMService") -> None:
        """Extract MEDDPICC delta from a call and write it to pending_delta."""
        account = canonicalize_account(call.account)
        memory = self.get_or_create(account)

        # Update call stats immediately (not gated on review)
        memory.call_count = (memory.call_count or 0) + 1
        if call.date:
            if not memory.last_call_date or call.date > memory.last_call_date:
                memory.last_call_date = call.date

        # Detect new vs existing
        memory.is_new_business = self._detect_is_new_business(account, call)

        # Extract delta via LLM
        prompt = DELTA_EXTRACTION_PROMPT.format(
            current_meddpicc=json.dumps(memory.meddpicc or EMPTY_MEDDPICC, indent=2),
            transcript=transcript_or_notes[:8000],
        )
        try:
            raw = llm._responses_text("You extract structured sales intelligence from call notes.", prompt, model=None, tools=None)
            if raw:
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                delta = json.loads(text.strip())
                memory.pending_delta = delta
                memory.pending_review = True
        except Exception as exc:
            logger.warning("MEDDPICC delta extraction failed for %s: %s", account, exc)

        self.db.commit()

    def approve(self, account: str, edits: dict | None = None) -> AccountDealMemory:
        """Approve (and optionally patch) the pending delta."""
        memory = self.db.get(AccountDealMemory, canonicalize_account(account))
        if not memory:
            raise ValueError(f"No account memory found for {account!r}")
        delta = dict(memory.pending_delta or {})
        if edits:
            delta.update(edits)
        if delta:
            self._apply_approved_delta(memory, delta)
        memory.pending_review = False
        memory.pending_delta = None
        memory.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return memory

    def dismiss(self, account: str) -> AccountDealMemory:
        memory = self.db.get(AccountDealMemory, canonicalize_account(account))
        if not memory:
            raise ValueError(f"No account memory found for {account!r}")
        memory.pending_review = False
        memory.pending_delta = None
        self.db.commit()
        return memory
