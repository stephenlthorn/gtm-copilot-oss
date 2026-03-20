from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_LINKEDIN_API = "https://api.linkedin.com/v2"
_LINKEDIN_SALES_NAV_API = "https://api.linkedin.com/sales-api/v2"


class LinkedInMCPHandlers:
    """Handlers for LinkedIn standard and Sales Navigator data operations."""

    def __init__(self, access_token: str, sales_nav_token: str | None = None) -> None:
        self._access_token = access_token
        self._sales_nav_token = sales_nav_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _sales_nav_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._sales_nav_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    @property
    def _sales_nav_available(self) -> bool:
        return bool(self._sales_nav_token)

    # ------------------------------------------------------------------
    # Standard LinkedIn v2 tools
    # ------------------------------------------------------------------

    async def li_search_people(
        self,
        keywords: str,
        company: str | None = None,
    ) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "LinkedIn access token not configured", "people": []}
        try:
            params: dict[str, Any] = {
                "q": "people",
                "keywords": keywords,
                "count": 10,
            }
            if company:
                params["keywords"] = f"{keywords} {company}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_LINKEDIN_API}/search/blended",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    people: list[dict[str, Any]] = []
                    for elem in elements:
                        extended = elem.get("extendedElements", [])
                        for ext in extended:
                            entity = ext.get("entity", {})
                            people.append({
                                "name": entity.get("title", {}).get("text", ""),
                                "headline": entity.get("primarySubtitle", {}).get("text", ""),
                                "location": entity.get("secondarySubtitle", {}).get("text", ""),
                                "profile_url": entity.get("navigationUrl", ""),
                            })
                    return {"people": people[:10], "count": len(people)}
                return {
                    "error": f"LinkedIn API returned status {resp.status_code}",
                    "people": [],
                }
        except Exception as exc:
            logger.exception("LinkedIn search_people error")
            return {"error": str(exc), "people": []}

    async def li_company_info(self, company_name: str) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "LinkedIn access token not configured"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_LINKEDIN_API}/search/blended",
                    params={"q": "companies", "keywords": company_name, "count": 5},
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    companies: list[dict[str, Any]] = []
                    for elem in elements:
                        extended = elem.get("extendedElements", [])
                        for ext in extended:
                            entity = ext.get("entity", {})
                            companies.append({
                                "name": entity.get("title", {}).get("text", ""),
                                "description": entity.get("primarySubtitle", {}).get("text", ""),
                                "industry": entity.get("secondarySubtitle", {}).get("text", ""),
                                "profile_url": entity.get("navigationUrl", ""),
                            })
                    return {
                        "companies": companies[:5],
                        "count": len(companies),
                    }
                return {
                    "error": f"LinkedIn API returned status {resp.status_code}",
                    "companies": [],
                }
        except Exception as exc:
            logger.exception("LinkedIn company_info error")
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Sales Navigator tools
    # ------------------------------------------------------------------

    async def li_sales_nav_search_leads(
        self,
        keywords: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._sales_nav_available:
            return {
                "error": "LinkedIn Sales Navigator token not configured",
                "leads": [],
            }
        payload: dict[str, Any] = {
            "query": {
                "keywords": keywords,
                **(filters or {}),
            },
            "count": 10,
            "start": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_LINKEDIN_SALES_NAV_API}/leads/search",
                    json=payload,
                    headers=self._sales_nav_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    leads: list[dict[str, Any]] = []
                    for el in elements:
                        first = el.get("firstName", "")
                        last = el.get("lastName", "")
                        name = f"{first} {last}".strip() or el.get("fullName", "")
                        current_position = (el.get("currentPositions") or [{}])[0]
                        leads.append({
                            "id": str(el.get("id", "")),
                            "name": name,
                            "title": current_position.get("title") or el.get("title"),
                            "company": current_position.get("companyName") or el.get("companyName"),
                            "geography": el.get("geoRegion"),
                            "industry": el.get("industry"),
                            "profile_url": el.get("publicProfileUrl"),
                        })
                    return {"leads": leads, "count": len(leads)}
                return {
                    "error": f"Sales Navigator API returned status {resp.status_code}",
                    "leads": [],
                }
        except Exception as exc:
            logger.warning("Sales Nav search_leads error: %s", exc)
            return {"error": str(exc), "leads": []}

    async def li_sales_nav_get_lead_profile(self, lead_id: str) -> dict[str, Any]:
        if not self._sales_nav_available:
            return {"error": "LinkedIn Sales Navigator token not configured"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_LINKEDIN_SALES_NAV_API}/leads/{lead_id}",
                    headers=self._sales_nav_headers(),
                )
                if resp.status_code == 200:
                    el = resp.json()
                    first = el.get("firstName", "")
                    last = el.get("lastName", "")
                    name = f"{first} {last}".strip() or el.get("fullName", "")
                    current_position = (el.get("currentPositions") or [{}])[0]
                    return {
                        "id": str(el.get("id", "")),
                        "name": name,
                        "title": current_position.get("title") or el.get("title"),
                        "company": current_position.get("companyName") or el.get("companyName"),
                        "geography": el.get("geoRegion"),
                        "industry": el.get("industry"),
                        "summary": el.get("summary"),
                        "profile_url": el.get("publicProfileUrl"),
                    }
                return {
                    "error": f"Sales Navigator API returned status {resp.status_code}",
                }
        except Exception as exc:
            logger.warning("Sales Nav get_lead_profile error: %s", exc)
            return {"error": str(exc)}

    async def li_sales_nav_search_accounts(
        self,
        keywords: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._sales_nav_available:
            return {
                "error": "LinkedIn Sales Navigator token not configured",
                "accounts": [],
            }
        payload: dict[str, Any] = {
            "query": {
                "keywords": keywords,
                **(filters or {}),
            },
            "count": 10,
            "start": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_LINKEDIN_SALES_NAV_API}/accounts/search",
                    json=payload,
                    headers=self._sales_nav_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    accounts: list[dict[str, Any]] = []
                    for el in elements:
                        accounts.append({
                            "id": str(el.get("id", "")),
                            "name": el.get("name", ""),
                            "industry": el.get("industry"),
                            "website": el.get("websiteUrl"),
                            "employee_count": el.get("employeeCount"),
                            "geography": el.get("headquartersLocation"),
                            "revenue": el.get("revenueRange"),
                        })
                    return {"accounts": accounts, "count": len(accounts)}
                return {
                    "error": f"Sales Navigator API returned status {resp.status_code}",
                    "accounts": [],
                }
        except Exception as exc:
            logger.warning("Sales Nav search_accounts error: %s", exc)
            return {"error": str(exc), "accounts": []}

    async def li_sales_nav_get_account_details(self, account_id: str) -> dict[str, Any]:
        if not self._sales_nav_available:
            return {"error": "LinkedIn Sales Navigator token not configured"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_LINKEDIN_SALES_NAV_API}/accounts/{account_id}",
                    headers=self._sales_nav_headers(),
                )
                if resp.status_code == 200:
                    el = resp.json()
                    return {
                        "id": str(el.get("id", "")),
                        "name": el.get("name", ""),
                        "industry": el.get("industry"),
                        "website": el.get("websiteUrl"),
                        "employee_count": el.get("employeeCount"),
                        "description": el.get("description"),
                        "geography": el.get("headquartersLocation"),
                        "revenue": el.get("revenueRange"),
                    }
                return {
                    "error": f"Sales Navigator API returned status {resp.status_code}",
                }
        except Exception as exc:
            logger.warning("Sales Nav get_account_details error: %s", exc)
            return {"error": str(exc)}


def create_linkedin_mcp_server(
    access_token: str,
    sales_nav_token: str | None = None,
) -> MCPServer:
    """Create and return the LinkedIn MCP server.

    Pass ``sales_nav_token`` (or set ``LINKEDIN_SALES_NAV_TOKEN`` /
    ``LINKEDIN_SALES_NAV_API_KEY`` in the environment) to enable the
    Sales Navigator tools alongside the standard LinkedIn tools.
    """
    import os

    resolved_sales_nav_token = (
        sales_nav_token
        or os.environ.get("LINKEDIN_SALES_NAV_TOKEN")
        or os.environ.get("LINKEDIN_SALES_NAV_API_KEY")
    )

    handlers = LinkedInMCPHandlers(access_token, resolved_sales_nav_token)

    tools = [
        # Standard LinkedIn tools
        MCPTool(
            name="li_search_people",
            description="Search for people on LinkedIn by keywords, optionally filtered by company.",
            parameters={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords (e.g., 'VP Engineering').",
                    },
                    "company": {
                        "type": "string",
                        "description": "Optional company name to narrow results.",
                    },
                },
                "required": ["keywords"],
            },
            handler=handlers.li_search_people,
        ),
        MCPTool(
            name="li_company_info",
            description="Look up company information on LinkedIn.",
            parameters={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name to look up.",
                    },
                },
                "required": ["company_name"],
            },
            handler=handlers.li_company_info,
        ),
        # Sales Navigator tools
        MCPTool(
            name="li_sales_nav_search_leads",
            description=(
                "Search for leads (prospects) using LinkedIn Sales Navigator. "
                "Returns richer profile data than standard LinkedIn search. "
                "Requires a Sales Navigator token."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Keywords to search for (e.g., 'CTO fintech').",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Optional Sales Navigator filter object "
                            "(e.g., {\"geographyIncluded\": [\"us:0\"], \"seniorityIncluded\": [\"C\"]}). "
                            "Keys map directly to the Sales Nav API query fields."
                        ),
                    },
                },
                "required": ["keywords"],
            },
            handler=handlers.li_sales_nav_search_leads,
        ),
        MCPTool(
            name="li_sales_nav_get_lead_profile",
            description=(
                "Retrieve a detailed prospect profile from LinkedIn Sales Navigator by lead ID."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "The Sales Navigator lead ID.",
                    },
                },
                "required": ["lead_id"],
            },
            handler=handlers.li_sales_nav_get_lead_profile,
        ),
        MCPTool(
            name="li_sales_nav_search_accounts",
            description=(
                "Search for companies/accounts using LinkedIn Sales Navigator. "
                "Returns richer company data than standard LinkedIn search. "
                "Requires a Sales Navigator token."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Keywords to search for (e.g., 'enterprise SaaS').",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Optional Sales Navigator filter object "
                            "(e.g., {\"geographyIncluded\": [\"us:0\"], \"headcountRange\": [\"B\", \"C\"]}). "
                            "Keys map directly to the Sales Nav API query fields."
                        ),
                    },
                },
                "required": ["keywords"],
            },
            handler=handlers.li_sales_nav_search_accounts,
        ),
        MCPTool(
            name="li_sales_nav_get_account_details",
            description=(
                "Retrieve detailed company information from LinkedIn Sales Navigator by account ID."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The Sales Navigator account ID.",
                    },
                },
                "required": ["account_id"],
            },
            handler=handlers.li_sales_nav_get_account_details,
        ),
    ]

    return MCPServer(
        name="linkedin",
        description="Search people and companies on LinkedIn, with Sales Navigator support.",
        tools=tools,
    )
