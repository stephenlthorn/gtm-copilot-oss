from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_DRIVE_API = "https://www.googleapis.com/drive/v3"


class GoogleDriveMCPHandlers:
    """Handlers for Google Drive operations."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def drive_search(self, query: str) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Google Drive access token not configured", "files": []}
        try:
            drive_query = f"fullText contains '{query}' and trashed = false"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_DRIVE_API}/files",
                    params={
                        "q": drive_query,
                        "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners)",
                        "pageSize": 20,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                files = data.get("files", [])
                return {
                    "files": [
                        {
                            "id": f.get("id"),
                            "name": f.get("name"),
                            "mime_type": f.get("mimeType"),
                            "modified_time": f.get("modifiedTime"),
                            "web_view_link": f.get("webViewLink"),
                            "owner": (f.get("owners") or [{}])[0].get("displayName", "")
                            if f.get("owners")
                            else "",
                        }
                        for f in files
                    ],
                    "count": len(files),
                }
        except Exception as exc:
            logger.exception("Google Drive search error")
            return {"error": str(exc), "files": []}

    async def drive_get_content(self, file_id: str) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "Google Drive access token not configured"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                meta_resp = await client.get(
                    f"{_DRIVE_API}/files/{file_id}",
                    params={"fields": "id,name,mimeType,modifiedTime"},
                    headers=self._headers(),
                )
                meta_resp.raise_for_status()
                meta = meta_resp.json()

                content_resp = await client.get(
                    f"{_DRIVE_API}/files/{file_id}/export",
                    params={"mimeType": "text/plain"},
                    headers=self._headers(),
                )
                if content_resp.status_code == 200:
                    text = content_resp.text[:10000]
                else:
                    content_resp2 = await client.get(
                        f"{_DRIVE_API}/files/{file_id}",
                        params={"alt": "media"},
                        headers=self._headers(),
                    )
                    text = content_resp2.text[:10000] if content_resp2.status_code == 200 else ""

                return {
                    "file": {
                        "id": meta.get("id"),
                        "name": meta.get("name"),
                        "mime_type": meta.get("mimeType"),
                        "modified_time": meta.get("modifiedTime"),
                    },
                    "content": text,
                }
        except Exception as exc:
            logger.exception("Google Drive get_content error")
            return {"error": str(exc)}


def create_drive_mcp_server(access_token: str) -> MCPServer:
    """Create and return the Google Drive MCP server."""
    handlers = GoogleDriveMCPHandlers(access_token)

    tools = [
        MCPTool(
            name="drive_search",
            description="Search Google Drive documents by keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for Google Drive.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.drive_search,
        ),
        MCPTool(
            name="drive_get_content",
            description="Get the text content of a Google Drive file by its ID.",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The Google Drive file ID.",
                    },
                },
                "required": ["file_id"],
            },
            handler=handlers.drive_get_content,
        ),
    ]

    return MCPServer(
        name="google_drive",
        description="Search and read documents from Google Drive.",
        tools=tools,
    )
