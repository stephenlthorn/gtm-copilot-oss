from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models import AccountDealMemory
from app.services.account_memory import AccountMemoryService, canonicalize_account

router = APIRouter()


def _user_email(request: Request) -> str | None:
    raw = request.headers.get("X-User-Email", "")
    return raw.strip().lower() or None


class ApproveRequest(BaseModel):
    edits: dict | None = None


class PatchRequest(BaseModel):
    deal_stage: str | None = None
    status: str | None = None
    is_new_business: bool | None = None
    meddpicc: dict | None = None
    key_contacts: list | None = None
    tech_stack: dict | None = None
    open_items: list | None = None


@router.get("/{account}/memory")
def get_memory(account: str, db: Session = Depends(db_session)) -> dict:
    svc = AccountMemoryService(db)
    memory = svc.get_or_create(account)
    return _memory_to_dict(memory)


@router.post("/{account}/memory/approve")
def approve_memory(account: str, req: ApproveRequest, db: Session = Depends(db_session)) -> dict:
    svc = AccountMemoryService(db)
    try:
        memory = svc.approve(account, edits=req.edits)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _memory_to_dict(memory)


@router.post("/{account}/memory/dismiss")
def dismiss_memory(account: str, db: Session = Depends(db_session)) -> dict:
    svc = AccountMemoryService(db)
    try:
        memory = svc.dismiss(account)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _memory_to_dict(memory)


@router.patch("/{account}/memory")
def patch_memory(account: str, req: PatchRequest, db: Session = Depends(db_session)) -> dict:
    key = canonicalize_account(account)
    memory = db.get(AccountDealMemory, key)
    if not memory:
        raise HTTPException(status_code=404, detail="Account memory not found")
    if req.deal_stage is not None:
        memory.deal_stage = req.deal_stage
    if req.status is not None:
        memory.status = req.status
    if req.is_new_business is not None:
        memory.is_new_business = req.is_new_business
    if req.meddpicc is not None:
        current = dict(memory.meddpicc or {})
        current.update(req.meddpicc)
        memory.meddpicc = current
    if req.key_contacts is not None:
        memory.key_contacts = req.key_contacts
    if req.tech_stack is not None:
        memory.tech_stack = req.tech_stack
    if req.open_items is not None:
        memory.open_items = req.open_items
    db.commit()
    return _memory_to_dict(memory)


def _memory_to_dict(memory: AccountDealMemory) -> dict:
    return {
        "account": memory.account,
        "deal_stage": memory.deal_stage,
        "is_new_business": memory.is_new_business,
        "status": memory.status,
        "meddpicc": memory.meddpicc,
        "key_contacts": memory.key_contacts,
        "tech_stack": memory.tech_stack,
        "open_items": memory.open_items,
        "summary": memory.summary,
        "call_count": memory.call_count,
        "last_call_date": memory.last_call_date.isoformat() if memory.last_call_date else None,
        "pending_review": memory.pending_review,
        "pending_delta": memory.pending_delta,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }
