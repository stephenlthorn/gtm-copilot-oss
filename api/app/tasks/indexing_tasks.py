from __future__ import annotations

import asyncio
import logging

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.indexing.embedder import EmbeddingService
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(name="sync_google_drive_v2")
def sync_google_drive(user_id: int | None = None, org_id: int = 1) -> dict:
    init_db()
    from app.services.indexing.drive_indexer import DriveIndexer

    with SessionLocal() as db:
        embedding_service = EmbeddingService()
        indexer = DriveIndexer(db, embedding_service)

        user_credentials = None
        if user_id is not None:
            from app.models.entities import User
            from app.services.google_drive_credentials import GoogleDriveCredentialService
            user = db.execute(
                __import__("sqlalchemy").select(User).where(User.id == user_id)
            ).scalar_one_or_none()
            if user is not None:
                cred_service = GoogleDriveCredentialService(db)
                try:
                    user_credentials = cred_service.get_google_credentials(user.email)
                except Exception as exc:
                    logger.warning("Could not load Drive credentials for user %s: %s", user.email, exc)

        result = _run_async(indexer.sync(user_credentials=user_credentials, org_id=org_id))

    return {
        "docs_indexed": result.docs_indexed,
        "chunks_indexed": result.chunks_indexed,
        "errors": result.errors,
    }


@celery_app.task(name="sync_feishu_v2")
def sync_feishu(org_id: int = 1) -> dict:
    init_db()
    from app.services.indexing.feishu_indexer import FeishuIndexer

    with SessionLocal() as db:
        embedding_service = EmbeddingService()
        indexer = FeishuIndexer(db, embedding_service)
        result = _run_async(indexer.sync(org_id=org_id))

    return {
        "docs_indexed": result.docs_indexed,
        "chunks_indexed": result.chunks_indexed,
        "errors": result.errors,
    }


@celery_app.task(name="sync_tidb_docs_v2")
def sync_tidb_docs(org_id: int = 1) -> dict:
    init_db()
    from app.services.indexing.docs_indexer import DocsIndexer

    with SessionLocal() as db:
        embedding_service = EmbeddingService()
        indexer = DocsIndexer(db, embedding_service)
        result = _run_async(indexer.sync(org_id=org_id))

    return {
        "docs_indexed": result.docs_indexed,
        "chunks_indexed": result.chunks_indexed,
        "errors": result.errors,
    }


@celery_app.task(name="sync_github_v2")
def sync_github(org_id: int = 1) -> dict:
    init_db()
    from app.services.indexing.github_indexer import GitHubIndexer

    with SessionLocal() as db:
        embedding_service = EmbeddingService()
        indexer = GitHubIndexer(db, embedding_service)
        result = _run_async(indexer.sync(org_id=org_id))

    return {
        "docs_indexed": result.docs_indexed,
        "chunks_indexed": result.chunks_indexed,
        "errors": result.errors,
    }


@celery_app.task(name="full_reindex_v2")
def full_reindex(org_id: int = 1) -> dict:
    init_db()
    results: dict[str, dict] = {}

    try:
        results["google_drive"] = sync_google_drive(org_id=org_id)
    except Exception as exc:
        logger.error("full_reindex: google_drive failed: %s", exc)
        results["google_drive"] = {"error": str(exc)}

    try:
        results["feishu"] = sync_feishu(org_id=org_id)
    except Exception as exc:
        logger.error("full_reindex: feishu failed: %s", exc)
        results["feishu"] = {"error": str(exc)}

    try:
        results["tidb_docs"] = sync_tidb_docs(org_id=org_id)
    except Exception as exc:
        logger.error("full_reindex: tidb_docs failed: %s", exc)
        results["tidb_docs"] = {"error": str(exc)}

    try:
        results["github"] = sync_github(org_id=org_id)
    except Exception as exc:
        logger.error("full_reindex: github failed: %s", exc)
        results["github"] = {"error": str(exc)}

    return results
