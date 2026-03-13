from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_FIRECRAWL_API = "https://api.firecrawl.dev/v1"


class FirecrawlMCPHandlers:
    """Handlers for Firecrawl web scraping and search operations."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def scrape(self, url: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "Firecrawl API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{_FIRECRAWL_API}/scrape",
                    json={
                        "url": url,
                        "formats": ["markdown"],
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("data", {})
                return {
                    "url": url,
                    "title": result.get("metadata", {}).get("title", ""),
                    "content": (result.get("markdown") or "")[:10000],
                    "metadata": result.get("metadata", {}),
                }
        except Exception as exc:
            logger.exception("Firecrawl scrape error")
            return {"error": str(exc)}

    async def search_web(self, query: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "Firecrawl API key not configured", "results": []}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{_FIRECRAWL_API}/search",
                    json={"query": query, "limit": 10},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("data", [])
                return {
                    "results": [
                        {
                            "url": r.get("url", ""),
                            "title": r.get("metadata", {}).get("title", ""),
                            "description": r.get("metadata", {}).get("description", ""),
                            "content": (r.get("markdown") or "")[:2000],
                        }
                        for r in results
                    ],
                    "count": len(results),
                }
        except Exception as exc:
            logger.exception("Firecrawl search_web error")
            return {"error": str(exc), "results": []}


def create_firecrawl_mcp_server(api_key: str) -> MCPServer:
    """Create and return the Firecrawl MCP server."""
    handlers = FirecrawlMCPHandlers(api_key)

    tools = [
        MCPTool(
            name="scrape",
            description="Scrape a web page URL and return its content as markdown.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape.",
                    },
                },
                "required": ["url"],
            },
            handler=handlers.scrape,
        ),
        MCPTool(
            name="search_web",
            description="Search the web using Firecrawl and return results with content.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.search_web,
        ),
    ]

    return MCPServer(
        name="firecrawl",
        description="Scrape web pages and search the web via Firecrawl.",
        tools=tools,
    )
