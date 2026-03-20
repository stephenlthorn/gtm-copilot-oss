from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.services.notifications.preferences import (
    DEFAULT_PREFERENCES,
    NotificationPreferencesService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class NotificationPreferenceItem(BaseModel):
    enabled: bool | None = None
    timing: str | None = None
    channel: str | None = None
    channel_name: str | None = None


class UpdatePreferencesRequest(BaseModel):
    preferences: dict[str, NotificationPreferenceItem]


class PreferencesResponse(BaseModel):
    preferences: dict[str, dict[str, Any]]


def _extract_user_context(request: Request) -> tuple[int, int]:
    """Extract user_id and org_id from request context.

    Looks for values set by auth middleware or passed as headers.
    """
    user_id = getattr(request.state, "user_id", None)
    org_id = getattr(request.state, "org_id", None)

    if user_id is None:
        user_id_header = request.headers.get("X-User-Id")
        if user_id_header:
            try:
                user_id = int(user_id_header)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-User-Id header")

    if org_id is None:
        org_id_header = request.headers.get("X-Org-Id")
        if org_id_header:
            try:
                org_id = int(org_id_header)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-Org-Id header")

    if user_id is None:
        raise HTTPException(status_code=401, detail="User authentication required")
    if org_id is None:
        raise HTTPException(status_code=400, detail="Organization context required")

    return user_id, org_id


@router.get("/preferences", response_model=PreferencesResponse)
def get_notification_preferences(
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    user_id, _org_id = _extract_user_context(request)
    service = NotificationPreferencesService(db)
    prefs = service.get_preferences(user_id)
    return {"preferences": prefs}


@router.put("/preferences", response_model=PreferencesResponse)
def update_notification_preferences(
    body: UpdatePreferencesRequest,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    user_id, org_id = _extract_user_context(request)

    invalid_types = [k for k in body.preferences if k not in DEFAULT_PREFERENCES]
    if invalid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown notification types: {', '.join(invalid_types)}",
        )

    prefs_dict: dict[str, dict[str, Any]] = {}
    for key, item in body.preferences.items():
        pref_update: dict[str, Any] = {}
        if item.enabled is not None:
            pref_update["enabled"] = item.enabled
        if item.timing is not None:
            pref_update["timing"] = item.timing
        if item.channel is not None:
            pref_update["channel"] = item.channel
        if item.channel_name is not None:
            pref_update["channel_name"] = item.channel_name
        if pref_update:
            prefs_dict[key] = pref_update

    service = NotificationPreferencesService(db)

    try:
        service.update_preferences(user_id, org_id, prefs_dict)
    except Exception:
        logger.exception("Failed to update notification preferences for user %d", user_id)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    updated_prefs = service.get_preferences(user_id)
    return {"preferences": updated_prefs}
