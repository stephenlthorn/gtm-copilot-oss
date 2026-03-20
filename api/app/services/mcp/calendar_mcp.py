from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class CalendarMCPHandlers:
    """Handlers for Google Calendar read-only operations."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def calendar_upcoming(self, days: int = 7) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Calendar access token not configured", "events": []}
        try:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days)).isoformat()

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_CALENDAR_API}/calendars/primary/events",
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 50,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return {
                    "events": [_format_event(e) for e in items],
                    "count": len(items),
                }
        except Exception as exc:
            logger.exception("Calendar upcoming error")
            return {"error": str(exc), "events": []}

    async def calendar_search(self, query: str) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Calendar access token not configured", "events": []}
        try:
            now = datetime.now(timezone.utc)
            time_min = (now - timedelta(days=90)).isoformat()
            time_max = (now + timedelta(days=90)).isoformat()

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_CALENDAR_API}/calendars/primary/events",
                    params={
                        "q": query,
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 30,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return {
                    "events": [_format_event(e) for e in items],
                    "count": len(items),
                }
        except Exception as exc:
            logger.exception("Calendar search error")
            return {"error": str(exc), "events": []}


def _format_event(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    attendees = event.get("attendees", [])
    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(No title)"),
        "start": start.get("dateTime") or start.get("date", ""),
        "end": end.get("dateTime") or end.get("date", ""),
        "location": event.get("location", ""),
        "description": (event.get("description") or "")[:500],
        "attendees": [
            {
                "email": a.get("email", ""),
                "name": a.get("displayName", ""),
                "response": a.get("responseStatus", ""),
            }
            for a in attendees[:20]
        ],
        "html_link": event.get("htmlLink", ""),
        "status": event.get("status", ""),
    }


def create_calendar_mcp_server(access_token: str) -> MCPServer:
    """Create and return the Calendar MCP server (read-only)."""
    handlers = CalendarMCPHandlers(access_token)

    tools = [
        MCPTool(
            name="calendar_upcoming",
            description="Get upcoming calendar events for the next N days (read-only).",
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 7).",
                        "default": 7,
                    },
                },
            },
            handler=handlers.calendar_upcoming,
        ),
        MCPTool(
            name="calendar_search",
            description="Search calendar events by keyword (read-only).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to find matching calendar events.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.calendar_search,
        ),
    ]

    return MCPServer(
        name="calendar",
        description="Search and view Google Calendar events (read-only).",
        tools=tools,
    )
