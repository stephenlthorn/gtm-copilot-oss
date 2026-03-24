from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import SyncSourceType, SyncStatusEnum
from app.services.indexing.embedder import EmbeddingService
from app.services.indexing.index_manager import IndexManager, SyncResult

logger = logging.getLogger(__name__)

_DOCS_BASE_URL = "https://docs.pingcap.com"

_SEED_PATHS = [
    "/tidb/stable/overview",
    "/tidb/stable/quick-start-with-tidb",
    "/tidb/stable/tidb-architecture",
    "/tidb/stable/sql-statements",
    "/tidb/stable/mysql-compatibility",
    "/tidb/stable/transaction-overview",
    "/tidb/stable/tiflash-overview",
    "/tidb/stable/data-migration-overview",
    "/tidb/stable/tidb-cloud/tidb-cloud-intro",
    "/tidb/stable/performance-tuning-overview",
    "/tidb/stable/backup-and-restore-overview",
    "/tidb/stable/security-overview",
    "/tidb/stable/monitoring-and-alert-overview",
]


class DocsIndexer:
    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.embedding_service = embedding_service or EmbeddingService()
        self.index_manager = IndexManager(db, self.embedding_service)

    async def sync(self, org_id: int = 1) -> SyncResult:
        source_type = SyncSourceType.tidb_docs

        self.index_manager.update_sync_status(
            source_type=source_type,
            org_id=org_id,
            status=SyncStatusEnum.syncing,
        )

        errors: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        try:
            pages = await self._crawl_pages()

            for page in pages:
                url = page["url"]
                title = page["title"]
                content = page["content"]

                if not content.strip():
                    continue

                try:
                    source_ref = url.replace(_DOCS_BASE_URL, "").strip("/") or url
                    metadata = {"url": url}

                    count = await self.index_manager.index_document(
                        source_type=source_type,
                        source_ref=source_ref,
                        title=title,
                        content=content,
                        metadata=metadata,
                        org_id=org_id,
                        chunk_strategy="section",
                    )
                    docs_indexed += 1
                    chunks_indexed += count
                except Exception as exc:
                    msg = f"Failed to index doc page {url}: {exc}"
                    logger.error(msg)
                    errors.append(msg)

            self.index_manager.update_sync_status(
                source_type=source_type,
                org_id=org_id,
                status=SyncStatusEnum.idle,
                docs_indexed=docs_indexed,
                chunks_indexed=chunks_indexed,
            )

        except Exception as exc:
            error_msg = f"TiDB docs sync failed: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            self.index_manager.update_sync_status(
                source_type=source_type,
                org_id=org_id,
                status=SyncStatusEnum.error,
                error_message=error_msg,
            )

        return SyncResult(
            docs_indexed=docs_indexed,
            chunks_indexed=chunks_indexed,
            errors=errors if errors else None,
        )

    async def _crawl_pages(self) -> list[dict]:
        pages: list[dict] = []

        if await self._try_firecrawl(pages):
            return pages

        await self._crawl_httpx(pages)
        return pages

    async def _try_firecrawl(self, pages: list[dict]) -> bool:
        try:
            from app.services.connectors.web_scraper import WebScraper

            scraper = WebScraper()
            for path in _SEED_PATHS:
                url = urljoin(_DOCS_BASE_URL, path)
                try:
                    result = scraper.scrape_url(url)
                    if result.content.strip():
                        pages.append({"url": url, "title": result.title, "content": result.content})
                except Exception as exc:
                    logger.warning("Scrape failed for %s: %s", url, exc)
            return True
        except Exception as exc:
            logger.warning("WebScraper init failed: %s, falling back to httpx", exc)
            return False

    async def _crawl_httpx(self, pages: list[dict]) -> None:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for path in _SEED_PATHS:
                url = urljoin(_DOCS_BASE_URL, path)
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    text = resp.text

                    title = url
                    title_match = _extract_title(text)
                    if title_match:
                        title = title_match

                    content = _extract_body_text(text)
                    if content.strip():
                        pages.append({"url": url, "title": title, "content": content})
                except Exception as exc:
                    logger.warning("httpx crawl failed for %s: %s", url, exc)


def _extract_title(html: str) -> str | None:
    import re
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_body_text(html: str) -> str:
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
