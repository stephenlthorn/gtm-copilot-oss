from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_LI_API_BASE = "https://api.linkedin.com/v2"
_LI_SALES_NAV_BASE = "https://api.linkedin.com/sales-api/v2"


@dataclass(frozen=True)
class LinkedInProfile:
    id: str
    name: str
    title: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class CompanyInfo:
    id: str
    name: str
    industry: str | None = None
    website: str | None = None
    employee_count: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class SalesNavLead:
    id: str
    name: str
    title: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    geography: str | None = None
    industry: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class SalesNavAccount:
    id: str
    name: str
    industry: str | None = None
    website: str | None = None
    employee_count: int | None = None
    description: str | None = None
    geography: str | None = None
    revenue: str | None = None


class LinkedInConnector:
    """Best-effort client for the LinkedIn v2 API and Sales Navigator API.

    LinkedIn's API is restrictive and requires specific partner-level access.
    Sales Navigator requires a separate OAuth token (LINKEDIN_SALES_NAV_TOKEN).
    This connector provides a thin wrapper; callers should handle 403/429
    responses gracefully.
    """

    def __init__(self, access_token: str, sales_nav_token: str | None = None) -> None:
        self.access_token = access_token
        self.sales_nav_token: str | None = sales_nav_token or os.environ.get(
            "LINKEDIN_SALES_NAV_TOKEN"
        ) or os.environ.get("LINKEDIN_SALES_NAV_API_KEY")

        self._client = httpx.AsyncClient(
            base_url=_LI_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=_DEFAULT_TIMEOUT,
        )

    @property
    def sales_nav_available(self) -> bool:
        """Return True if a Sales Navigator token is present."""
        return bool(self.sales_nav_token)

    def _sales_nav_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=_LI_SALES_NAV_BASE,
            headers={
                "Authorization": f"Bearer {self.sales_nav_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=_DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Standard LinkedIn v2 methods
    # ------------------------------------------------------------------

    async def search_people(
        self, keywords: str, company: str | None = None
    ) -> list[LinkedInProfile]:
        params: dict[str, str] = {
            "q": "people",
            "keywords": keywords,
            "count": "10",
        }
        if company:
            params["facetCurrentCompany"] = company

        try:
            resp = await self._client.get("/search/people", params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "LinkedIn people search failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []

        elements = resp.json().get("elements", [])
        return [self._parse_profile(el) for el in elements]

    async def get_company_info(self, company_id: str) -> CompanyInfo | None:
        try:
            resp = await self._client.get(f"/organizations/{company_id}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "LinkedIn company lookup failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return None

        data = resp.json()
        return CompanyInfo(
            id=str(data.get("id", company_id)),
            name=data.get("localizedName", ""),
            industry=data.get("industries", [None])[0] if data.get("industries") else None,
            website=data.get("websiteUrl"),
            employee_count=data.get("staffCount"),
            description=data.get("localizedDescription"),
        )

    # ------------------------------------------------------------------
    # Sales Navigator methods
    # ------------------------------------------------------------------

    async def search_leads(
        self,
        keywords: str,
        filters: dict[str, Any] | None = None,
    ) -> list[SalesNavLead]:
        """Search for leads using the Sales Navigator API.

        Falls back to an empty list if Sales Nav is unavailable or the
        request fails.
        """
        if not self.sales_nav_available:
            logger.warning("Sales Navigator token not configured; skipping lead search")
            return []

        payload: dict[str, Any] = {
            "query": {
                "keywords": keywords,
                **(filters or {}),
            },
            "count": 10,
            "start": 0,
        }

        try:
            async with self._sales_nav_client() as client:
                resp = await client.post("/leads/search", json=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Sales Nav lead search failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []

        elements = resp.json().get("elements", [])
        return [self._parse_sales_nav_lead(el) for el in elements]

    async def get_lead_profile(self, lead_id: str) -> SalesNavLead | None:
        """Retrieve a detailed lead profile from Sales Navigator."""
        if not self.sales_nav_available:
            logger.warning("Sales Navigator token not configured; skipping lead profile lookup")
            return None

        try:
            async with self._sales_nav_client() as client:
                resp = await client.get(f"/leads/{lead_id}")
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Sales Nav lead profile lookup failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return None

        return self._parse_sales_nav_lead(resp.json())

    async def search_accounts(
        self,
        keywords: str,
        filters: dict[str, Any] | None = None,
    ) -> list[SalesNavAccount]:
        """Search for accounts using the Sales Navigator API.

        Falls back to an empty list if Sales Nav is unavailable or the
        request fails.
        """
        if not self.sales_nav_available:
            logger.warning("Sales Navigator token not configured; skipping account search")
            return []

        payload: dict[str, Any] = {
            "query": {
                "keywords": keywords,
                **(filters or {}),
            },
            "count": 10,
            "start": 0,
        }

        try:
            async with self._sales_nav_client() as client:
                resp = await client.post("/accounts/search", json=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Sales Nav account search failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []

        elements = resp.json().get("elements", [])
        return [self._parse_sales_nav_account(el) for el in elements]

    async def get_account_details(self, account_id: str) -> SalesNavAccount | None:
        """Retrieve detailed company information from Sales Navigator."""
        if not self.sales_nav_available:
            logger.warning(
                "Sales Navigator token not configured; skipping account details lookup"
            )
            return None

        try:
            async with self._sales_nav_client() as client:
                resp = await client.get(f"/accounts/{account_id}")
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Sales Nav account details lookup failed (status=%s): %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return None

        return self._parse_sales_nav_account(resp.json())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_profile(data: dict) -> LinkedInProfile:
        first = data.get("firstName", {}).get("localized", {}).get("en_US", "")
        last = data.get("lastName", {}).get("localized", {}).get("en_US", "")
        name = f"{first} {last}".strip() or data.get("name", "")

        return LinkedInProfile(
            id=str(data.get("id", "")),
            name=name,
            title=data.get("headline"),
            company=data.get("currentCompany"),
            linkedin_url=data.get("publicProfileUrl"),
            summary=data.get("summary"),
        )

    @staticmethod
    def _parse_sales_nav_lead(data: dict) -> SalesNavLead:
        first = data.get("firstName", "")
        last = data.get("lastName", "")
        name = f"{first} {last}".strip() or data.get("fullName", "") or data.get("name", "")

        current_position = (data.get("currentPositions") or [{}])[0]

        return SalesNavLead(
            id=str(data.get("id", "")),
            name=name,
            title=current_position.get("title") or data.get("title"),
            company=current_position.get("companyName") or data.get("companyName"),
            linkedin_url=data.get("publicProfileUrl"),
            geography=data.get("geoRegion"),
            industry=data.get("industry"),
            summary=data.get("summary"),
        )

    @staticmethod
    def _parse_sales_nav_account(data: dict) -> SalesNavAccount:
        return SalesNavAccount(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            industry=data.get("industry"),
            website=data.get("websiteUrl"),
            employee_count=data.get("employeeCount"),
            description=data.get("description"),
            geography=data.get("headquartersLocation"),
            revenue=data.get("revenueRange"),
        )
