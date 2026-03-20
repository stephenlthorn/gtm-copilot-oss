from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    summary: str
    start_time: datetime
    end_time: datetime
    attendees: list[str] = field(default_factory=list)
    description: str | None = None
    is_external: bool = False


class CalendarConnector:
    """Read-only connector for Google Calendar.

    Retrieves upcoming meetings and identifies external ones based on the
    organization domain.
    """

    def __init__(self, credentials: Credentials, org_domain: str | None = None) -> None:
        self._service = build("calendar", "v3", credentials=credentials)
        self._org_domain = org_domain

    def get_upcoming_meetings(
        self, days_ahead: int = 7
    ) -> list[CalendarEvent]:
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        result = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            attendee_emails = [
                a.get("email", "") for a in item.get("attendees", [])
            ]
            is_ext = self._has_external_attendees(attendee_emails)

            start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")
            end_raw = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date", "")

            try:
                start_time = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                start_time = now

            try:
                end_time = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                end_time = start_time + timedelta(hours=1)

            events.append(
                CalendarEvent(
                    event_id=item.get("id", ""),
                    summary=item.get("summary", "(No title)"),
                    start_time=start_time,
                    end_time=end_time,
                    attendees=attendee_emails,
                    description=item.get("description"),
                    is_external=is_ext,
                )
            )

        return events

    def _has_external_attendees(self, emails: list[str]) -> bool:
        if not self._org_domain or not emails:
            return False
        return any(
            not email.endswith(f"@{self._org_domain}")
            for email in emails
            if email
        )
