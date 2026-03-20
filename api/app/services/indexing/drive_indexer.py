from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.drive_connector import DriveConnector
from app.models.entities import SyncSourceType, SyncStatus, SyncStatusEnum
from app.services.indexing.embedder import EmbeddingService
from app.services.indexing.index_manager import IndexManager, SyncResult

logger = logging.getLogger(__name__)


class DriveIndexer:
    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None) -> None:
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()
        self.index_manager = IndexManager(db, self.embedding_service)

    async def sync(
        self,
        user_credentials=None,
        org_id: int = 1,
    ) -> SyncResult:
        source_type = SyncSourceType.google_drive

        self.index_manager.update_sync_status(
            source_type=source_type,
            org_id=org_id,
            status=SyncStatusEnum.syncing,
        )

        errors: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        try:
            last_sync = self._get_last_sync_time(source_type, org_id)
            connector = DriveConnector(oauth_credentials=user_credentials)
            files = connector.list_files(since=last_sync)

            for drive_file in files:
                try:
                    metadata = {
                        "mime_type": drive_file.mime,
                        "owner": drive_file.owner,
                        "url": drive_file.url,
                        "drive_file_id": drive_file.drive_file_id,
                        "path": drive_file.path,
                    }

                    strategy = self._pick_chunk_strategy(drive_file.mime)

                    count = await self.index_manager.index_document(
                        source_type=source_type,
                        source_ref=drive_file.drive_file_id,
                        title=drive_file.title,
                        content=drive_file.content,
                        metadata=metadata,
                        org_id=org_id,
                        chunk_strategy=strategy,
                    )
                    docs_indexed += 1
                    chunks_indexed += count
                except Exception as exc:
                    msg = f"Failed to index Drive file {drive_file.title}: {exc}"
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
            error_msg = f"Drive sync failed: {exc}"
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

    def _get_last_sync_time(self, source_type: SyncSourceType, org_id: int) -> datetime | None:
        row = self.db.execute(
            select(SyncStatus).where(
                SyncStatus.source_type == source_type,
                SyncStatus.org_id == org_id,
            )
        ).scalar_one_or_none()
        if row is not None and row.last_sync_at is not None:
            return row.last_sync_at
        return None

    @staticmethod
    def _pick_chunk_strategy(mime_type: str) -> str:
        if "presentation" in mime_type or "slides" in mime_type:
            return "section"
        if "spreadsheet" in mime_type or "csv" in mime_type:
            return "paragraph"
        if "markdown" in mime_type:
            return "section"
        return "paragraph"
