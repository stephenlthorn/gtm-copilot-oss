from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AuditStatus
from app.schemas.chat import ChatRequest
from app.services.audit import write_audit_log
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.memory import MemoryService

router = APIRouter()

CONTEXT_BUDGETS = {
    "gpt-5.4": 100000,
    "gpt-5.4-mini": 100000,
    "gpt-5.4-nano": 24000,
    "gpt-5.3-codex": 100000,
    "o4-mini": 160000,
    "o3": 160000,
    "o3-pro": 160000,
    "o3-mini": 160000,
    "gpt-5.1-codex": 100000,
    "gpt-5-codex-mini": 24000,
}
DEFAULT_BUDGET = 100000


@router.get("/history")
def chat_history(request: Request, limit: int = 100, model: str = "gpt-5.4") -> list[dict]:
    from app.models.entities import ChatMessage

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        return []
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ChatMessage)
                .where(ChatMessage.user_email == user_email)
                .order_by(asc(ChatMessage.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        budget = CONTEXT_BUDGETS.get(model, DEFAULT_BUDGET)
        result = []
        used = 0
        for msg in reversed(rows):  # newest first
            tokens = len(msg.content) // 4
            if used + tokens > budget:
                break
            result.insert(0, msg)
            used += tokens
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat(),
            }
            for r in result
        ]


@router.post("")
def chat(req: ChatRequest, request: Request) -> dict:
    openai_token = request.headers.get("X-OpenAI-Token") or req.openai_token
    with SessionLocal() as db:
        orchestrator = ChatOrchestrator(db, openai_token=openai_token)

        try:
            data, retrieval = orchestrator.run(
                mode=req.mode,
                user=req.user,
                message=req.message,
                top_k=req.top_k,
                filters=req.filters.model_dump(),
                context=req.context.model_dump(),
                rag_enabled=req.rag_enabled,
                web_search_enabled=req.web_search_enabled,
                section=req.section,
                tidb_expert=req.tidb_expert,
            )
            # Persist chat messages
            try:
                from app.models.entities import ChatMessage
                import uuid as _uuid
                from datetime import datetime

                db.add(
                    ChatMessage(
                        id=str(_uuid.uuid4()),
                        user_email=req.user,
                        role="user",
                        content=req.message,
                        created_at=datetime.utcnow(),
                    )
                )
                db.add(
                    ChatMessage(
                        id=str(_uuid.uuid4()),
                        user_email=req.user,
                        role="assistant",
                        content=data.get("answer", ""),
                        created_at=datetime.utcnow(),
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
            write_audit_log(
                db,
                actor=req.user,
                action="chat",
                input_payload=req.model_dump(),
                retrieval_payload=retrieval,
                output_payload=data,
                status=AuditStatus.OK,
            )
            try:
                MemoryService(db).capture_interaction(
                    actor=req.user,
                    mode=req.mode,
                    message=req.message,
                    response_payload=data,
                    retrieval_payload=retrieval,
                )
            except Exception:
                db.rollback()
            return data
        except Exception as exc:
            db.rollback()
            write_audit_log(
                db,
                actor=req.user,
                action="chat",
                input_payload=req.model_dump(),
                retrieval_payload={},
                output_payload={},
                status=AuditStatus.ERROR,
                error_message=str(exc),
            )
            raise
