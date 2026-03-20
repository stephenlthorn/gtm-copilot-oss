from __future__ import annotations

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


class FirecrawlConnector:
    """Scrapes web pages using the Firecrawl SDK."""

    def __init__(self, api_key: str) -> None:
        self._app = FirecrawlApp(api_key=api_key)

    def scrape_url(self, url: str) -> ScrapedContent:
        result = self._app.scrape_url(url, params={"formats": ["markdown"]})
        return self._parse_result(url, result)

    def scrape_urls(self, urls: list[str]) -> list[ScrapedContent]:
        scraped: list[ScrapedContent] = []
        for url in urls:
            try:
                scraped.append(self.scrape_url(url))
            except Exception:
                logger.warning("Failed to scrape %s", url, exc_info=True)
                scraped.append(
                    ScrapedContent(
                        url=url,
                        title="(Scrape Failed)",
                        content="",
                        metadata={"error": True},
                    )
                )
        return scraped

    @staticmethod
    def _parse_result(url: str, result: dict) -> ScrapedContent:
        metadata = result.get("metadata", {})
        title = metadata.get("title", "") or metadata.get("ogTitle", "") or url
        content = result.get("markdown", "") or result.get("content", "")
        return ScrapedContent(
            url=url,
            title=title,
            content=content,
            metadata=metadata,
        )
