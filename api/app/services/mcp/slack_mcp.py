from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.settings import Settings, get_settings
from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)


class SlackMCPHandlers:
    """Handlers for Slack operations via the Slack Web API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def _token(self) -> str:
        return (self._settings.slack_bot_token or "").strip()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def slack_search(
        self,
        query: str,
        channel: str | None = None,
    ) -> dict[str, Any]:
        if not self._token:
            return {"error": "Slack bot token not configured", "messages": []}
        try:
            search_query = query
            if channel:
                search_query = f"in:{channel} {query}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://slack.com/api/search.messages",
                    params={"query": search_query, "count": 20},
                    headers=self._headers(),
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"error": data.get("error", "unknown"), "messages": []}
                matches = (data.get("messages") or {}).get("matches", [])
                return {
                    "messages": [
                        {
                            "text": m.get("text", ""),
                            "user": m.get("username", ""),
                            "channel": (m.get("channel") or {}).get("name", ""),
                            "ts": m.get("ts", ""),
                            "permalink": m.get("permalink", ""),
                        }
                        for m in matches[:20]
                    ],
                    "count": len(matches),
                }
        except Exception as exc:
            logger.exception("Slack search error")
            return {"error": str(exc), "messages": []}

    async def slack_post(self, channel: str, message: str) -> dict[str, Any]:
        if not self._token:
            return {"error": "Slack bot token not configured"}
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    json={"channel": channel, "text": message},
                    headers=self._headers(),
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"error": data.get("error", "unknown")}
                return {
                    "ok": True,
                    "channel": data.get("channel"),
                    "ts": data.get("ts"),
                }
        except Exception as exc:
            logger.exception("Slack post error")
            return {"error": str(exc)}

    async def slack_get_channels(self) -> dict[str, Any]:
        if not self._token:
            return {"error": "Slack bot token not configured", "channels": []}
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://slack.com/api/conversations.list",
                    params={"types": "public_channel,private_channel", "limit": 100},
                    headers=self._headers(),
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"error": data.get("error", "unknown"), "channels": []}
                channels = data.get("channels", [])
                return {
                    "channels": [
                        {
                            "id": ch.get("id"),
                            "name": ch.get("name"),
                            "topic": (ch.get("topic") or {}).get("value", ""),
                            "num_members": ch.get("num_members", 0),
                        }
                        for ch in channels
                    ],
                    "count": len(channels),
                }
        except Exception as exc:
            logger.exception("Slack get_channels error")
            return {"error": str(exc), "channels": []}


def create_slack_mcp_server(settings: Settings | None = None) -> MCPServer:
    """Create and return the Slack MCP server."""
    handlers = SlackMCPHandlers(settings)

    tools = [
        MCPTool(
            name="slack_search",
            description="Search Slack messages. Optionally filter by channel name.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for Slack messages.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional channel name to search within.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.slack_search,
        ),
        MCPTool(
            name="slack_post",
            description="Post a message to a Slack channel.",
            parameters={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "The Slack channel ID or name to post to.",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message text to post.",
                    },
                },
                "required": ["channel", "message"],
            },
            handler=handlers.slack_post,
        ),
        MCPTool(
            name="slack_get_channels",
            description="List available Slack channels.",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=handlers.slack_get_channels,
        ),
    ]

    return MCPServer(
        name="slack",
        description="Search and post messages in Slack channels.",
        tools=tools,
    )
