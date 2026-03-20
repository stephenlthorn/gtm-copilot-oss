from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_emails: list[str] = field(default_factory=list)
    date: datetime | None = None
    snippet: str = ""
    body: str = ""


class GmailConnector:
    """Read-only connector for Gmail.

    Uses the Gmail API to search and read emails without modification.
    """

    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials)

    def search_emails(
        self, query: str, max_results: int = 10
    ) -> list[EmailMessage]:
        result = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = result.get("messages", [])
        return [self.get_email(msg["id"]) for msg in messages]

    def get_email(self, message_id: str) -> EmailMessage:
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

        date_str = headers.get("date", "")
        parsed_date: datetime | None = None
        try:
            from email.utils import parsedate_to_datetime
            parsed_date = parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            pass

        to_raw = headers.get("to", "")
        to_emails = [addr.strip() for addr in to_raw.split(",") if addr.strip()]

        body = self._extract_body(msg.get("payload", {}))

        return EmailMessage(
            id=msg["id"],
            thread_id=msg.get("threadId", ""),
            subject=headers.get("subject", "(No Subject)"),
            from_email=headers.get("from", ""),
            to_emails=to_emails,
            date=parsed_date,
            snippet=msg.get("snippet", ""),
            body=body,
        )

    @staticmethod
    def _extract_body(payload: dict) -> str:
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

        return ""
