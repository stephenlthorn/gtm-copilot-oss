from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.settings import Settings, get_settings
from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)


class FeishuMCPHandlers:
    """Handlers for Feishu/Lark document operations."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = (base_url or "https://open.feishu.cn/open-apis").rstrip("/")
        self._tenant_token: str | None = None

    async def _get_tenant_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            self._tenant_token = data.get("tenant_access_token", "")
            return self._tenant_token or ""

    async def _headers(self) -> dict[str, str]:
        token = await self._get_tenant_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def feishu_search(self, query: str) -> dict[str, Any]:
        if not self._app_id or not self._app_secret:
            return {"error": "Feishu app credentials not configured", "docs": []}
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/suite/docs-api/search/object",
                    json={"search_key": query, "count": 20, "offset": 0},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                docs_data = data.get("data", {}).get("docs_entities", [])
                return {
                    "docs": [
                        {
                            "doc_id": d.get("docs_token", ""),
                            "title": d.get("title", ""),
                            "doc_type": d.get("docs_type", ""),
                            "owner": d.get("owner_id", ""),
                            "url": d.get("url", ""),
                        }
                        for d in docs_data
                    ],
                    "count": len(docs_data),
                }
        except Exception as exc:
            logger.exception("Feishu search error")
            return {"error": str(exc), "docs": []}

    async def feishu_get_content(self, doc_id: str) -> dict[str, Any]:
        if not self._app_id or not self._app_secret:
            return {"error": "Feishu app credentials not configured"}
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/docx/v1/documents/{doc_id}/raw_content",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("data", {}).get("content", "")
                return {
                    "doc_id": doc_id,
                    "content": content[:10000],
                }
        except Exception as exc:
            logger.exception("Feishu get_content error")
            return {"error": str(exc)}


def create_feishu_mcp_server(
    settings: Settings | None = None,
) -> MCPServer:
    """Create and return the Feishu MCP server."""
    s = settings or get_settings()
    handlers = FeishuMCPHandlers(
        app_id=s.feishu_app_id,
        app_secret=s.feishu_app_secret,
        base_url=s.feishu_base_url,
    )

    tools = [
        MCPTool(
            name="feishu_search",
            description="Search Feishu/Lark documents by keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for Feishu documents.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.feishu_search,
        ),
        MCPTool(
            name="feishu_get_content",
            description="Get the content of a Feishu document by document ID.",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "The Feishu document ID/token.",
                    },
                },
                "required": ["doc_id"],
            },
            handler=handlers.feishu_get_content,
        ),
    ]

    return MCPServer(
        name="feishu",
        description="Search and read documents from Feishu/Lark.",
        tools=tools,
    )
