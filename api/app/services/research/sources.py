from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings

# Forward-compatible imports for Phase 2/3 modules.
# These modules may not exist yet but will be created in parallel phases.
try:
    from app.services.connectors.firecrawl import FirecrawlConnector
except ImportError:  # pragma: no cover
    FirecrawlConnector = None  # type: ignore[assignment,misc]

try:
    from app.services.connectors.chorus import ChorusConnector
except ImportError:  # pragma: no cover
    ChorusConnector = None  # type: ignore[assignment,misc]

try:
    from app.services.crm.salesforce import SalesforceConnector
except ImportError:  # pragma: no cover
    SalesforceConnector = None  # type: ignore[assignment,misc]

try:
    from app.services.indexing.retrieval import HybridRetrievalService
except ImportError:  # pragma: no cover
    HybridRetrievalService = None  # type: ignore[assignment,misc]


logger = logging.getLogger(__name__)

_SOURCE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SourceResult:
    source_name: str
    status: str  # "success" | "failed" | "timeout"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _slugify(name: str) -> str:
    """Convert a company name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class ResearchSourceRunner:
    """Orchestrates fan-out research across all active data sources.

    Each source runs independently with a per-source timeout so that a
    single slow source does not block the rest.
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
        """Execute all source queries concurrently and return results keyed by source name."""
        tasks: dict[str, asyncio.Task[SourceResult]] = {}

        async with asyncio.TaskGroup() as tg:
            if website:
                tasks["company_website"] = tg.create_task(
                    self._run_with_timeout("company_website", self.scrape_company_website(website))
                )
            tasks["zoominfo"] = tg.create_task(
                self._run_with_timeout("zoominfo", self.search_zoominfo(account_name))
            )
            tasks["linkedin"] = tg.create_task(
                self._run_with_timeout("linkedin", self.search_linkedin(account_name))
            )
            tasks["crunchbase"] = tg.create_task(
                self._run_with_timeout("crunchbase", self.search_crunchbase(account_name))
            )
            tasks["news"] = tg.create_task(
                self._run_with_timeout("news", self.search_news(account_name))
            )
            tasks["job_postings"] = tg.create_task(
                self._run_with_timeout("job_postings", self.search_job_postings(account_name))
            )
            tasks["reviews"] = tg.create_task(
                self._run_with_timeout("reviews", self.search_reviews(account_name))
            )
            tasks["salesforce"] = tg.create_task(
                self._run_with_timeout("salesforce", self.search_salesforce(account_name))
            )
            tasks["chorus_calls"] = tg.create_task(
                self._run_with_timeout("chorus_calls", self.search_chorus_calls(account_name))
            )
            tasks["internal_docs"] = tg.create_task(
                self._run_with_timeout(
                    "internal_docs", self.search_internal_docs(account_name, org_id)
                )
            )
            tasks["tidb_docs"] = tg.create_task(
                self._run_with_timeout("tidb_docs", self.search_tidb_docs(account_name))
            )
            if custom_urls:
                tasks["custom_urls"] = tg.create_task(
                    self._run_with_timeout("custom_urls", self.scrape_custom_urls(custom_urls))
                )

        return {name: task.result() for name, task in tasks.items()}

    async def _run_with_timeout(
        self, source_name: str, coro: Any
    ) -> SourceResult:
        try:
            return await asyncio.wait_for(coro, timeout=_SOURCE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("Source %s timed out after %ds", source_name, _SOURCE_TIMEOUT_SECONDS)
            return SourceResult(source_name=source_name, status="timeout")
        except Exception as exc:
            logger.exception("Source %s failed", source_name)
            return SourceResult(source_name=source_name, status="failed", error=str(exc))

    # ------------------------------------------------------------------
    # Individual source methods
    # ------------------------------------------------------------------

    async def scrape_company_website(self, website: str) -> SourceResult:
        """Scrape the company website via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="company_website", status="failed", error="FirecrawlConnector not available")
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        data = await connector.scrape(website)
        return SourceResult(source_name="company_website", status="success", data=data)

    async def search_zoominfo(self, company_name: str) -> SourceResult:
        """Search ZoomInfo for company data via connector."""
        # ZoomInfo connector will be provided by Phase 3
        return SourceResult(
            source_name="zoominfo",
            status="failed",
            error="ZoomInfo connector not yet implemented",
        )

    async def search_linkedin(self, company_name: str) -> SourceResult:
        """Search LinkedIn for company data via connector."""
        # LinkedIn connector will be provided by Phase 3
        return SourceResult(
            source_name="linkedin",
            status="failed",
            error="LinkedIn connector not yet implemented",
        )

    async def search_crunchbase(self, company_name: str) -> SourceResult:
        """Scrape Crunchbase company page via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="crunchbase", status="failed", error="FirecrawlConnector not available")
        slug = _slugify(company_name)
        url = f"https://www.crunchbase.com/organization/{slug}"
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        try:
            data = await connector.scrape(url)
            return SourceResult(source_name="crunchbase", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="crunchbase", status="failed", error=str(exc))

    async def search_news(self, company_name: str) -> SourceResult:
        """Search Google News for recent company mentions via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="news", status="failed", error="FirecrawlConnector not available")
        url = f"https://news.google.com/search?q={company_name}"
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        try:
            data = await connector.scrape(url)
            return SourceResult(source_name="news", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="news", status="failed", error=str(exc))

    async def search_job_postings(self, company_name: str) -> SourceResult:
        """Search Indeed/LinkedIn jobs via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="job_postings", status="failed", error="FirecrawlConnector not available")
        url = f"https://www.indeed.com/jobs?q={company_name}"
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        try:
            data = await connector.scrape(url)
            return SourceResult(source_name="job_postings", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="job_postings", status="failed", error=str(exc))

    async def search_reviews(self, company_name: str) -> SourceResult:
        """Search G2/TrustRadius for company reviews via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="reviews", status="failed", error="FirecrawlConnector not available")
        slug = _slugify(company_name)
        url = f"https://www.g2.com/products/{slug}/reviews"
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        try:
            data = await connector.scrape(url)
            return SourceResult(source_name="reviews", status="success", data=data)
        except Exception as exc:
            return SourceResult(source_name="reviews", status="failed", error=str(exc))

    async def search_salesforce(self, account_name: str) -> SourceResult:
        """Search Salesforce CRM for account data."""
        if SalesforceConnector is None:
            return SourceResult(source_name="salesforce", status="failed", error="SalesforceConnector not available")
        try:
            from app.models.entities import SystemConfig
            config = self._db.query(SystemConfig).filter_by(
                config_key="salesforce_credentials"
            ).first()
            if not config or not config.config_value_plain:
                return SourceResult(source_name="salesforce", status="failed", error="No Salesforce credentials configured")
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

    async def search_chorus_calls(self, account_name: str) -> SourceResult:
        """Search Chorus for call recordings related to this account."""
        if ChorusConnector is None:
            return SourceResult(source_name="chorus_calls", status="failed", error="ChorusConnector not available")
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

    async def search_internal_docs(self, company_name: str, org_id: int) -> SourceResult:
        """Search knowledge index (Google Drive / Feishu) for internal documents."""
        if HybridRetrievalService is None:
            return SourceResult(source_name="internal_docs", status="failed", error="HybridRetrievalService not available")
        try:
            retrieval = HybridRetrievalService(db=self._db, org_id=org_id)
            results = await retrieval.search(query=company_name, top_k=5)
            return SourceResult(
                source_name="internal_docs",
                status="success",
                data={"documents": results},
            )
        except Exception as exc:
            return SourceResult(source_name="internal_docs", status="failed", error=str(exc))

    async def search_tidb_docs(self, company_name: str) -> SourceResult:
        """Search TiDB documentation index for relevant content."""
        if HybridRetrievalService is None:
            return SourceResult(source_name="tidb_docs", status="failed", error="HybridRetrievalService not available")
        try:
            retrieval = HybridRetrievalService(db=self._db, org_id=0)
            results = await retrieval.search(
                query=f"TiDB {company_name} use case", top_k=5, source_filter="tidb_docs"
            )
            return SourceResult(
                source_name="tidb_docs",
                status="success",
                data={"documents": results},
            )
        except Exception as exc:
            return SourceResult(source_name="tidb_docs", status="failed", error=str(exc))

    async def scrape_custom_urls(self, urls: list[str]) -> SourceResult:
        """Scrape user-configured custom URLs via Firecrawl."""
        if FirecrawlConnector is None:
            return SourceResult(source_name="custom_urls", status="failed", error="FirecrawlConnector not available")
        connector = FirecrawlConnector(api_key=self._settings.openai_api_key or "")
        results: list[dict[str, Any]] = []
        for url in urls:
            try:
                data = await connector.scrape(url)
                results.append({"url": url, "status": "success", "data": data})
            except Exception as exc:
                results.append({"url": url, "status": "failed", "error": str(exc)})
        return SourceResult(source_name="custom_urls", status="success", data={"pages": results})
