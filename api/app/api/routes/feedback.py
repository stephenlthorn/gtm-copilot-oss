from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_auth
from app.models.feedback import AIFeedback
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services.embedding import EmbeddingService

router = APIRouter()

VALID_CATEGORIES = {
    "wrong_info", "missing_info", "wrong_context",
    "outdated_info", "too_generic", "wrong_tone", "incomplete",
}


@router.post("", response_model=FeedbackRead, status_code=201)
def create_feedback(
    body: FeedbackCreate,
    user_email: str = Depends(require_auth),
    db: Session = Depends(db_session),
):
    if body.rating not in ("positive", "negative"):
        raise HTTPException(status_code=422, detail="rating must be 'positive' or 'negative'")

    email = user_email
    category = body.failure_category if body.failure_category in VALID_CATEGORIES else None
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
        failure_category=category,
        embedding=embedding,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    # Write chunk quality signals if citations provided
    if body.citations:
        try:
            from datetime import datetime, timedelta, timezone
            from app.models import AuditLog
            from app.models.feedback import ChunkQualitySignal

            audit_log = None
            if body.audit_id:
                audit_log = db.execute(
                    select(AuditLog).where(AuditLog.id == body.audit_id)
                ).scalar_one_or_none()
            if audit_log is None:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
                audit_log = db.execute(
                    select(AuditLog)
                    .where(AuditLog.actor == email)
                    .where(AuditLog.timestamp >= cutoff)
                    .order_by(AuditLog.timestamp.desc())
                    .limit(1)
                ).scalar_one_or_none()

            cited_set = set(body.citations)
            signal_val = "cited_positive" if body.rating == "positive" else "cited_negative"
            for chunk_id in cited_set:
                db.add(ChunkQualitySignal(
                    chunk_id=chunk_id,
                    signal=signal_val,
                    query_mode=body.mode,
                ))

            if audit_log and audit_log.retrieval_json:
                retrieved = {r["chunk_id"] for r in audit_log.retrieval_json.get("results", [])}
                for chunk_id in retrieved - cited_set:
                    db.add(ChunkQualitySignal(
                        chunk_id=chunk_id,
                        signal="retrieved_unused",
                        query_mode=body.mode,
                    ))

            db.commit()
        except Exception:
            pass

    return fb


@router.get("", response_model=list[FeedbackRead])
def list_feedback(
    mode: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user_email: str = Depends(require_auth),
    db: Session = Depends(db_session),
):
    stmt = select(AIFeedback).order_by(AIFeedback.created_at.desc()).limit(limit)
    if mode:
        stmt = stmt.where(AIFeedback.mode == mode)
    return db.execute(stmt).scalars().all()
