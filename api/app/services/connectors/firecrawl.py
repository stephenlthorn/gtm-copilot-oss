from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScrapedContent:
    url: str
    title: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    metadata: dict = field(default_factory=dict)


class FirecrawlConnector:
    """Scrapes and searches web pages using the Firecrawl SDK."""

    def __init__(self, api_key: str) -> None:
        self._app = FirecrawlApp(api_key=api_key)

    # ── Sync ────────────────────────────────────────────────────────────

    def scrape_url(self, url: str) -> ScrapedContent:
        result = self._app.scrape_url(url, params={"formats": ["markdown"]})
        return self._parse_scrape_result(url, result)

    def scrape_urls(self, urls: list[str]) -> list[ScrapedContent]:
        scraped: list[ScrapedContent] = []
        for url in urls:
            try:
                scraped.append(self.scrape_url(url))
            except Exception:
                logger.warning("Failed to scrape %s", url, exc_info=True)
                scraped.append(ScrapedContent(url=url, title="(Scrape Failed)", content="", metadata={"error": True}))
        return scraped

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        try:
            results = self._app.search(query, params={"limit": limit})
            items = results if isinstance(results, list) else (results.get("data") or [])
            return [self._parse_search_result(r) for r in items]
        except Exception:
            logger.warning("Firecrawl search failed for: %s", query, exc_info=True)
            return []

    # ── Async wrappers (for the async research pipeline) ────────────────

    async def async_scrape_url(self, url: str) -> ScrapedContent:
        return await asyncio.to_thread(self.scrape_url, url)

    async def async_search(self, query: str, limit: int = 5) -> list[SearchResult]:
        return await asyncio.to_thread(self.search, query, limit)

    # ── Parsers ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_scrape_result(url: str, result: dict) -> ScrapedContent:
        metadata = result.get("metadata", {})
        title = metadata.get("title", "") or metadata.get("ogTitle", "") or url
        content = result.get("markdown", "") or result.get("content", "")
        return ScrapedContent(url=url, title=title, content=content, metadata=metadata)

    @staticmethod
    def _parse_search_result(r: dict) -> SearchResult:
        return SearchResult(
            url=r.get("url", ""),
            title=r.get("title", ""),
            snippet=r.get("description", "") or r.get("markdown", "")[:300],
            metadata=r.get("metadata", {}),
        )
