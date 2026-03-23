from __future__ import annotations

import uuid as _uuid_mod
from datetime import date as _date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models import AuditStatus, CallArtifact, ChorusCall, KBDocument, KBChunk
from app.schemas.messaging import RegenerateDraftRequest
from app.services.audit import write_audit_log
from app.services.messaging import MessagingService

router = APIRouter()


class ManualCallRequest(PydanticBaseModel):
    account: str
    notes: str
    date: str | None = None
    participants: list[str] = []
    stage: str | None = None


@router.get("")
def list_calls(
    account: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(db_session),
) -> list[dict]:
    stmt = select(ChorusCall).order_by(ChorusCall.date.desc()).limit(limit)
    if account:
        stmt = stmt.where(ChorusCall.account == account)

    calls = db.execute(stmt).scalars().all()
    return [
        {
            "chorus_call_id": c.chorus_call_id,
            "date": c.date,
            "account": c.account,
            "opportunity": c.opportunity,
            "stage": c.stage,
            "rep_email": c.rep_email,
            "se_email": c.se_email,
        }
        for c in calls
    ]


@router.post("/manual")
def log_manual_call(
    req: ManualCallRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(db_session),
) -> dict:
    from app.models import KBDocument, KBChunk, SourceType
    from app.services.embedding import EmbeddingService
    from app.utils.hashing import sha256_text

    rep_email = (request.headers.get("X-User-Email") or "").strip().lower() or "unknown"
    openai_token = request.headers.get("X-OpenAI-Token")
    call_date = _date.fromisoformat(req.date) if req.date else _date.today()
    call_id = _uuid_mod.uuid4()

    call = ChorusCall(
        id=call_id,
        chorus_call_id=None,
        source_type="manual",
        account=req.account,
        date=call_date,
        rep_email=rep_email,
        stage=req.stage,
        participants=[{"email": p} for p in req.participants],
        meeting_summary=req.notes[:500],
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    # Index notes as KBDocument + single KBChunk
    try:
        embedder = EmbeddingService()
        doc = KBDocument(
            source_type=SourceType.CHORUS,
            source_id=str(call_id),
            title=f"Manual call — {req.account} — {call_date}",
            url=None,
            mime_type="text/plain",
            owner=rep_email,
            permissions_hash=sha256_text(rep_email),
            tags={
                "account": req.account,
                "date": call_date.isoformat(),
                "source_type": "manual_call",
            },
        )
        db.add(doc)
        db.flush()
        emb = embedder.embed(req.notes)
        db.add(KBChunk(
            document_id=doc.id,
            chunk_index=0,
            text=req.notes,
            token_count=len(req.notes.split()),
            embedding=emb,
            metadata_json={"account": req.account, "source_type": "manual_call"},
            content_hash=sha256_text(req.notes),
        ))
        db.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to index manual call notes: %s", exc)

    background_tasks.add_task(_run_delta_pipeline, str(call_id), req.notes, openai_token)

    return {"id": str(call_id), "account": req.account, "date": call_date.isoformat(), "source_type": "manual"}


def _run_delta_pipeline(call_id_str: str, notes: str, api_key: str | None = None) -> None:
    from app.db.session import SessionLocal
    from app.services.account_memory import AccountMemoryService
    from app.services.llm import LLMService
    import logging
    db = SessionLocal()
    try:
        call = db.get(ChorusCall, _uuid_mod.UUID(call_id_str))
        if not call:
            return
        svc = AccountMemoryService(db)
        llm = LLMService(api_key=api_key)
        svc.run_delta_pipeline(call, notes, llm)
    except Exception as exc:
        logging.getLogger(__name__).warning("Delta pipeline failed for manual call %s: %s", call_id_str, exc)
    finally:
        db.close()


@router.get("/{chorus_call_id}")
def call_detail(chorus_call_id: str, db: Session = Depends(db_session)) -> dict:
    call = db.execute(select(ChorusCall).where(ChorusCall.chorus_call_id == chorus_call_id)).scalar_one_or_none()
    if call is None:
        try:
            call = db.get(ChorusCall, _uuid_mod.UUID(chorus_call_id))
        except (ValueError, AttributeError):
            pass
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")

    call_ref = call.chorus_call_id or str(call.id)
    artifact = db.execute(
        select(CallArtifact).where(CallArtifact.chorus_call_id == call_ref).order_by(CallArtifact.created_at.desc())
    ).scalars().first()

    doc = db.execute(select(KBDocument).where(KBDocument.source_id == call_ref)).scalar_one_or_none()
    chunks: list[KBChunk] = []
    if doc:
        chunks = db.execute(
            select(KBChunk).where(KBChunk.document_id == doc.id).order_by(KBChunk.chunk_index.asc())
        ).scalars().all()

    return {
        "call": {
            "id": str(call.id),
            "chorus_call_id": call.chorus_call_id,
            "source_type": getattr(call, "source_type", "chorus"),
            "date": call.date,
            "account": call.account,
            "opportunity": call.opportunity,
            "stage": call.stage,
            "rep_email": call.rep_email,
            "se_email": call.se_email,
            "participants": call.participants,
            "recording_url": call.recording_url,
            "transcript_url": call.transcript_url,
        },
        "artifact": {
            "id": str(artifact.id),
            "summary": artifact.summary,
            "objections": artifact.objections,
            "competitors_mentioned": artifact.competitors_mentioned,
            "risks": artifact.risks,
            "next_steps": artifact.next_steps,
            "recommended_collateral": artifact.recommended_collateral,
            "follow_up_questions": artifact.follow_up_questions,
        }
        if artifact
        else None,
        "chunks": [
            {
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "metadata": chunk.metadata_json,
            }
            for chunk in chunks
        ],
    }


@router.post("/{chorus_call_id}/regenerate-draft")
def regenerate_draft(
    chorus_call_id: str,
    req: RegenerateDraftRequest,
    db: Session = Depends(db_session),
) -> dict:
    call = db.execute(select(ChorusCall).where(ChorusCall.chorus_call_id == chorus_call_id)).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="call not found")

    artifact = db.execute(
        select(CallArtifact).where(CallArtifact.chorus_call_id == chorus_call_id).order_by(CallArtifact.created_at.desc())
    ).scalars().first()
    if not artifact:
        raise HTTPException(status_code=404, detail="artifact not found")

    to = req.to or [call.rep_email]
    cc = req.cc or ([call.se_email] if call.se_email else [])
    svc = MessagingService(db)
    subject = svc.build_email_subject(call.account)
    body = svc.build_email_body(
        account=call.account,
        summary=artifact.summary,
        next_steps=artifact.next_steps,
        questions=artifact.follow_up_questions,
        collateral=artifact.recommended_collateral,
        sources=[f"Call Transcript {chorus_call_id}", "Internal knowledge collateral"],
    )
    row = svc.draft_or_send(
        to=to,
        cc=cc,
        subject=subject,
        body=body,
        requested_mode=req.mode,
        chorus_call_id=chorus_call_id,
        artifact_id=artifact.id,
    )
    output = {
        "mode": row.mode.value,
        "to": row.to_recipients,
        "cc": row.cc_recipients,
        "subject": row.subject,
        "body": row.body,
        "reason_blocked": row.reason_blocked,
    }
    write_audit_log(
        db,
        actor=call.rep_email,
        action="draft_message",
        input_payload={"chorus_call_id": chorus_call_id, **req.model_dump()},
        retrieval_payload={},
        output_payload=output,
        status=AuditStatus.OK,
    )
    return output
