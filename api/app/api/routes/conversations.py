from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.services.chat.chat_service import ChatService

router = APIRouter()


class CreateConversationRequest(BaseModel):
    title: str | None = None
    account_id: int | None = None


class SendMessageRequest(BaseModel):
    message: str


def _extract_user_id(request: Request) -> int:
    """Extract user ID from request headers or auth context."""
    raw = request.headers.get("X-User-Id", "0")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


def _extract_org_id(request: Request) -> int:
    """Extract org ID from request headers or auth context."""
    raw = request.headers.get("X-Org-Id", "1")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 1


@router.get("")
def list_conversations(
    request: Request,
    db: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    """List conversations for the current user."""
    user_id = _extract_user_id(request)
    service = ChatService(
        db,
        openai_api_key=request.headers.get("X-OpenAI-Token"),
    )
    return service.get_conversations(user_id)


@router.post("")
def create_conversation(
    body: CreateConversationRequest,
    request: Request,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Create a new conversation."""
    user_id = _extract_user_id(request)
    org_id = _extract_org_id(request)
    service = ChatService(
        db,
        openai_api_key=request.headers.get("X-OpenAI-Token"),
    )
    conversation = service.create_conversation(
        user_id=user_id,
        org_id=org_id,
        title=body.title,
        account_id=body.account_id,
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "account_id": conversation.account_id,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
    }


@router.get("/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    db: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    """Get all messages in a conversation."""
    service = ChatService(db)
    return service.get_messages(conversation_id)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    body: SendMessageRequest,
    request: Request,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    """Send a message and stream the response using Server-Sent Events."""
    user_id = _extract_user_id(request)
    org_id = _extract_org_id(request)
    service = ChatService(
        db,
        openai_api_key=request.headers.get("X-OpenAI-Token"),
    )

    async def event_stream():
        async for chunk in service.send_message(
            conversation_id=conversation_id,
            user_message=body.message,
            user_id=user_id,
            org_id=org_id,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
