from __future__ import annotations

import logging
from datetime import date, timedelta

from celery.schedules import crontab
from sqlalchemy import select

from app.core.settings import get_settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.worker import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


celery_app.conf.beat_schedule.update({
    "competitive-monitoring-daily": {
        "task": "run_competitive_monitoring",
        "schedule": crontab(hour=6, minute=0),
    },
    "deal-risk-scan-daily": {
        "task": "scan_deal_risks",
        "schedule": crontab(hour=8, minute=0),
    },
})


@celery_app.task(name="send_notification")
def send_notification(notification_dict: dict) -> dict:
    """Send a notification immediately."""
    init_db()
    from app.services.notifications.dispatcher import NotificationDispatcher
    from app.services.notifications.types import Notification

    notification = Notification.from_dict(notification_dict)

    with SessionLocal() as db:
        dispatcher = NotificationDispatcher(db)
        success = dispatcher.dispatch(notification)

    return {
        "success": success,
        "type": notification.type.value,
        "user_id": notification.user_id,
    }


@celery_app.task(name="scheduled_notification")
def scheduled_notification(notification_dict: dict) -> dict:
    """Send a notification that was previously scheduled (called via ETA/countdown)."""
    init_db()
    from app.services.notifications.dispatcher import NotificationDispatcher
    from app.services.notifications.types import Notification, NotificationTiming

    notification = Notification.from_dict(notification_dict)

    with SessionLocal() as db:
        dispatcher = NotificationDispatcher(db)
        user = dispatcher._get_user(notification.user_id)
        if not user:
            logger.error("User %d not found for scheduled notification", notification.user_id)
            return {"success": False, "error": "user_not_found"}

        pref = dispatcher._preferences_service.get_preference_for_type(
            notification.user_id, notification.type.value
        )
        success = dispatcher._send_now(notification, user, pref)

    return {
        "success": success,
        "type": notification.type.value,
        "user_id": notification.user_id,
    }


@celery_app.task(name="run_competitive_monitoring")
def run_competitive_monitoring(org_id: int) -> dict:
    """Run competitive monitoring for an organization.

    Scheduled daily at 6am via Celery Beat.
    """
    init_db()
    from app.services.notifications.competitive_monitor import CompetitiveMonitorService

    with SessionLocal() as db:
        service = CompetitiveMonitorService(db)
        results = service.run_monitoring(org_id)

    return {
        "org_id": org_id,
        "items_found": len(results),
        "notable_items": sum(1 for r in results if r.is_notable),
    }


@celery_app.task(name="scan_deal_risks")
def scan_deal_risks(org_id: int) -> dict:
    """Scan for deal risks: stale deals, approaching close dates, missing next steps.

    Scheduled daily at 8am via Celery Beat.
    """
    init_db()
    from app.models.entities import Deal, DealStatus, User
    from app.services.notifications.dispatcher import NotificationDispatcher
    from app.services.notifications.types import Notification, NotificationType

    with SessionLocal() as db:
        today = date.today()
        stale_threshold = today - timedelta(days=14)

        stmt = select(Deal).where(
            Deal.org_id == org_id,
            Deal.status == DealStatus.open,
        )
        deals = db.execute(stmt).scalars().all()

        risks_found: list[dict] = []
        dispatcher = NotificationDispatcher(db)

        for deal in deals:
            risk_reasons: list[str] = []

            if deal.close_date and deal.close_date <= today:
                risk_reasons.append(
                    f"Close date has passed ({deal.close_date.isoformat()})"
                )

            if deal.close_date and deal.close_date <= today + timedelta(days=7):
                risk_reasons.append(
                    f"Close date is within 7 days ({deal.close_date.isoformat()})"
                )

            if deal.updated_at and deal.updated_at.date() < stale_threshold:
                risk_reasons.append(
                    f"No updates for {(today - deal.updated_at.date()).days} days"
                )

            if not risk_reasons:
                continue

            risk_info = {
                "deal_id": deal.id,
                "deal_name": deal.name or f"Deal #{deal.id}",
                "account_id": deal.account_id,
                "reasons": risk_reasons,
            }
            risks_found.append(risk_info)

            if deal.owner_user_id:
                notification = Notification(
                    type=NotificationType.DEAL_RISK,
                    title=f"Deal Risk: {deal.name or 'Unnamed Deal'}",
                    body="; ".join(risk_reasons),
                    user_id=deal.owner_user_id,
                    org_id=org_id,
                    metadata={
                        "risk": {
                            "account": f"Account #{deal.account_id}",
                            "severity": "high" if deal.close_date and deal.close_date <= today else "medium",
                            "description": "; ".join(risk_reasons),
                            "deal_name": deal.name or f"Deal #{deal.id}",
                        }
                    },
                )
                try:
                    dispatcher.dispatch(notification)
                except Exception:
                    logger.exception(
                        "Failed to notify user %d about deal risk for deal %d",
                        deal.owner_user_id,
                        deal.id,
                    )

    return {
        "org_id": org_id,
        "deals_scanned": len(deals),
        "risks_found": len(risks_found),
    }
