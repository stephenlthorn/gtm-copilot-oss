from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class CompanyData:
    id: str
    name: str
    industry: str | None = None
    employee_count: int | None = None
    revenue: str | None = None
    website: str | None = None
    description: str | None = None
    technographics: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PersonData:
    id: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None


class ZoomInfoConnector:
    """Client for the ZoomInfo API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://api.zoominfo.com",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=_DEFAULT_TIMEOUT,
        )

    async def search_company(self, name: str) -> CompanyData | None:
        resp = await self._client.post(
            "/search/company",
            json={"companyName": name, "maxResults": 1},
        )
        resp.raise_for_status()
        results = resp.json().get("data", [])
        if not results:
            return None
        return self._parse_company(results[0])

    async def search_person(
        self, name: str, company: str | None = None
    ) -> list[PersonData]:
        payload: dict = {"fullName": name, "maxResults": 10}
        if company:
            payload["companyName"] = company

        resp = await self._client.post("/search/contact", json=payload)
        resp.raise_for_status()
        results = resp.json().get("data", [])
        return [self._parse_person(r) for r in results]

    async def get_technographics(self, company_id: str) -> dict:
        resp = await self._client.get(f"/lookup/company/technographics/{company_id}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse_company(data: dict) -> CompanyData:
        return CompanyData(
            id=str(data.get("id", "")),
            name=data.get("companyName", ""),
            industry=data.get("industry"),
            employee_count=data.get("employeeCount"),
            revenue=data.get("revenue"),
            website=data.get("website"),
            description=data.get("companyDescription"),
            technographics=data.get("technographics", {}),
        )

    @staticmethod
    def _parse_person(data: dict) -> PersonData:
        return PersonData(
            id=str(data.get("id", "")),
            name=data.get("fullName", ""),
            title=data.get("jobTitle"),
            email=data.get("email"),
            phone=data.get("phone"),
            linkedin_url=data.get("linkedinUrl"),
        )
