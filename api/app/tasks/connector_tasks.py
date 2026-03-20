from __future__ import annotations

import asyncio
import logging

from app.core.settings import get_settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.worker import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="sync_chorus_connector")
def sync_chorus(org_id: int) -> dict:
    """Sync new Chorus calls for an organization."""
    init_db()
    from app.services.connectors.chorus import ChorusConnector
    from app.services.connectors.chorus_sync import ChorusSyncService

    api_key = settings.call_api_key or settings.chorus_api_key
    base_url = settings.call_base_url or settings.chorus_base_url or "https://chorus.ai/v3"

    if not api_key:
        from app.models.entities import User

        with SessionLocal() as db:
            users = db.query(User).filter(User.org_id == org_id).all()
            for u in users:
                accounts = u.connected_accounts or {}
                chorus = accounts.get("chorus", {})
                if isinstance(chorus, dict) and chorus.get("access_token"):
                    api_key = chorus["access_token"]
                    break

    if not api_key:
        return {"error": "Chorus API key or base URL not configured"}

    async def _sync():
        connector = ChorusConnector(api_key=api_key, base_url=base_url)
        try:
            with SessionLocal() as db:
                svc = ChorusSyncService(connector=connector, db=db)
                result = await svc.sync_new_calls(org_id)
                return {
                    "calls_fetched": result.calls_fetched,
                    "calls_stored": result.calls_stored,
                    "transcripts_indexed": result.transcripts_indexed,
                    "artifacts_created": result.artifacts_created,
                    "errors": result.errors,
                }
        finally:
            await connector.close()

    return _run_async(_sync())


@celery_app.task(name="sync_salesforce_connector")
def sync_salesforce(org_id: int, instance_url: str, access_token: str) -> dict:
    """Sync accounts, deals, and contacts from Salesforce."""
    init_db()
    from app.services.connectors.salesforce_sync import SalesforceSyncService

    async def _sync():
        with SessionLocal() as db:
            svc = SalesforceSyncService(db=db)
            result = await svc.sync_all(
                org_id=org_id,
                instance_url=instance_url,
                access_token=access_token,
            )
            return {
                "accounts_synced": result.accounts_synced,
                "deals_synced": result.deals_synced,
                "contacts_synced": result.contacts_synced,
                "errors": result.errors,
            }

    return _run_async(_sync())


@celery_app.task(name="scrape_urls_connector")
def scrape_urls(urls: list[str], org_id: int) -> dict:
    """Scrape URLs via Firecrawl and return content."""
    init_db()
    from app.services.connectors.firecrawl import FirecrawlConnector

    api_key = settings.openai_api_key
    firecrawl_key = getattr(settings, "firecrawl_api_key", None) or api_key

    if not firecrawl_key:
        return {"error": "Firecrawl API key not configured"}

    connector = FirecrawlConnector(api_key=firecrawl_key)
    results = connector.scrape_urls(urls)
    return {
        "scraped": len(results),
        "pages": [
            {
                "url": r.url,
                "title": r.title,
                "content_length": len(r.content),
                "has_error": r.metadata.get("error", False),
            }
            for r in results
        ],
    }
