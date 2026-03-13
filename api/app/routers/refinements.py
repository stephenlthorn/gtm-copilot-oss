from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.entities import AIRefinement, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["refinements"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RefinementOut(BaseModel):
    id: int
    user_id: int | None
    output_type: str | None
    feedback_text: str | None
    context_filter: dict[str, Any] | None = None
    scope: str | None
    active: bool
    effectiveness: int
    created_at: str | None = None


class UpdateRefinementRequest(BaseModel):
    feedback_text: str | None = None
    context_filter: dict[str, Any] | None = None
    active: bool | None = None


class PromoteResponse(BaseModel):
    id: int
    scope: str
    status: str = "promoted"


# ---------------------------------------------------------------------------
# User-facing endpoints
# ---------------------------------------------------------------------------


@router.get("/api/refinements", response_model=list[RefinementOut])
def list_user_refinements(
    user_id: int = Query(...),
    output_type: str | None = Query(None),
    db: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    """List the current user's refinements."""
    from app.services.research.refinement_service import RefinementService

    service = RefinementService(db)
    refinements = service.get_refinements(user_id=user_id, output_type=output_type or "pre_call")
    return [_refinement_to_dict(r) for r in refinements]


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/refinements", response_model=list[RefinementOut])
def list_all_refinements(
    org_id: int = Query(...),
    output_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    """Admin: list ALL refinements across the org."""
    query = (
        db.query(AIRefinement)
        .join(User, AIRefinement.user_id == User.id)
        .filter(User.org_id == org_id)
    )
    if output_type:
        query = query.filter(AIRefinement.output_type == output_type)

    refinements = query.order_by(AIRefinement.created_at.desc()).offset(offset).limit(limit).all()
    return [_refinement_to_dict(r) for r in refinements]


@router.post("/api/admin/refinements/{refinement_id}/promote", response_model=PromoteResponse)
def promote_refinement(
    refinement_id: int,
    admin_user_id: int = Query(...),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Admin: promote a personal refinement to team scope."""
    from app.services.research.refinement_service import RefinementService

    service = RefinementService(db)
    try:
        refinement = service.promote_to_team(refinement_id, admin_user_id)
        return {
            "id": refinement.id,
            "scope": refinement.scope.value if hasattr(refinement.scope, "value") else str(refinement.scope),
            "status": "promoted",
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/api/admin/refinements/{refinement_id}", response_model=RefinementOut)
def update_refinement(
    refinement_id: int,
    req: UpdateRefinementRequest,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Admin: edit a refinement."""
    refinement = db.query(AIRefinement).get(refinement_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="Refinement not found")

    if req.feedback_text is not None:
        refinement.feedback_text = req.feedback_text
    if req.context_filter is not None:
        refinement.context_filter = req.context_filter
    if req.active is not None:
        refinement.active = req.active

    db.commit()
    db.refresh(refinement)
    return _refinement_to_dict(refinement)


@router.delete("/api/admin/refinements/{refinement_id}")
def disable_refinement(
    refinement_id: int,
    db: Session = Depends(db_session),
) -> dict[str, str]:
    """Admin: disable (soft-delete) a refinement."""
    refinement = db.query(AIRefinement).get(refinement_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="Refinement not found")

    refinement.active = False
    db.commit()
    return {"status": "disabled"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _refinement_to_dict(r: AIRefinement) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "output_type": r.output_type,
        "feedback_text": r.feedback_text,
        "context_filter": r.context_filter,
        "scope": r.scope.value if hasattr(r.scope, "value") else str(r.scope),
        "active": r.active,
        "effectiveness": r.effectiveness or 0,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
