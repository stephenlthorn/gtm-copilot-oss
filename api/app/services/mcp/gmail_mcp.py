from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


class GmailMCPHandlers:
    """Handlers for Gmail read-only operations."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def gmail_search(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Gmail access token not configured", "emails": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GMAIL_API}/users/me/messages",
                    params={"q": query, "maxResults": min(max_results, 20)},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                messages = resp.json().get("messages", [])

                results: list[dict[str, Any]] = []
                for msg_ref in messages[:max_results]:
                    msg_resp = await client.get(
                        f"{_GMAIL_API}/users/me/messages/{msg_ref['id']}",
                        params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                        headers=self._headers(),
                    )
                    if msg_resp.status_code != 200:
                        continue
                    msg_data = msg_resp.json()
                    headers_list = msg_data.get("payload", {}).get("headers", [])
                    header_map = {h["name"]: h["value"] for h in headers_list}
                    results.append({
                        "id": msg_data.get("id"),
                        "thread_id": msg_data.get("threadId"),
                        "subject": header_map.get("Subject", ""),
                        "from": header_map.get("From", ""),
                        "date": header_map.get("Date", ""),
                        "snippet": msg_data.get("snippet", ""),
                    })

                return {"emails": results, "count": len(results)}
        except Exception as exc:
            logger.exception("Gmail search error")
            return {"error": str(exc), "emails": []}

    async def gmail_get_email(self, message_id: str) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Gmail access token not configured"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GMAIL_API}/users/me/messages/{message_id}",
                    params={"format": "full"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                msg = resp.json()
                headers_list = msg.get("payload", {}).get("headers", [])
                header_map = {h["name"]: h["value"] for h in headers_list}

                body = ""
                payload = msg.get("payload", {})
                parts = payload.get("parts", [])
                if parts:
                    for part in parts:
                        if part.get("mimeType") == "text/plain":
                            data = part.get("body", {}).get("data", "")
                            if data:
                                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                                break
                elif payload.get("body", {}).get("data"):
                    data = payload["body"]["data"]
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

                return {
                    "id": msg.get("id"),
                    "thread_id": msg.get("threadId"),
                    "subject": header_map.get("Subject", ""),
                    "from": header_map.get("From", ""),
                    "to": header_map.get("To", ""),
                    "date": header_map.get("Date", ""),
                    "body": body[:10000],
                }
        except Exception as exc:
            logger.exception("Gmail get_email error")
            return {"error": str(exc)}


def create_gmail_mcp_server(access_token: str) -> MCPServer:
    """Create and return the Gmail MCP server (read-only)."""
    handlers = GmailMCPHandlers(access_token)

    tools = [
        MCPTool(
            name="gmail_search",
            description="Search emails in Gmail using Gmail search syntax (read-only).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query (e.g., 'from:user@example.com subject:meeting').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (default: 5, max: 20).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            handler=handlers.gmail_search,
        ),
        MCPTool(
            name="gmail_get_email",
            description="Get the full content of a specific email by message ID (read-only).",
            parameters={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The Gmail message ID.",
                    },
                },
                "required": ["message_id"],
            },
            handler=handlers.gmail_get_email,
        ),
    ]

    return MCPServer(
        name="gmail",
        description="Search and read emails from Gmail (read-only).",
        tools=tools,
    )
