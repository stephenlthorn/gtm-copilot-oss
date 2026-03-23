from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.services.prompt_service import PromptService

router = APIRouter()


def _get_user(request: Request) -> str:
    return request.headers.get("X-User-Email", "unknown@example.com")


class UpdatePromptBody(BaseModel):
    content: str
    note: str | None = None


class OverrideBody(BaseModel):
    content: str


@router.get("")
def list_prompts(db: Session = Depends(db_session)):
    return PromptService(db).list_all()


@router.get("/{prompt_id}/versions")
def list_versions(prompt_id: str, db: Session = Depends(db_session)):
    return PromptService(db).get_versions(prompt_id)


@router.get("/{prompt_id}/versions/{version}")
def get_version(prompt_id: str, version: int, db: Session = Depends(db_session)):
    result = PromptService(db).get_version(prompt_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return result


@router.get("/{prompt_id}/my-override")
def get_my_override(prompt_id: str, request: Request, db: Session = Depends(db_session)):
    result = PromptService(db).get_user_override(prompt_id, _get_user(request))
    if result is None:
        raise HTTPException(status_code=404, detail="No override found")
    return result


@router.put("/{prompt_id}/my-override")
def save_my_override(prompt_id: str, body: OverrideBody, request: Request, db: Session = Depends(db_session)):
    PromptService(db).save_user_override(prompt_id, _get_user(request), body.content)
    return {"ok": True}


@router.delete("/{prompt_id}/my-override")
def delete_my_override(prompt_id: str, request: Request, db: Session = Depends(db_session)):
    PromptService(db).delete_user_override(prompt_id, _get_user(request))
    return {"ok": True}


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str, db: Session = Depends(db_session)):
    result = PromptService(db).get(prompt_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return result


@router.put("/{prompt_id}")
def update_prompt(prompt_id: str, body: UpdatePromptBody, request: Request, db: Session = Depends(db_session)):
    try:
        PromptService(db).save(prompt_id, body.content, edited_by=_get_user(request), note=body.note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.post("/{prompt_id}/reset")
def reset_prompt(prompt_id: str, request: Request, db: Session = Depends(db_session)):
    try:
        PromptService(db).reset(prompt_id, reset_by=_get_user(request))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.post("/{prompt_id}/rollback/{version}")
def rollback_prompt(prompt_id: str, version: int, request: Request, db: Session = Depends(db_session)):
    try:
        PromptService(db).rollback(prompt_id, version, rolled_back_by=_get_user(request))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
