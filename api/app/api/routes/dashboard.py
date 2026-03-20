from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter()


@router.get("/upcoming-meetings")
def upcoming_meetings(
    request: Request,
    db: Session = Depends(db_session),
    days: int = Query(7, ge=1, le=30),
) -> dict:
    from app.models.entities import ResearchReport

    org_id = int(request.headers.get("X-Org-Id", "1"))
    cutoff = datetime.utcnow() + timedelta(days=days)

    reports = (
        db.query(ResearchReport)
        .filter(
            ResearchReport.org_id == org_id,
            ResearchReport.report_type == "pre_call",
            ResearchReport.created_at >= datetime.utcnow() - timedelta(days=30),
        )
        .order_by(ResearchReport.created_at.desc())
        .limit(50)
        .all()
    )

    return {
        "meetings": [
            {
                "id": r.id,
                "account_id": r.account_id,
                "meeting_id": r.meeting_id,
                "status": r.status.value if r.status else "pending",
                "created_at": str(r.created_at),
            }
            for r in reports
        ]
    }


@router.get("/recent-calls")
def recent_calls(
    request: Request,
    db: Session = Depends(db_session),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    from app.models.entities import ChorusCall, CallArtifact, ResearchReport

    calls = (
        db.query(ChorusCall)
        .order_by(ChorusCall.date.desc())
        .limit(limit)
        .all()
    )

    result = []
    for call in calls:
        artifact = db.query(CallArtifact).filter(CallArtifact.chorus_call_id == call.chorus_call_id).first()
        postcall = (
            db.query(ResearchReport)
            .filter(ResearchReport.report_type == "post_call")
            .filter(ResearchReport.raw_sources.isnot(None))
            .first()
        )
        result.append({
            "chorus_call_id": call.chorus_call_id,
            "date": str(call.date),
            "account": call.account,
            "rep_email": call.rep_email,
            "has_artifact": artifact is not None,
            "has_postcall_report": postcall is not None,
            "summary": artifact.summary if artifact else None,
        })

    return {"calls": result}


@router.get("/pipeline")
def pipeline_analytics(
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import Deal

    org_id = int(request.headers.get("X-Org-Id", "1"))
    deals = db.query(Deal).filter(Deal.org_id == org_id).all()

    by_stage: dict[str, list] = {}
    total_value = 0.0
    at_risk = 0

    for d in deals:
        stage = d.stage or "unknown"
        if stage not in by_stage:
            by_stage[stage] = []
        amount = float(d.amount) if d.amount else 0.0
        by_stage[stage].append({
            "id": d.id,
            "name": d.name,
            "amount": amount,
            "close_date": str(d.close_date) if d.close_date else None,
            "status": d.status.value if d.status else "open",
        })
        total_value += amount
        metadata = d.metadata_json or {}
        if metadata.get("risk_flag"):
            at_risk += 1

    return {
        "total_deals": len(deals),
        "total_value": total_value,
        "at_risk": at_risk,
        "by_stage": by_stage,
    }


@router.get("/competitive-intel")
def competitive_intel_feed(
    request: Request,
    db: Session = Depends(db_session),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    from app.models.entities import CompetitorIntel

    org_id = int(request.headers.get("X-Org-Id", "1"))
    items = (
        db.query(CompetitorIntel)
        .filter(CompetitorIntel.org_id == org_id)
        .order_by(CompetitorIntel.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": i.id,
                "competitor_name": i.competitor_name,
                "intel_type": i.intel_type.value if i.intel_type else None,
                "title": i.title,
                "summary": i.summary,
                "source_url": i.source_url,
                "is_notable": i.is_notable,
                "created_at": str(i.created_at),
            }
            for i in items
        ]
    }


@router.get("/content-gaps")
def content_gaps(
    request: Request,
    db: Session = Depends(db_session),
    days: int = Query(30, ge=1, le=90),
    min_frequency: int = Query(2, ge=1, le=20),
    gap_threshold: int = Query(2, ge=0, le=10),
) -> dict:
    from app.models.entities import Conversation, KnowledgeIndex, Message, MessageRole

    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "what", "how", "when", "where", "why",
        "who", "which", "that", "this", "these", "those", "i", "we", "you",
        "they", "it", "my", "our", "your", "their", "its", "me", "us", "him",
        "her", "them", "not", "no", "so", "if", "as", "up", "out", "about",
        "into", "than", "then", "just", "also", "any", "all", "some", "more",
        "get", "got", "need", "want", "use", "make", "go", "going", "does",
    }

    org_id = int(request.headers.get("X-Org-Id", "1"))
    since = datetime.utcnow() - timedelta(days=days)

    # Fetch recent user messages scoped to this org via conversation join
    rows = (
        db.query(Message.content, Message.created_at)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.org_id == org_id,
            Message.role == MessageRole.user,
            Message.created_at >= since,
            Message.content.isnot(None),
        )
        .order_by(Message.created_at.desc())
        .limit(500)
        .all()
    )

    if not rows:
        return {"gaps": [], "analyzed_messages": 0, "period_days": days}

    def extract_keywords(text: str) -> list[str]:
        words = text.lower().split()
        return [
            w.strip(".,!?;:\"'()[]")
            for w in words
            if len(w) > 3 and w.strip(".,!?;:\"'()[]") not in STOPWORDS
        ]

    # Build topic clusters keyed by their two most-frequent keywords
    # {topic_key: {"keywords": [...], "messages": [...], "last_asked": datetime}}
    topic_clusters: dict[str, dict] = {}

    for content, created_at in rows:
        keywords = extract_keywords(content)
        if not keywords:
            continue
        # Use top-2 unique keywords (by order of appearance) as the cluster key
        seen: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.append(kw)
            if len(seen) == 2:
                break
        topic_key = " ".join(seen) if seen else seen[0] if seen else None
        if not topic_key:
            continue

        if topic_key not in topic_clusters:
            topic_clusters[topic_key] = {
                "keywords": seen,
                "messages": [],
                "last_asked": created_at,
            }
        topic_clusters[topic_key]["messages"].append(content)
        if created_at > topic_clusters[topic_key]["last_asked"]:
            topic_clusters[topic_key]["last_asked"] = created_at

    # Filter to clusters asked at least min_frequency times
    frequent_topics = {
        key: data
        for key, data in topic_clusters.items()
        if len(data["messages"]) >= min_frequency
    }

    # For each frequent topic, count matching knowledge_index rows
    gaps = []
    for topic_key, data in frequent_topics.items():
        keywords = data["keywords"]
        frequency = len(data["messages"])

        match_count = 0
        for kw in keywords:
            match_count += (
                db.query(func.count(KnowledgeIndex.id))
                .filter(
                    KnowledgeIndex.org_id == org_id,
                    KnowledgeIndex.chunk_text.ilike(f"%{kw}%"),
                )
                .scalar()
                or 0
            )

        if match_count <= gap_threshold:
            gaps.append({
                "topic": topic_key,
                "keywords": keywords,
                "frequency": frequency,
                "last_asked": str(data["last_asked"]),
                "knowledge_matches": match_count,
                "sample_question": data["messages"][0][:200],
            })

    # Sort by frequency descending so highest-priority gaps appear first
    gaps.sort(key=lambda g: g["frequency"], reverse=True)

    return {
        "gaps": gaps,
        "analyzed_messages": len(rows),
        "period_days": days,
    }


@router.get("/api-usage")
def api_usage(
    request: Request,
    db: Session = Depends(db_session),
    days: int = Query(30, ge=1, le=90),
) -> dict:
    from app.models.entities import APIUsageLog

    org_id = int(request.headers.get("X-Org-Id", "1"))
    since = datetime.utcnow() - timedelta(days=days)

    logs = (
        db.query(
            APIUsageLog.source,
            func.count(APIUsageLog.id).label("call_count"),
            func.sum(APIUsageLog.tokens_used).label("total_tokens"),
            func.sum(APIUsageLog.estimated_cost_usd).label("total_cost"),
        )
        .filter(APIUsageLog.org_id == org_id, APIUsageLog.created_at >= since)
        .group_by(APIUsageLog.source)
        .all()
    )

    return {
        "period_days": days,
        "by_source": [
            {
                "source": row.source,
                "call_count": row.call_count,
                "total_tokens": int(row.total_tokens or 0),
                "total_cost_usd": float(row.total_cost or 0),
            }
            for row in logs
        ],
    }
