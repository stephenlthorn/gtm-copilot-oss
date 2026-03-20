from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter()

_VALID_ROLES = {"sales_rep", "se", "marketing", "admin"}


@router.get("/users")
def list_users(
    request: Request,
    db: Session = Depends(db_session),
) -> list[dict]:
    from app.models.entities import User

    org_id = int(request.headers.get("X-Org-Id", "1"))
    users = db.query(User).filter(User.org_id == org_id).order_by(User.created_at.asc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role.value if u.role else "sales_rep",
            "created_at": str(u.created_at) if u.created_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}")
def update_user_role(
    user_id: int,
    request: Request,
    body: dict = Body(...),
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User, UserRole

    org_id = int(request.headers.get("X-Org-Id", "1"))
    role_value = body.get("role", "")
    if role_value not in _VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {sorted(_VALID_ROLES)}",
        )

    user = db.query(User).filter(User.id == user_id, User.org_id == org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = UserRole(role_value)
    db.commit()
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
    }
