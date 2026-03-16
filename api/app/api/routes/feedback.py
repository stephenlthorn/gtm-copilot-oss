from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.feedback import AIFeedback
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services.embedding import EmbeddingService

router = APIRouter()


@router.post("", response_model=FeedbackRead, status_code=201)
def create_feedback(
    body: FeedbackCreate,
    x_user_email: str = Header(...),
    db: Session = Depends(db_session),
):
    if body.rating not in ("positive", "negative"):
        raise HTTPException(status_code=422, detail="rating must be 'positive' or 'negative'")

    email = x_user_email.strip().lower()
    text_to_embed = body.correction.strip() if body.correction and body.correction.strip() else body.original_response
    embedding = None
    try:
        svc = EmbeddingService()
        embedding = svc.embed(text_to_embed)
    except Exception:
        pass

    fb = AIFeedback(
        user_email=email,
        mode=body.mode,
        query_text=body.query_text,
        original_response=body.original_response,
        rating=body.rating,
        correction=body.correction,
        embedding=embedding,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("", response_model=list[FeedbackRead])
def list_feedback(
    mode: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_session),
):
    stmt = select(AIFeedback).order_by(AIFeedback.created_at.desc()).limit(limit)
    if mode:
        stmt = stmt.where(AIFeedback.mode == mode)
    return db.execute(stmt).scalars().all()
