from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.db.session import SessionLocal
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="run_precall_research", bind=True, max_retries=2)
def run_precall_research(
    self: Any,
    company_name: str,
    user_id: int,
    org_id: int,
    meeting_id: str | None = None,
    contact_id: int | None = None,
) -> dict[str, Any]:
    """Celery task to run the full pre-call research pipeline."""
    from app.services.research.orchestrator import ResearchOrchestrator

    try:
        with SessionLocal() as db:
            orchestrator = ResearchOrchestrator(db)
            report = _run_async(
                orchestrator.trigger_precall_research(
                    company_name=company_name,
                    user_id=user_id,
                    org_id=org_id,
                    meeting_id=meeting_id,
                    contact_id=contact_id,
                )
            )
            return {
                "report_id": report.id,
                "status": report.status.value if report.status else "unknown",
                "account_id": report.account_id,
            }
    except Exception as exc:
        logger.exception("Pre-call research task failed for %s", company_name)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="run_postcall_research", bind=True, max_retries=2)
def run_postcall_research(
    self: Any,
    chorus_call_id: str,
    org_id: int,
) -> dict[str, Any]:
    """Celery task to run the post-call analysis pipeline."""
    from app.services.research.orchestrator import ResearchOrchestrator

    try:
        with SessionLocal() as db:
            orchestrator = ResearchOrchestrator(db)
            report = _run_async(
                orchestrator.trigger_postcall_research(
                    chorus_call_id=chorus_call_id,
                    org_id=org_id,
                )
            )
            return {
                "report_id": report.id,
                "status": report.status.value if report.status else "unknown",
                "has_follow_up": report.follow_up_email is not None,
            }
    except Exception as exc:
        logger.exception("Post-call research task failed for %s", chorus_call_id)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="scan_calendars")
def scan_calendars() -> dict[str, Any]:
    """Periodic task: scan all users' calendars and trigger research for upcoming meetings."""
    from app.models.entities import User
    from app.services.research.calendar_scanner import CalendarScannerService

    results: dict[str, Any] = {"users_scanned": 0, "triggers_found": 0, "tasks_launched": 0}

    with SessionLocal() as db:
        users = db.query(User).all()
        scanner = CalendarScannerService(db)

        for user in users:
            try:
                triggers = _run_async(scanner.scan_upcoming(user.id, user.org_id))
                results["users_scanned"] += 1
                results["triggers_found"] += len(triggers)

                for trigger in triggers:
                    if trigger.needs_research:
                        run_precall_research.delay(
                            company_name=trigger.company_name,
                            user_id=user.id,
                            org_id=user.org_id,
                            meeting_id=trigger.event_id,
                        )
                        results["tasks_launched"] += 1

            except Exception:
                logger.exception("Calendar scan failed for user %d", user.id)

    return results


celery_app.conf.beat_schedule["scan-calendars"] = {
    "task": "scan_calendars",
    "schedule": 60 * 60,  # Every hour
}
