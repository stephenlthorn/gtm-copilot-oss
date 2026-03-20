from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter()


@router.get("")
def list_accounts(
    request: Request,
    db: Session = Depends(db_session),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    from app.models.entities import Account

    org_id = int(request.headers.get("X-Org-Id", "1"))
    query = db.query(Account).filter(Account.org_id == org_id)
    if search:
        query = query.filter(Account.name.ilike(f"%{search}%"))
    total = query.count()
    accounts = query.order_by(Account.updated_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "industry": a.industry,
                "website": a.website,
                "employee_count": a.employee_count,
                "revenue_range": a.revenue_range,
                "external_id": a.external_id,
                "crm_source": a.crm_source,
            }
            for a in accounts
        ],
    }


@router.get("/{account_id}")
def get_account(
    account_id: int,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import Account, Deal, Contact, ResearchReport, ChorusCall

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    deals = db.query(Deal).filter(Deal.account_id == account_id).all()
    contacts = db.query(Contact).filter(Contact.account_id == account_id).all()
    reports = (
        db.query(ResearchReport)
        .filter(ResearchReport.account_id == account_id)
        .order_by(ResearchReport.created_at.desc())
        .limit(10)
        .all()
    )
    calls = (
        db.query(ChorusCall)
        .filter(ChorusCall.account == account.name)
        .order_by(ChorusCall.date.desc())
        .limit(10)
        .all()
    )

    return {
        "account": {
            "id": account.id,
            "name": account.name,
            "industry": account.industry,
            "website": account.website,
            "employee_count": account.employee_count,
            "revenue_range": account.revenue_range,
            "description": account.description,
            "metadata": account.metadata_json,
        },
        "deals": [
            {"id": d.id, "name": d.name, "stage": d.stage, "amount": float(d.amount) if d.amount else None, "status": d.status.value if d.status else "open"}
            for d in deals
        ],
        "contacts": [
            {"id": c.id, "name": c.name, "title": c.title, "email": c.email}
            for c in contacts
        ],
        "recent_reports": [
            {"id": r.id, "report_type": r.report_type.value if r.report_type else None, "status": r.status.value if r.status else None, "created_at": str(r.created_at)}
            for r in reports
        ],
        "recent_calls": [
            {"chorus_call_id": c.chorus_call_id, "date": str(c.date), "rep_email": c.rep_email}
            for c in calls
        ],
    }


@router.get("/{account_id}/deals")
def get_account_deals(
    account_id: int,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import Deal

    deals = db.query(Deal).filter(Deal.account_id == account_id).all()
    return {
        "deals": [
            {
                "id": d.id,
                "name": d.name,
                "stage": d.stage,
                "amount": float(d.amount) if d.amount else None,
                "close_date": str(d.close_date) if d.close_date else None,
                "status": d.status.value if d.status else "open",
                "owner_user_id": d.owner_user_id,
            }
            for d in deals
        ]
    }


@router.get("/{account_id}/contacts")
def get_account_contacts(
    account_id: int,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import Contact

    contacts = db.query(Contact).filter(Contact.account_id == account_id).all()
    return {
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "title": c.title,
                "email": c.email,
                "linkedin_url": c.linkedin_url,
            }
            for c in contacts
        ]
    }


@router.get("/{account_id}/reports")
def get_account_reports(
    account_id: int,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import ResearchReport

    reports = (
        db.query(ResearchReport)
        .filter(ResearchReport.account_id == account_id)
        .order_by(ResearchReport.created_at.desc())
        .all()
    )
    return {
        "reports": [
            {
                "id": r.id,
                "report_type": r.report_type.value if r.report_type else None,
                "status": r.status.value if r.status else None,
                "meeting_id": r.meeting_id,
                "sections": r.sections,
                "created_at": str(r.created_at),
            }
            for r in reports
        ]
    }


@router.get("/{account_id}/calls")
def get_account_calls(
    account_id: int,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import Account, ChorusCall, CallArtifact

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    calls = (
        db.query(ChorusCall)
        .filter(ChorusCall.account == account.name)
        .order_by(ChorusCall.date.desc())
        .all()
    )

    result = []
    for call in calls:
        artifact = db.query(CallArtifact).filter(CallArtifact.chorus_call_id == call.chorus_call_id).first()
        result.append({
            "chorus_call_id": call.chorus_call_id,
            "date": str(call.date),
            "rep_email": call.rep_email,
            "se_email": call.se_email,
            "participants": call.participants,
            "summary": artifact.summary if artifact else None,
            "next_steps": artifact.next_steps if artifact else [],
        })

    return {"calls": result}
