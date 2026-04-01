from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.entities import SyncStatus

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_SOURCES = {"google_drive", "chorus", "tidb_docs", "tidb_github"}


@router.get("/search")
async def knowledge_search(
    q: str = Query(..., min_length=2, description="Search query"),
    org_id: int = Query(default=1, description="Organization ID"),
    top_k: int = Query(default=10, ge=1, le=50, description="Number of results"),
    source_types: str | None = Query(default=None, description="Comma-separated source types"),
    db: Session = Depends(db_session),
) -> dict:
    from app.services.indexing.embedder import EmbeddingService
    from app.services.indexing.retrieval import HybridRetrievalService

    parsed_source_types: list[str] | None = None
    if source_types:
        parsed_source_types = [s.strip() for s in source_types.split(",") if s.strip()]

    embedding_service = EmbeddingService()
    retrieval = HybridRetrievalService(db, embedding_service)

    results = await retrieval.search(
        query=q,
        org_id=org_id,
        top_k=top_k,
        source_types=parsed_source_types,
    )

    return {
        "query": q,
        "results": [
            {
                "chunk_text": r.chunk_text,
                "source_type": r.source_type,
                "source_ref": r.source_ref,
                "title": r.title,
                "score": round(r.score, 6),
                "metadata": r.metadata,
            }
            for r in results
        ],
    }


@router.get("/sync-status")
def sync_status(
    org_id: int = Query(default=1, description="Organization ID"),
    db: Session = Depends(db_session),
) -> dict:
    rows = db.execute(
        select(SyncStatus).where(SyncStatus.org_id == org_id)
    ).scalars().all()

    statuses: list[dict] = []
    for row in rows:
        source_value = row.source_type.value if hasattr(row.source_type, "value") else str(row.source_type)
        statuses.append({
            "source_type": source_value,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "docs_indexed": row.docs_indexed,
            "chunks_indexed": row.chunks_indexed,
            "error_message": row.error_message,
        })

    return {"org_id": org_id, "sources": statuses}


@router.post("/sync/{source}")
def trigger_sync(
    source: str,
    org_id: int = Query(default=1, description="Organization ID"),
    user_id: int | None = Query(default=None, description="User ID for Drive sync"),
) -> dict:
    if source not in _VALID_SOURCES and source != "all":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {source}. Must be one of: {sorted(_VALID_SOURCES)} or 'all'",
        )

    from app.tasks.indexing_tasks import (
        full_reindex,
        sync_github,
        sync_google_drive,
        sync_tidb_docs,
    )

    task_map = {
        "google_drive": lambda: sync_google_drive.delay(user_id=user_id, org_id=org_id),
        "tidb_docs": lambda: sync_tidb_docs.delay(org_id=org_id),
        "tidb_github": lambda: sync_github.delay(org_id=org_id),
        "all": lambda: full_reindex.delay(org_id=org_id),
    }

    launcher = task_map.get(source)
    if launcher is None:
        raise HTTPException(status_code=400, detail=f"No task configured for source: {source}")

    task = launcher()

    return {
        "message": f"Sync triggered for {source}",
        "task_id": task.id,
        "org_id": org_id,
    }
