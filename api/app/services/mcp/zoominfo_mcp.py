from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_ZOOMINFO_API = "https://api.zoominfo.com"


class ZoomInfoMCPHandlers:
    """Handlers for ZoomInfo data enrichment operations."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def zi_company_search(self, name: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "ZoomInfo API key not configured", "companies": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_ZOOMINFO_API}/search/company",
                    json={
                        "companyName": name,
                        "maxResults": 10,
                        "outputFields": [
                            "id", "name", "website", "industry", "subIndustry",
                            "employeeCount", "revenue", "city", "state", "country",
                            "description", "foundedYear", "ticker",
                        ],
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("data", [])
                return {
                    "companies": companies[:10],
                    "count": len(companies),
                }
        except Exception as exc:
            logger.exception("ZoomInfo company_search error")
            return {"error": str(exc), "companies": []}

    async def zi_person_search(
        self,
        name: str,
        company: str | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "ZoomInfo API key not configured", "people": []}
        try:
            body: dict[str, Any] = {
                "fullName": name,
                "maxResults": 10,
                "outputFields": [
                    "id", "firstName", "lastName", "email", "phone",
                    "jobTitle", "companyName", "companyId", "linkedinUrl",
                ],
            }
            if company:
                body["companyName"] = company

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_ZOOMINFO_API}/search/person",
                    json=body,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                people = data.get("data", [])
                return {
                    "people": people[:10],
                    "count": len(people),
                }
        except Exception as exc:
            logger.exception("ZoomInfo person_search error")
            return {"error": str(exc), "people": []}

    async def zi_technographics(self, company_name: str) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "ZoomInfo API key not configured", "technologies": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_ZOOMINFO_API}/search/company",
                    json={
                        "companyName": company_name,
                        "maxResults": 1,
                        "outputFields": ["id", "name", "techAttributes"],
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("data", [])
                if not companies:
                    return {"error": f"Company '{company_name}' not found", "technologies": []}
                tech = companies[0].get("techAttributes", [])
                return {
                    "company": company_name,
                    "technologies": tech,
                    "count": len(tech),
                }
        except Exception as exc:
            logger.exception("ZoomInfo technographics error")
            return {"error": str(exc), "technologies": []}


def create_zoominfo_mcp_server(api_key: str) -> MCPServer:
    """Create and return the ZoomInfo MCP server."""
    handlers = ZoomInfoMCPHandlers(api_key)

    tools = [
        MCPTool(
            name="zi_company_search",
            description="Look up company information from ZoomInfo by company name.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The company name to search for.",
                    },
                },
                "required": ["name"],
            },
            handler=handlers.zi_company_search,
        ),
        MCPTool(
            name="zi_person_search",
            description="Look up a person in ZoomInfo by name, optionally filtered by company.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's full name.",
                    },
                    "company": {
                        "type": "string",
                        "description": "Optional company name to narrow search.",
                    },
                },
                "required": ["name"],
            },
            handler=handlers.zi_person_search,
        ),
        MCPTool(
            name="zi_technographics",
            description="Get the technology stack/technographics for a company from ZoomInfo.",
            parameters={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name to look up tech stack for.",
                    },
                },
                "required": ["company_name"],
            },
            handler=handlers.zi_technographics,
        ),
    ]

    return MCPServer(
        name="zoominfo",
        description="Company and person enrichment data from ZoomInfo, including technographics.",
        tools=tools,
    )
