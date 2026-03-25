from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import UserTemplate

router = APIRouter()
user_router = APIRouter()


class TemplateUpsert(BaseModel):
    template_name: str
    content: str


@router.get("/all")
def get_all_templates(request: Request) -> list[dict]:
    """Return all non-default user templates (for the picker dropdown)."""
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(UserTemplate).where(UserTemplate.is_default == False)  # noqa: E712
            )
            .scalars()
            .all()
        )
        return [
            {
                "user_email": r.user_email,
                "section_key": r.section_key,
                "template_name": r.template_name,
                "content": r.content,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]


@user_router.get("")
def get_my_templates(request: Request) -> list[dict]:
    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(UserTemplate).where(
                    (UserTemplate.user_email == user_email)
                    | (UserTemplate.is_default == True)  # noqa: E712
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": r.id,
                "user_email": r.user_email,
                "section_key": r.section_key,
                "template_name": r.template_name,
                "content": r.content,
                "is_default": r.is_default,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]


@user_router.put("/{section_key}")
def upsert_template(section_key: str, body: TemplateUpsert, request: Request) -> dict:
    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    with SessionLocal() as db:
        existing = db.execute(
            select(UserTemplate).where(
                UserTemplate.user_email == user_email,
                UserTemplate.section_key == section_key,
                UserTemplate.is_default == False,  # noqa: E712
            )
        ).scalar_one_or_none()
        if existing:
            existing.template_name = body.template_name
            existing.content = body.content
            existing.updated_at = datetime.utcnow()
            db.commit()
        else:
            row = UserTemplate(
                id=str(uuid.uuid4()),
                user_email=user_email,
                section_key=section_key,
                template_name=body.template_name,
                content=body.content,
                is_default=False,
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
        return {"section_key": section_key, "ok": True}
