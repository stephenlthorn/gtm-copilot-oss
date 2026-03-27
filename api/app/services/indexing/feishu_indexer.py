from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.ingest.feishu_connector import FeishuConnector
from app.models.entities import SyncSourceType, SyncStatus, SyncStatusEnum
from app.services.indexing.embedder import EmbeddingService
from app.services.indexing.index_manager import IndexManager, SyncResult

logger = logging.getLogger(__name__)


class FeishuIndexer:
    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self._app_id = app_id or self.settings.feishu_app_id
        self._app_secret = app_secret or self.settings.feishu_app_secret
        self.embedding_service = embedding_service or EmbeddingService()
        self.index_manager = IndexManager(db, self.embedding_service)

    async def sync(self, org_id: int = 1) -> SyncResult:
        source_type = SyncSourceType.feishu

        self.index_manager.update_sync_status(
            source_type=source_type,
            org_id=org_id,
            status=SyncStatusEnum.syncing,
        )

        errors: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        try:
            connector = FeishuConnector(
                app_id=self._app_id,
                app_secret=self._app_secret,
                base_url=self.settings.feishu_base_url,
                access_token=self.settings.feishu_access_token or None,
            )

            root_tokens = self._get_root_tokens()
            doc_items = connector.list_documents(root_tokens, recursive=True)

            wiki_root_tokens = [
                t.strip() for t in (self.settings.feishu_wiki_root_tokens or "").split(",") if t.strip()
            ] or None

            wiki_items: list = []
            try:
                wiki_items = connector.list_wiki_documents(root_tokens=wiki_root_tokens)
            except Exception as exc:
                msg = f"Feishu wiki listing failed: {exc}"
                logger.warning(msg)
                errors.append(msg)

            all_items = doc_items + wiki_items

            for item in all_items:
                token = item.get("token", "")
                title = item.get("name") or item.get("title") or token

                try:
                    content = connector.get_doc_content(token)
                    if not content or not content.strip():
                        continue

                    metadata = {
                        "feishu_token": token,
                        "doc_type": item.get("type", ""),
                        "root_token": item.get("_root_token", ""),
                    }

                    count = await self.index_manager.index_document(
                        source_type=source_type,
                        source_ref=token,
                        title=title,
                        content=content,
                        metadata=metadata,
                        org_id=org_id,
                        chunk_strategy="section",
                    )
                    docs_indexed += 1
                    chunks_indexed += count
                except Exception as exc:
                    self.db.rollback()
                    msg = f"Failed to index Feishu doc {title}: {exc}"
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
            error_msg = f"Feishu sync failed: {exc}"
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

    def _get_root_tokens(self) -> list[str]:
        from app.models.entities import KBConfig
        config = self.db.execute(select(KBConfig).limit(1)).scalar_one_or_none()
        if config is not None and config.feishu_root_tokens:
            return [t.strip() for t in config.feishu_root_tokens.split(",") if t.strip()]
        if self.settings.feishu_oauth_scopes:
            return [""]
        return [""]
