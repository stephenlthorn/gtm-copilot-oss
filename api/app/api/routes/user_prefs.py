from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.entities import UserPreference
from app.schemas.user_prefs import UserPrefRead, UserPrefUpdate

router = APIRouter()


@router.get("/preferences", response_model=UserPrefRead)
def get_user_preferences(
    x_user_email: str = Header(...),
    db: Session = Depends(db_session),
):
    pref = db.get(UserPreference, x_user_email.strip().lower())
    if pref is None:
        raise HTTPException(status_code=404, detail="No preferences found")
    return pref


@router.put("/preferences", response_model=UserPrefRead)
def upsert_user_preferences(
    body: UserPrefUpdate,
    x_user_email: str = Header(...),
    db: Session = Depends(db_session),
):
    email = x_user_email.strip().lower()
    pref = db.get(UserPreference, email)
    if pref is None:
        pref = UserPreference(user_email=email)
        db.add(pref)
    if body.llm_model is not None:
        pref.llm_model = body.llm_model or None
    if body.reasoning_effort is not None:
        pref.reasoning_effort = body.reasoning_effort or None
    db.commit()
    db.refresh(pref)
    return pref
