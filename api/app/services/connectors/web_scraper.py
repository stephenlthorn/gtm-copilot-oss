from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 10
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


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


class _TextExtractor(HTMLParser):
    """Lightweight HTML-to-text converter. Strips scripts, styles, and tags."""

    _SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "path"})

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._title: str = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self._title:
            self._title = data.strip()
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        lines = [line.strip() for line in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line))

    def get_title(self) -> str:
        return self._title


class WebScraper:
    """Scrapes web pages using requests + HTML parsing. Zero external dependencies."""

    def scrape_url(self, url: str) -> ScrapedContent:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        extractor = _TextExtractor()
        extractor.feed(resp.text)

        title = extractor.get_title() or url
        content = extractor.get_text()

        description = ""
        og_title = ""
        for match in re.finditer(
            r'<meta\s+(?:name|property)=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
            resp.text[:5000],
            re.IGNORECASE,
        ):
            name, value = match.group(1).lower(), match.group(2)
            if name == "description":
                description = value
            elif name in ("og:title", "twitter:title"):
                og_title = value

        return ScrapedContent(
            url=url,
            title=og_title or title,
            content=content,
            metadata={"description": description, "og_title": og_title},
        )

    def scrape_urls(self, urls: list[str]) -> list[ScrapedContent]:
        scraped: list[ScrapedContent] = []
        for url in urls:
            try:
                scraped.append(self.scrape_url(url))
            except Exception:
                logger.warning("Failed to scrape %s", url, exc_info=True)
                scraped.append(ScrapedContent(url=url, title="(Scrape Failed)", content="", metadata={"error": True}))
        return scraped

    async def async_scrape_url(self, url: str) -> ScrapedContent:
        return await asyncio.to_thread(self.scrape_url, url)
