from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import ResearchReport, User

logger = logging.getLogger(__name__)

_DEFAULT_LOOKAHEAD_DAYS = 3


@dataclass(frozen=True)
class ResearchTrigger:
    event_id: str
    meeting_title: str
    start_time: datetime
    company_name: str
    attendees: list[str] = field(default_factory=list)
    needs_research: bool = True


class CalendarScannerService:
    """Scans upcoming calendar events to identify meetings needing pre-call research."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    async def scan_upcoming(
        self, user_id: int, org_id: int
    ) -> list[ResearchTrigger]:
        """Scan a user's calendar for upcoming external meetings that need research.

        Steps:
        1. Get user's calendar credentials
        2. Fetch meetings in next N days (from user preferences)
        3. Filter for external attendees (outside org domain)
        4. Check if research_report already exists for meeting_id
        5. Return list of meetings needing research
        """
        user = self._db.query(User).get(user_id)
        if not user:
            logger.warning("User %d not found for calendar scan", user_id)
            return []

        lookahead_days = _DEFAULT_LOOKAHEAD_DAYS
        if user.preferences and isinstance(user.preferences, dict):
            lookahead_days = user.preferences.get("research_lookahead_days", _DEFAULT_LOOKAHEAD_DAYS)

        events = await self._fetch_calendar_events(user, lookahead_days)

        org_domains = self._get_org_domains()

        triggers: list[ResearchTrigger] = []
        for event in events:
            external_attendees = self._filter_external_attendees(
                event.get("attendees", []), org_domains
            )
            if not external_attendees:
                continue

            event_id = event.get("id", "")
            existing_report = (
                self._db.query(ResearchReport)
                .filter_by(meeting_id=event_id, org_id=org_id)
                .first()
            )
            if existing_report:
                continue

            company_name = self._extract_company_name(event, external_attendees)

            trigger = ResearchTrigger(
                event_id=event_id,
                meeting_title=event.get("summary", "Untitled Meeting"),
                start_time=self._parse_event_time(event.get("start", {})),
                company_name=company_name,
                attendees=external_attendees,
                needs_research=True,
            )
            triggers.append(trigger)

        return triggers

    async def _fetch_calendar_events(
        self, user: User, lookahead_days: int
    ) -> list[dict[str, Any]]:
        """Fetch upcoming calendar events for the user.

        Uses Google Calendar API via stored credentials. Returns raw event
        dicts for processing.
        """
        try:
            from app.models.entities import GoogleDriveUserCredential
            from app.services.token_crypto import decrypt_token

            cred = (
                self._db.query(GoogleDriveUserCredential)
                .filter_by(user_email=user.email)
                .first()
            )
            if not cred:
                logger.info("No Google credentials for user %s", user.email)
                return []

            import httpx

            token_data = decrypt_token(cred.token_encrypted)
            access_token = token_data.get("access_token", "") if isinstance(token_data, dict) else str(token_data)

            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=lookahead_days)).isoformat()

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": "50",
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code != 200:
                    logger.warning("Calendar API returned %d for user %s", resp.status_code, user.email)
                    return []
                data = resp.json()
                return data.get("items", [])

        except Exception:
            logger.exception("Failed to fetch calendar events for user %s", user.email)
            return []

    def _get_org_domains(self) -> set[str]:
        """Return the set of internal domains for filtering external attendees."""
        return set(self._settings.domain_allowlist)

    @staticmethod
    def _filter_external_attendees(
        attendees: list[dict[str, Any]], org_domains: set[str]
    ) -> list[str]:
        """Return emails of attendees whose domain is not in the org domain list."""
        external: list[str] = []
        for attendee in attendees:
            email = attendee.get("email", "")
            if not email:
                continue
            domain = email.split("@")[-1].lower()
            if domain not in org_domains:
                external.append(email)
        return external

    @staticmethod
    def _extract_company_name(
        event: dict[str, Any], external_attendees: list[str]
    ) -> str:
        """Best-effort extraction of company name from event or attendee domains.

        Checks the event title/description first, then falls back to the most
        common external domain.
        """
        title = event.get("summary", "")
        description = event.get("description", "")

        for text in [title, description]:
            match = re.search(r"(?:with|@|re:)\s+([A-Z][A-Za-z0-9\s&.]+)", text)
            if match:
                return match.group(1).strip()

        if external_attendees:
            domain = external_attendees[0].split("@")[-1]
            company = domain.split(".")[0].capitalize()
            return company

        return "Unknown Company"

    @staticmethod
    def _parse_event_time(start: dict[str, Any]) -> datetime:
        """Parse a Google Calendar event start time."""
        date_time_str = start.get("dateTime")
        if date_time_str:
            return datetime.fromisoformat(date_time_str)
        date_str = start.get("date")
        if date_str:
            return datetime.fromisoformat(date_str)
        return datetime.now(timezone.utc)
