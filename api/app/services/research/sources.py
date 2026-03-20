from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_SOURCE_TIMEOUT_SECONDS = 45
_WEB_SEARCH_TOOLS = [{"type": "web_search_preview"}]

_WEB_SEARCH_SYSTEM = (
    "You are a sales intelligence research assistant. "
    "Search the web and return factual, structured information useful for B2B sales preparation. "
    "Be concise. Focus on database technology, infrastructure, funding, headcount, and buying signals."
)


@dataclass(frozen=True)
class SourceResult:
    source_name: str
    status: str  # "success" | "failed" | "timeout" | "skipped"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


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
    """Fan-out research across all OSINT data sources.

    LinkedIn, news, job postings, Crunchbase, and tech stack all use
    OpenAI web_search_preview — no Firecrawl key required for these.
    Firecrawl is only used for direct website scraping (optional).
    EDGAR and HN Algolia are free with no API key.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()
        self._llm: Any = None

    def _get_llm(self):
        if self._llm is None:
            from app.services.llm import LLMService
            self._llm = LLMService()
        return self._llm

    async def _llm_web_search(self, prompt: str) -> str | None:
        """Call the LLM with web_search_preview to gather company intel."""
        llm = self._get_llm()
        return await asyncio.to_thread(
            llm._responses_text,
            _WEB_SEARCH_SYSTEM,
            prompt,
            None,
            _WEB_SEARCH_TOOLS,
        )

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
            # ── OpenAI web search sources (require OPENAI_API_KEY only) ──
            tasks["linkedin"] = tg.create_task(
                self._run("linkedin", self.search_linkedin(account_name))
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
            tasks["tech_stack"] = tg.create_task(
                self._run("tech_stack", self.search_tech_stack(account_name, website))
            )

            # ── Free OSINT (no API key) ───────────────────────────────────
            tasks["edgar"] = tg.create_task(
                self._run("edgar", self.search_edgar(account_name))
            )
            tasks["hn"] = tg.create_task(
                self._run("hn", self.search_hn(account_name))
            )

            # ── Firecrawl (optional — direct website scrape) ─────────────
            if website:
                tasks["company_website"] = tg.create_task(
                    self._run("company_website", self.scrape_company_website(website))
                )

            # ── Internal data ─────────────────────────────────────────────
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

    # ── OpenAI web search sources ─────────────────────────────────────────

    async def search_linkedin(self, company_name: str) -> SourceResult:
        prompt = (
            f"Search LinkedIn and other sources for '{company_name}' company profile. "
            f"Find: employee count, key executives (CTO, VP Engineering, Head of Data), "
            f"recent hires or departures, company description, headquarters, and industry. "
            f"Return structured facts."
        )
        result = await self._llm_web_search(prompt)
        if not result:
            return SourceResult(source_name="linkedin", status="failed", error="LLM returned no result")
        return SourceResult(source_name="linkedin", status="success", data={"summary": result})

    async def search_crunchbase(self, company_name: str) -> SourceResult:
        prompt = (
            f"Search Crunchbase and news for '{company_name}' funding history and company details. "
            f"Find: total funding raised, latest funding round (amount, date, investors), "
            f"valuation if known, number of employees, founding year, and key investors. "
            f"Return structured facts."
        )
        result = await self._llm_web_search(prompt)
        if not result:
            return SourceResult(source_name="crunchbase", status="failed", error="LLM returned no result")
        return SourceResult(source_name="crunchbase", status="success", data={"summary": result})

    async def search_news(self, company_name: str) -> SourceResult:
        prompt = (
            f"Search for recent news about '{company_name}' from the past 12 months. "
            f"Focus on: infrastructure or database announcements, cloud migration, "
            f"major product launches, acquisitions, leadership changes, or funding events "
            f"that might affect their technology buying decisions. "
            f"List the top 5 most relevant news items with dates."
        )
        result = await self._llm_web_search(prompt)
        if not result:
            return SourceResult(source_name="news", status="failed", error="LLM returned no result")
        return SourceResult(source_name="news", status="success", data={"summary": result})

    async def search_job_postings(self, company_name: str) -> SourceResult:
        prompt = (
            f"Search LinkedIn Jobs, Greenhouse, Lever, and Indeed for current open positions at '{company_name}' "
            f"in: database engineering, data infrastructure, data platform, DBA, backend/data engineering, "
            f"site reliability engineering, and cloud architecture. "
            f"Identify any specific database technologies mentioned in job descriptions (MySQL, PostgreSQL, Oracle, etc.). "
            f"This signals their current tech stack and infrastructure investment direction."
        )
        result = await self._llm_web_search(prompt)
        if not result:
            return SourceResult(source_name="job_postings", status="failed", error="LLM returned no result")
        return SourceResult(source_name="job_postings", status="success", data={"summary": result})

    async def search_tech_stack(self, company_name: str, website: str) -> SourceResult:
        domain = re.sub(r"^https?://", "", website or "").split("/")[0] if website else company_name.lower()
        prompt = (
            f"Search for '{company_name}' technology stack information from multiple sources:\n"
            f"1. Check builtwith.com for {domain} — what databases and infrastructure do they use?\n"
            f"2. Check stackshare.io for {company_name} — what's in their tech stack?\n"
            f"3. Search GitHub for {company_name} repositories mentioning MySQL, PostgreSQL, sharding, Vitess, or ProxySQL\n"
            f"4. Look for engineering blog posts about their database or infrastructure\n"
            f"Focus on: database systems (MySQL, PostgreSQL, Oracle, Aurora, MongoDB, etc.), "
            f"cloud provider, and any signs of scaling pain or migration activity."
        )
        result = await self._llm_web_search(prompt)
        if not result:
            return SourceResult(source_name="tech_stack", status="failed", error="LLM returned no result")
        return SourceResult(source_name="tech_stack", status="success", data={"summary": result})

    # ── Direct scrape (Firecrawl, optional) ──────────────────────────────

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
