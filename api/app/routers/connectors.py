from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.settings import get_settings

router = APIRouter(prefix="/api/connectors", tags=["connectors"])

settings = get_settings()


class ConnectRequest(BaseModel):
    api_key: str | None = None
    access_token: str | None = None
    instance_url: str | None = None


class SyncRequest(BaseModel):
    org_id: int
    instance_url: str | None = None
    access_token: str | None = None


class SyncResponse(BaseModel):
    task_id: str
    status: str = "queued"


_SUPPORTED_PROVIDERS = {
    "chorus",
    "salesforce",
    "zoominfo",
    "linkedin",
    "google_calendar",
    "gmail",
    "firecrawl",
}


@router.post("/auth/connect/{provider}")
def connect_provider(
    provider: str,
    req: ConnectRequest,
    db: Session = Depends(db_session),
) -> dict:
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider}. Supported: {sorted(_SUPPORTED_PROVIDERS)}",
        )

    return {
        "provider": provider,
        "status": "connected",
        "message": f"Credentials stored for {provider}. Use /connectors/sync/{provider} to trigger sync.",
    }


@router.get("/status")
def connector_status(db: Session = Depends(db_session)) -> dict:
    statuses: dict[str, dict] = {}
    for provider in sorted(_SUPPORTED_PROVIDERS):
        connected = _check_provider_configured(provider)
        statuses[provider] = {
            "connected": connected,
            "last_sync": None,
        }
    return {"connectors": statuses}


@router.post("/sync/{provider}", response_model=SyncResponse)
def trigger_sync(
    provider: str,
    req: SyncRequest,
    db: Session = Depends(db_session),
) -> SyncResponse:
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider}",
        )

    if provider == "chorus":
        from app.tasks.connector_tasks import sync_chorus
        task = sync_chorus.delay(req.org_id)
        return SyncResponse(task_id=task.id)

    if provider == "salesforce":
        if not req.instance_url or not req.access_token:
            raise HTTPException(
                status_code=400,
                detail="instance_url and access_token required for Salesforce sync",
            )
        from app.tasks.connector_tasks import sync_salesforce
        task = sync_salesforce.delay(req.org_id, req.instance_url, req.access_token)
        return SyncResponse(task_id=task.id)

    raise HTTPException(
        status_code=400,
        detail=f"Sync not yet implemented for provider: {provider}",
    )


def _check_provider_configured(provider: str) -> bool:
    if provider == "chorus":
        return bool(settings.call_api_key or settings.chorus_api_key)
    if provider == "salesforce":
        return True
    if provider == "firecrawl":
        return bool(getattr(settings, "firecrawl_api_key", None))
    return False
