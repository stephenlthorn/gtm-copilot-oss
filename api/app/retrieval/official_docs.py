"""Live official-product documentation retriever.

Searches a configurable docs domain via DuckDuckGo Lite (no API key needed)
and fetches top result pages as RetrievedChunk objects.
All errors are swallowed; callers always get a (possibly empty) list.
"""
from __future__ import annotations

import logging
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import httpx

from app.models.entities import SourceType
from app.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
_DDG_HTML_URL = "https://duckduckgo.com/html/"
_SEARCH_TIMEOUT = 8.0
_FETCH_TIMEOUT = 6.0
_USER_AGENT = "Mozilla/5.0 (compatible; GTM-Copilot/1.0; +https://example.com)"
_ONLINE_SCORE = 0.72  # Fixed relevance score for online docs hits.
_DEFAULT_DOC_URLS = [
    "https://docs.example.com/product/stable/overview",
    "https://docs.example.com/product/stable/architecture",
    "https://docs.example.com/product/stable/compatibility",
]
_KEYWORD_DOC_URLS = [
    ("migration", "https://docs.example.com/product/stable/migration-overview"),
    ("ddl", "https://docs.example.com/product/stable/online-ddl"),
    ("storage", "https://docs.example.com/product/stable/storage"),
    ("architecture", "https://docs.example.com/product/stable/architecture"),
    ("security", "https://docs.example.com/product/stable/security"),
    ("analytics", "https://docs.example.com/product/stable/analytics"),
    ("replication", "https://docs.example.com/product/stable/replication"),
    ("lag", "https://docs.example.com/product/stable/replication-observability"),
]


class _HrefCollector(HTMLParser):
    """Collect all href attribute values from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.append(value)


class _TextExtractor(HTMLParser):
    """Extract human-readable text from HTML, skipping script/style blocks."""

    _BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "td", "th", "dt", "dd", "blockquote"}
    _SKIP_TAGS = {"script", "style", "nav", "footer", "header"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_block = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag in self._BLOCK_TAGS:
            self._in_block = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in self._BLOCK_TAGS:
            self._in_block = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_block:
            stripped = data.strip()
            if stripped:
                self.chunks.append(stripped)


def _extract_doc_urls(html: str) -> list[str]:
    """Return deduplicated docs.example.com URLs found in *html*."""
    parser = _HrefCollector()
    parser.feed(html)
    seen: set[str] = set()
    result: list[str] = []
    for href in parser.hrefs:
        candidate = href
        if "uddg=" in href:
            query = parse_qs(urlparse(href).query)
            if query.get("uddg"):
                candidate = unquote(query["uddg"][0])
        if candidate.startswith("//"):
            candidate = f"https:{candidate}"
        if "docs.example.com" in candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def _extract_text_from_html(html: str, max_chars: int = 2_500) -> str:
    """Return visible article text from *html*, capped at *max_chars*."""
    parser = _TextExtractor()
    parser.feed(html)
    return " ".join(parser.chunks)[:max_chars]


class OfficialDocsRetriever:
    """Deterministically fetch official documentation for a query."""

    @staticmethod
    def _heuristic_docs_urls(query: str) -> list[str]:
        lowered = query.lower()
        urls: list[str] = []
        for keyword, url in _KEYWORD_DOC_URLS:
            if keyword in lowered and url not in urls:
                urls.append(url)
        for url in _DEFAULT_DOC_URLS:
            if url not in urls:
                urls.append(url)
        return urls

    def search(self, query: str, max_results: int = 3) -> list[RetrievedChunk]:
        """Return up to *max_results* RetrievedChunks from live product docs.

        Never raises — returns empty list on any failure.
        """
        try:
            urls = self._search_docs_urls(query)
            chunks: list[RetrievedChunk] = []
            for url in urls[:max_results]:
                try:
                    chunk = self._fetch_page(url)
                    if chunk is not None:
                        chunks.append(chunk)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("OfficialDocsRetriever: skipping %s (%s)", url, exc)
            return chunks
        except Exception as exc:  # noqa: BLE001
            logger.warning("OfficialDocsRetriever.search failed: %s", exc)
            return []

    def _search_docs_urls(self, query: str) -> list[str]:
        with httpx.Client(timeout=_SEARCH_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                _DDG_LITE_URL,
                params={"q": f"site:docs.example.com product {query}"},
                headers={"User-Agent": _USER_AGENT},
            )
            urls = _extract_doc_urls(resp.text)
            if urls:
                return urls
            # Some regions often get anti-bot 202 pages from the lite endpoint.
            html_resp = client.get(
                _DDG_HTML_URL,
                params={"q": f"site:docs.example.com product {query}"},
                headers={"User-Agent": _USER_AGENT},
            )
            urls = _extract_doc_urls(html_resp.text)
            if urls:
                return urls
        return self._heuristic_docs_urls(query)

    def _fetch_page(self, url: str) -> RetrievedChunk | None:
        with httpx.Client(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
        if resp.status_code != 200:
            return None
        text = _extract_text_from_html(resp.text)
        if len(text) < 80:
            return None
        slug = url.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").title() if slug else "Official Product Docs"
        return RetrievedChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            score=_ONLINE_SCORE,
            text=text,
            metadata={"source": SourceType.OFFICIAL_DOCS_ONLINE.value, "url": url},
            source_type=SourceType.OFFICIAL_DOCS_ONLINE.value,
            source_id=url,
            title=title,
            url=url,
            file_id=None,
        )


# Backward-compatible helper used by tests/imports.
def _extract_official_doc_urls(html: str) -> list[str]:
    return _extract_doc_urls(html)
