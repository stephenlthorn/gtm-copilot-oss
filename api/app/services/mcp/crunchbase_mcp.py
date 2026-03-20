from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_CRUNCHBASE_API = "https://api.crunchbase.com/api/v4"


class CrunchbaseHandlers:
    """Handlers for Crunchbase company and funding data operations."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def crunchbase_search_companies(
        self,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "Crunchbase API key not configured", "results": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_CRUNCHBASE_API}/autocompletes",
                    params={
                        "query": query,
                        "collection_ids": "organizations",
                        "limit": limit,
                        "user_key": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                entities = data.get("entities", [])
                results = [
                    {
                        "name": e.get("identifier", {}).get("value", ""),
                        "permalink": e.get("identifier", {}).get("permalink", ""),
                        "uuid": e.get("identifier", {}).get("uuid", ""),
                        "short_description": e.get("short_description", ""),
                    }
                    for e in entities
                ]
                return {"results": results, "count": len(results)}
        except Exception as exc:
            logger.exception("Crunchbase search_companies error")
            return {"error": str(exc), "results": []}

    async def crunchbase_get_company(self, permalink: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "Crunchbase API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_CRUNCHBASE_API}/entities/organizations/{permalink}",
                    params={
                        "card_ids": "fields",
                        "user_key": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                props = data.get("properties", {})
                return {
                    "permalink": permalink,
                    "name": props.get("title", ""),
                    "short_description": props.get("short_description", ""),
                    "description": props.get("description", ""),
                    "website": props.get("website", {}).get("value", ""),
                    "founded_on": props.get("founded_on", {}).get("value", ""),
                    "total_funding_usd": props.get("funding_total", {}).get("value_usd"),
                    "num_funding_rounds": props.get("num_funding_rounds"),
                    "employee_count": props.get("num_employees_enum", ""),
                    "headquarters": props.get("location_identifiers", []),
                    "categories": [
                        c.get("value", "")
                        for c in props.get("category_groups", [])
                    ],
                    "last_funding_type": props.get("last_funding_type", ""),
                    "ipo_status": props.get("ipo_status", ""),
                }
        except Exception as exc:
            logger.exception("Crunchbase get_company error")
            return {"error": str(exc)}

    async def crunchbase_get_funding(self, permalink: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "Crunchbase API key not configured", "rounds": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_CRUNCHBASE_API}/entities/organizations/{permalink}/cards/funding_rounds",
                    params={"user_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                rounds = data.get("entities", [])
                results = [
                    {
                        "announced_on": r.get("properties", {}).get("announced_on", {}).get("value", ""),
                        "funding_type": r.get("properties", {}).get("funding_type", ""),
                        "money_raised_usd": r.get("properties", {}).get("money_raised", {}).get("value_usd"),
                        "num_investors": r.get("properties", {}).get("num_investors"),
                        "lead_investors": [
                            inv.get("value", "")
                            for inv in r.get("properties", {}).get("lead_investor_identifiers", [])
                        ],
                        "permalink": r.get("identifier", {}).get("permalink", ""),
                    }
                    for r in rounds
                ]
                return {"permalink": permalink, "rounds": results, "count": len(results)}
        except Exception as exc:
            logger.exception("Crunchbase get_funding error")
            return {"error": str(exc), "rounds": []}


def create_crunchbase_mcp_server(api_key: str) -> MCPServer:
    """Create and return the Crunchbase MCP server."""
    handlers = CrunchbaseHandlers(api_key)

    tools = [
        MCPTool(
            name="crunchbase_search_companies",
            description="Search for companies on Crunchbase by name or keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company name or keyword to search for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            handler=handlers.crunchbase_search_companies,
        ),
        MCPTool(
            name="crunchbase_get_company",
            description="Get detailed company information from Crunchbase by permalink.",
            parameters={
                "type": "object",
                "properties": {
                    "permalink": {
                        "type": "string",
                        "description": "The Crunchbase permalink (slug) for the organization, e.g. 'openai'.",
                    },
                },
                "required": ["permalink"],
            },
            handler=handlers.crunchbase_get_company,
        ),
        MCPTool(
            name="crunchbase_get_funding",
            description="Get funding rounds for a company from Crunchbase by permalink.",
            parameters={
                "type": "object",
                "properties": {
                    "permalink": {
                        "type": "string",
                        "description": "The Crunchbase permalink (slug) for the organization, e.g. 'openai'.",
                    },
                },
                "required": ["permalink"],
            },
            handler=handlers.crunchbase_get_funding,
        ),
    ]

    return MCPServer(
        name="crunchbase",
        description="Search companies and retrieve funding data from Crunchbase.",
        tools=tools,
    )
