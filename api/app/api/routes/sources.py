from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter()


@router.get("")
def list_sources(
    request: Request,
    db: Session = Depends(db_session),
    scope: str | None = Query(None),
    account_id: int | None = Query(None),
) -> dict:
    from app.models.entities import SourceScope
    from app.services.indexing.source_registry import SourceRegistryService

    org_id = int(request.headers.get("X-Org-Id", "1"))

    scope_enum: SourceScope | None = None
    if scope is not None:
        try:
            scope_enum = SourceScope(scope)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid scope '{scope}'. Must be one of: {[s.value for s in SourceScope]}",
            )

    service = SourceRegistryService(db)

    if account_id is not None:
        sources = service.get_active_sources(org_id, account_id=account_id)
    else:
        sources = service.list_sources(org_id, scope=scope_enum)

    return {
        "sources": [
            {
                "id": s.id,
                "source_type": s.source_type.value if s.source_type else None,
                "provider": s.provider,
                "config": s.config,
                "scope": s.scope.value if s.scope else None,
                "account_id": s.account_id,
                "user_id": s.user_id,
                "org_id": s.org_id,
                "active": s.active,
            }
            for s in sources
        ]
    }


@router.post("")
def add_source(
    request: Request,
    db: Session = Depends(db_session),
    body: dict | None = Body(default=None),
) -> dict:
    from app.models.entities import SourceScope
    from app.services.indexing.source_registry import SourceRegistryService

    org_id = int(request.headers.get("X-Org-Id", "1"))
    user_id = int(request.headers.get("X-User-Id", "1"))

    if not body:
        raise HTTPException(status_code=422, detail="Request body is required")

    provider = body.get("provider")
    if not provider:
        raise HTTPException(status_code=422, detail="'provider' is required")

    config = body.get("config", {})
    if not isinstance(config, dict):
        raise HTTPException(status_code=422, detail="'config' must be an object")

    raw_scope = body.get("scope", "global")
    try:
        scope = SourceScope(raw_scope)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid scope '{raw_scope}'. Must be one of: {[s.value for s in SourceScope]}",
        )

    account_id: int | None = body.get("account_id")

    service = SourceRegistryService(db)
    source = service.add_custom_source(
        user_id=user_id,
        org_id=org_id,
        provider=provider,
        config=config,
        scope=scope,
        account_id=account_id,
    )

    return {
        "source": {
            "id": source.id,
            "source_type": source.source_type.value if source.source_type else None,
            "provider": source.provider,
            "config": source.config,
            "scope": source.scope.value if source.scope else None,
            "account_id": source.account_id,
            "user_id": source.user_id,
            "org_id": source.org_id,
            "active": source.active,
        }
    }


@router.put("/{source_id}")
def update_source(
    source_id: int,
    request: Request,
    db: Session = Depends(db_session),
    body: dict | None = Body(default=None),
) -> dict:
    from sqlalchemy import select

    from app.models.entities import SourceRegistry

    source = db.execute(
        select(SourceRegistry).where(SourceRegistry.id == source_id)
    ).scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    if not body:
        raise HTTPException(status_code=422, detail="Request body is required")

    if "config" in body:
        new_config = body["config"]
        if not isinstance(new_config, dict):
            raise HTTPException(status_code=422, detail="'config' must be an object")
        source.config = new_config

    if "active" in body:
        active_val = body["active"]
        if not isinstance(active_val, bool):
            raise HTTPException(status_code=422, detail="'active' must be a boolean")
        source.active = active_val

    db.commit()
    db.refresh(source)

    return {
        "source": {
            "id": source.id,
            "source_type": source.source_type.value if source.source_type else None,
            "provider": source.provider,
            "config": source.config,
            "scope": source.scope.value if source.scope else None,
            "account_id": source.account_id,
            "user_id": source.user_id,
            "org_id": source.org_id,
            "active": source.active,
        }
    }


@router.delete("/{source_id}")
def remove_source(
    source_id: int,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.services.indexing.source_registry import SourceRegistryService

    service = SourceRegistryService(db)
    deleted = service.remove_source(source_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    return {"deleted": True, "source_id": source_id}
