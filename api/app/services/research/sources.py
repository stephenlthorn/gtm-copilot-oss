from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_SOURCE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SourceResult:
    source_name: str
    status: str  # "success" | "failed" | "timeout" | "skipped"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _get_firecrawl(settings) -> Any | None:
    if not settings.firecrawl_api_key:
        return None
    try:
        from app.services.connectors.firecrawl import FirecrawlConnector
        return FirecrawlConnector(api_key=settings.firecrawl_api_key)
    except Exception as exc:
        logger.warning("Could not init FirecrawlConnector: %s", exc)
        return None


class ResearchSourceRunner:
    """Fan-out research across all active OSINT data sources.

    Each source runs independently with a per-source timeout.
    New sources (EDGAR, BuiltWith, HN) are wired in here.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    async def run_all_sources(
        self,
        account_name: str,
        website: str,
        org_id: int,
        account_id: int | None = None,
        custom_urls: list[str] | None = None,
    ) -> dict[str, SourceResult]:
        tasks: dict[str, asyncio.Task[SourceResult]] = {}

        async with asyncio.TaskGroup() as tg:
            # ── Web scraping sources (require Firecrawl key) ──────────────
            if website:
                tasks["company_website"] = tg.create_task(
                    self._run("company_website", self.scrape_company_website(website))
                )
            tasks["crunchbase"] = tg.create_task(
                self._run("crunchbase", self.search_crunchbase(account_name))
            )
            tasks["news"] = tg.create_task(
                self._run("news", self.search_news(account_name))
            )
            tasks["job_postings"] = tg.create_task(
                self._run("job_postings", self.search_job_postings(account_name))
            )
            tasks["reviews"] = tg.create_task(
                self._run("reviews", self.search_reviews(account_name))
            )

            # ── Free OSINT sources (no API key needed) ────────────────────
            tasks["edgar"] = tg.create_task(
                self._run("edgar", self.search_edgar(account_name))
            )
            tasks["hn"] = tg.create_task(
                self._run("hn", self.search_hn(account_name))
            )

            # ── Paid OSINT sources ────────────────────────────────────────
            if website:
                tasks["builtwith"] = tg.create_task(
                    self._run("builtwith", self.search_builtwith(website))
                )

            # ── Internal data sources ─────────────────────────────────────
            tasks["chorus_calls"] = tg.create_task(
                self._run("chorus_calls", self.search_chorus_calls(account_name))
            )
            tasks["salesforce"] = tg.create_task(
                self._run("salesforce", self.search_salesforce(account_name))
            )

            if custom_urls:
                tasks["custom_urls"] = tg.create_task(
                    self._run("custom_urls", self.scrape_custom_urls(custom_urls))
                )

        return {name: task.result() for name, task in tasks.items()}

    async def _run(self, source_name: str, coro: Any) -> SourceResult:
        try:
            return await asyncio.wait_for(coro, timeout=_SOURCE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("Source %s timed out after %ds", source_name, _SOURCE_TIMEOUT_SECONDS)
            return SourceResult(source_name=source_name, status="timeout")
        except Exception as exc:
            logger.exception("Source %s failed", source_name)
            return SourceResult(source_name=source_name, status="failed", error=str(exc))

    # ── Web scraping ─────────────────────────────────────────────────────

    async def scrape_company_website(self, website: str) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="company_website", status="skipped", error="FIRECRAWL_API_KEY not set")
        scraped = await fc.async_scrape_url(website)
        return SourceResult(
            source_name="company_website",
            status="success",
            data={"title": scraped.title, "content": scraped.content[:8000], "url": website},
        )

    async def search_crunchbase(self, company_name: str) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="crunchbase", status="skipped", error="FIRECRAWL_API_KEY not set")
        # Use Firecrawl search instead of direct scrape — more reliable than slug guessing
        results = await fc.async_search(f"site:crunchbase.com {company_name} funding employees", limit=3)
        hits = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
        return SourceResult(source_name="crunchbase", status="success", data={"results": hits})

    async def search_news(self, company_name: str) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="news", status="skipped", error="FIRECRAWL_API_KEY not set")
        results = await fc.async_search(
            f"{company_name} database infrastructure expansion funding 2024 2025", limit=5
        )
        hits = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
        return SourceResult(source_name="news", status="success", data={"results": hits})

    async def search_job_postings(self, company_name: str) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="job_postings", status="skipped", error="FIRECRAWL_API_KEY not set")
        results = await fc.async_search(
            f"{company_name} hiring database engineer DBA platform engineer site:linkedin.com OR site:greenhouse.io OR site:lever.co",
            limit=5,
        )
        hits = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
        return SourceResult(source_name="job_postings", status="success", data={"results": hits})

    async def search_reviews(self, company_name: str) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="reviews", status="skipped", error="FIRECRAWL_API_KEY not set")
        results = await fc.async_search(
            f"{company_name} database review site:g2.com OR site:trustradius.com", limit=3
        )
        hits = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
        return SourceResult(source_name="reviews", status="success", data={"results": hits})

    async def scrape_custom_urls(self, urls: list[str]) -> SourceResult:
        fc = _get_firecrawl(self._settings)
        if not fc:
            return SourceResult(source_name="custom_urls", status="skipped", error="FIRECRAWL_API_KEY not set")
        results = []
        for url in urls:
            try:
                scraped = await fc.async_scrape_url(url)
                results.append({"url": url, "title": scraped.title, "content": scraped.content[:4000]})
            except Exception as exc:
                results.append({"url": url, "error": str(exc)})
        return SourceResult(source_name="custom_urls", status="success", data={"pages": results})

    # ── Free OSINT ────────────────────────────────────────────────────────

    async def search_edgar(self, company_name: str) -> SourceResult:
        try:
            from app.services.connectors.edgar import fetch_edgar_data
            data = await asyncio.to_thread(fetch_edgar_data, company_name)
            return SourceResult(source_name="edgar", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="edgar", status="failed", error=str(exc))

    async def search_hn(self, company_name: str) -> SourceResult:
        try:
            from app.services.connectors.hn import search_company as hn_search
            data = await asyncio.to_thread(hn_search, company_name)
            return SourceResult(source_name="hn", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="hn", status="failed", error=str(exc))

    # ── Paid OSINT ────────────────────────────────────────────────────────

    async def search_builtwith(self, domain: str) -> SourceResult:
        if not self._settings.builtwith_api_key:
            return SourceResult(source_name="builtwith", status="skipped", error="BUILTWITH_API_KEY not set")
        try:
            from app.services.connectors.builtwith import fetch_builtwith_data
            # Strip protocol/path to get bare domain
            domain_clean = re.sub(r"^https?://", "", domain).split("/")[0]
            data = await asyncio.to_thread(fetch_builtwith_data, self._settings.builtwith_api_key, domain_clean)
            return SourceResult(source_name="builtwith", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="builtwith", status="failed", error=str(exc))

    # ── Internal data ─────────────────────────────────────────────────────

    async def search_chorus_calls(self, account_name: str) -> SourceResult:
        try:
            from app.models.entities import ChorusCall
            calls = (
                self._db.query(ChorusCall)
                .filter(ChorusCall.account.ilike(f"%{account_name}%"))
                .order_by(ChorusCall.date.desc())
                .limit(10)
                .all()
            )
            call_data = [
                {
                    "chorus_call_id": c.chorus_call_id,
                    "date": str(c.date),
                    "account": c.account,
                    "opportunity": c.opportunity,
                    "stage": c.stage,
                    "rep_email": c.rep_email,
                }
                for c in calls
            ]
            return SourceResult(source_name="chorus_calls", status="success", data={"calls": call_data})
        except Exception as exc:
            return SourceResult(source_name="chorus_calls", status="failed", error=str(exc))

    async def search_salesforce(self, account_name: str) -> SourceResult:
        try:
            from app.services.crm.salesforce import SalesforceConnector
            from app.models.entities import SystemConfig
            config = self._db.query(SystemConfig).filter_by(config_key="salesforce_credentials").first()
            if not config or not config.config_value_plain:
                return SourceResult(source_name="salesforce", status="skipped", error="No Salesforce credentials configured")
            creds = config.config_value_plain
            connector = SalesforceConnector(
                instance_url=creds.get("instance_url", ""),
                access_token=creds.get("access_token", ""),
            )
            account = await connector.search_by_name(account_name)
            return SourceResult(
                source_name="salesforce",
                status="success",
                data={"account": account} if account else {},
            )
        except Exception as exc:
            return SourceResult(source_name="salesforce", status="failed", error=str(exc))
