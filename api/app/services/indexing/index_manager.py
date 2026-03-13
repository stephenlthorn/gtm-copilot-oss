from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.entities import (
    KnowledgeIndex,
    SyncSourceType,
    SyncStatus,
    SyncStatusEnum,
)
from app.services.indexing.chunker import chunk_text
from app.services.indexing.embedder import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    docs_indexed: int = 0
    chunks_indexed: int = 0
    errors: list[str] | None = None


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IndexManager:
    def __init__(self, db: Session, embedding_service: EmbeddingService) -> None:
        self.db = db
        self.embedding_service = embedding_service

    async def index_document(
        self,
        source_type: SyncSourceType,
        source_ref: str,
        title: str,
        content: str,
        metadata: dict | None,
        org_id: int,
        chunk_strategy: str = "paragraph",
        max_tokens: int = 500,
        overlap_tokens: int = 50,
    ) -> int:
        self.delete_document(source_type, source_ref, org_id)

        chunks = chunk_text(
            content,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            strategy=chunk_strategy,
        )

        if not chunks:
            return 0

        chunk_texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_chunks(chunk_texts)

        rows: list[KnowledgeIndex] = []
        for chunk, embedding in zip(chunks, embeddings):
            row = KnowledgeIndex(
                source_type=source_type,
                source_ref=source_ref,
                title=title,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
                embedding=json.dumps(embedding),
                embedding_model=self.embedding_service.settings.openai_embedding_model,
                metadata_=metadata or {},
                org_id=org_id,
            )
            rows.append(row)

        self.db.add_all(rows)
        self.db.commit()

        logger.info(
            "Indexed %d chunks for source_ref=%s (type=%s, org=%d)",
            len(rows),
            source_ref,
            source_type.value,
            org_id,
        )
        return len(rows)

    def delete_document(
        self,
        source_type: SyncSourceType,
        source_ref: str,
        org_id: int,
    ) -> int:
        stmt = delete(KnowledgeIndex).where(
            KnowledgeIndex.source_type == source_type,
            KnowledgeIndex.source_ref == source_ref,
            KnowledgeIndex.org_id == org_id,
        )
        result = self.db.execute(stmt)
        self.db.commit()
        deleted = result.rowcount
        if deleted:
            logger.info(
                "Deleted %d existing chunks for source_ref=%s (type=%s, org=%d)",
                deleted,
                source_ref,
                source_type.value,
                org_id,
            )
        return deleted

    def update_sync_status(
        self,
        source_type: SyncSourceType,
        org_id: int,
        status: SyncStatusEnum,
        docs_indexed: int = 0,
        chunks_indexed: int = 0,
        error_message: str | None = None,
    ) -> None:
        existing = self.db.execute(
            select(SyncStatus).where(
                SyncStatus.source_type == source_type,
                SyncStatus.org_id == org_id,
            )
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if existing is not None:
            values: dict = {
                "status": status,
                "error_message": error_message,
            }
            if status == SyncStatusEnum.idle:
                values["last_sync_at"] = now
                values["docs_indexed"] = docs_indexed
                values["chunks_indexed"] = chunks_indexed
            self.db.execute(
                update(SyncStatus)
                .where(SyncStatus.id == existing.id)
                .values(**values)
            )
        else:
            row = SyncStatus(
                source_type=source_type,
                org_id=org_id,
                status=status,
                docs_indexed=docs_indexed,
                chunks_indexed=chunks_indexed,
                error_message=error_message,
                last_sync_at=now if status == SyncStatusEnum.idle else None,
            )
            self.db.add(row)

        self.db.commit()
