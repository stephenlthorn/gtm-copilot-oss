from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import SourceRegistry, SourceRegistryType, SourceScope

logger = logging.getLogger(__name__)


class SourceRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(
        self,
        org_id: int,
        scope: SourceScope | None = None,
    ) -> list[SourceRegistry]:
        stmt = select(SourceRegistry).where(SourceRegistry.org_id == org_id)
        if scope is not None:
            stmt = stmt.where(SourceRegistry.scope == scope)
        return list(self.db.execute(stmt).scalars().all())

    def add_custom_source(
        self,
        user_id: int,
        org_id: int,
        provider: str,
        config: dict,
        scope: SourceScope = SourceScope.global_,
        account_id: int | None = None,
    ) -> SourceRegistry:
        source = SourceRegistry(
            source_type=SourceRegistryType.custom,
            provider=provider,
            config=config,
            scope=scope,
            account_id=account_id,
            user_id=user_id,
            org_id=org_id,
            active=True,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        logger.info(
            "Added custom source: provider=%s, org=%d, user=%d",
            provider,
            org_id,
            user_id,
        )
        return source

    def remove_source(self, source_id: int) -> bool:
        source = self.db.execute(
            select(SourceRegistry).where(SourceRegistry.id == source_id)
        ).scalar_one_or_none()
        if source is None:
            return False
        self.db.delete(source)
        self.db.commit()
        logger.info("Removed source id=%d", source_id)
        return True

    def get_active_sources(
        self,
        org_id: int,
        account_id: int | None = None,
    ) -> list[SourceRegistry]:
        stmt = (
            select(SourceRegistry)
            .where(SourceRegistry.org_id == org_id)
            .where(SourceRegistry.active == True)
        )
        if account_id is not None:
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    SourceRegistry.account_id == account_id,
                    SourceRegistry.scope == SourceScope.global_,
                )
            )
        return list(self.db.execute(stmt).scalars().all())
