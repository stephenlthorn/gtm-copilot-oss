from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.entities import (
    ReportStatus,
    ReportType,
    ResearchReport,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TriggerResearchRequest(BaseModel):
    company_name: str
    user_id: int
    org_id: int
    contact_id: int | None = None
    meeting_id: str | None = None


class TriggerResearchResponse(BaseModel):
    task_id: str
    status: str = "queued"


class VerifyCompanyRequest(BaseModel):
    company_name: str
    org_id: int


class CompanyVerificationResponse(BaseModel):
    name: str
    industry: str
    website: str
    employee_count_estimate: int | None
    confidence: float
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class ReportSummary(BaseModel):
    id: int
    account_id: int
    report_type: str
    status: str
    meeting_id: str | None = None
    created_at: str | None = None


class ReportDetail(BaseModel):
    id: int
    account_id: int
    contact_id: int | None = None
    report_type: str
    status: str
    meeting_id: str | None = None
    sections: dict[str, Any] = Field(default_factory=dict)
    raw_sources: dict[str, Any] | None = None
    follow_up_email: str | None = None
    generated_by_user_id: int | None = None
    org_id: int
    created_at: str | None = None
    updated_at: str | None = None


class RefineRequest(BaseModel):
    user_id: int
    feedback_text: str
    context_filter: dict[str, Any] | None = None


class RefineResponse(BaseModel):
    refinement_id: int
    status: str = "created"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/trigger", response_model=TriggerResearchResponse)
def trigger_research(
    req: TriggerResearchRequest,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Manually trigger pre-call research for a company.

    Enqueues a Celery task and returns the task ID immediately.
    """
    from app.tasks.research_tasks import run_precall_research

    task = run_precall_research.delay(
        company_name=req.company_name,
        user_id=req.user_id,
        org_id=req.org_id,
        meeting_id=req.meeting_id,
        contact_id=req.contact_id,
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/verify-company", response_model=CompanyVerificationResponse)
async def verify_company(
    req: VerifyCompanyRequest,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Company verification step: LLM proposes company info for user confirmation."""
    from app.services.research.company_verify import CompanyVerifyService

    service = CompanyVerifyService(db)
    verification = await service.verify_company(req.company_name, req.org_id)
    return {
        "name": verification.name,
        "industry": verification.industry,
        "website": verification.website,
        "employee_count_estimate": verification.employee_count_estimate,
        "confidence": verification.confidence,
        "alternatives": verification.alternatives,
    }


@router.get("/reports", response_model=list[ReportSummary])
def list_reports(
    org_id: int = Query(...),
    account_id: int | None = Query(None),
    report_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    """List research reports with optional filters."""
    query = db.query(ResearchReport).filter_by(org_id=org_id)

    if account_id is not None:
        query = query.filter_by(account_id=account_id)
    if report_type is not None:
        query = query.filter_by(report_type=report_type)
    if status is not None:
        query = query.filter_by(status=status)

    reports = query.order_by(ResearchReport.created_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "report_type": r.report_type.value if hasattr(r.report_type, "value") else str(r.report_type),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "meeting_id": r.meeting_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: int,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Get a specific research report by ID."""
    report = db.query(ResearchReport).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "account_id": report.account_id,
        "contact_id": report.contact_id,
        "report_type": report.report_type.value if hasattr(report.report_type, "value") else str(report.report_type),
        "status": report.status.value if hasattr(report.status, "value") else str(report.status),
        "meeting_id": report.meeting_id,
        "sections": report.sections or {},
        "raw_sources": report.raw_sources,
        "follow_up_email": report.follow_up_email,
        "generated_by_user_id": report.generated_by_user_id,
        "org_id": report.org_id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@router.post("/reports/{report_id}/refine", response_model=RefineResponse)
def refine_report(
    report_id: int,
    req: RefineRequest,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Submit AI refinement feedback for a report.

    Creates a new refinement rule that will be applied to future report
    generation for this user.
    """
    report = db.query(ResearchReport).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    output_type = report.report_type.value if hasattr(report.report_type, "value") else str(report.report_type)

    from app.services.research.refinement_service import RefinementService

    service = RefinementService(db)
    refinement = service.add_refinement(
        user_id=req.user_id,
        output_type=output_type,
        feedback_text=req.feedback_text,
        context_filter=req.context_filter,
    )
    return {"refinement_id": refinement.id, "status": "created"}
