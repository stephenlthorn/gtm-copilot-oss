from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from app.services.connectors.web_scraper import WebScraper

logger = logging.getLogger(__name__)

_MAX_FIELD_CHARS = 2000
_SCRAPE_TIMEOUT_SECONDS = 10


@dataclass
class AccountBriefContext:
    company_homepage: str = ""
    company_about: str = ""
    crunchbase: str = ""
    stackshare: str = ""
    job_signals: str = ""
    prospect_profile: str = ""


class AccountBriefResearcher:
    """Concurrently scrapes multiple web sources to build research context
    for a 7-section account brief."""

    def __init__(self, connector: WebScraper | None = None) -> None:
        self._connector = connector or WebScraper()

    async def research(
        self,
        account_name: str,
        website: str | None,
        linkedin_url: str | None,
    ) -> AccountBriefContext:
        slug = self._slug(account_name)

        url_map: dict[str, str] = {}
        if website:
            base = website.rstrip("/")
            url_map["company_homepage"] = base
            url_map["company_about"] = f"{base}/about"
        url_map["crunchbase"] = f"https://www.crunchbase.com/organization/{slug}"
        url_map["stackshare"] = f"https://stackshare.io/{slug}"
        url_map["job_signals"] = (
            f"https://www.linkedin.com/jobs/search/?keywords={quote(account_name)}&f_TPR=r604800"
        )
        if linkedin_url:
            url_map["prospect_profile"] = linkedin_url

        results = await asyncio.gather(
            *[self._scrape(key, url) for key, url in url_map.items()],
            return_exceptions=True,
        )

        ctx = AccountBriefContext()
        for item in results:
            if isinstance(item, tuple):
                key, content = item
                object.__setattr__(ctx, key, content) if hasattr(ctx, key) else None
                setattr(ctx, key, content)

        return ctx

    async def _scrape(self, field_name: str, url: str) -> tuple[str, str]:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._connector.scrape_url, url),
                timeout=_SCRAPE_TIMEOUT_SECONDS,
            )
            content = (result.content or "")[:_MAX_FIELD_CHARS]
            return field_name, content
        except Exception:
            logger.debug("Scrape failed for field=%s url=%s", field_name, url)
            return field_name, ""

    @staticmethod
    def _slug(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
