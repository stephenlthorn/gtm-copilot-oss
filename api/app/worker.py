from __future__ import annotations

from datetime import date

from celery import Celery

from app.core.settings import get_settings
from app.db.init_db import init_db
import app.tasks.indexing_tasks  # noqa: F401 — registers v2 Celery tasks
from app.db.session import SessionLocal
from app.ingest.drive_ingestor import DriveIngestor
from app.ingest.transcript_ingestor import TranscriptIngestor

settings = get_settings()
celery_app = Celery("gtm_copilot", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "daily-ingestion-v2": {
            "task": "full_reindex_v2",
            "schedule": 24 * 60 * 60,
        }
    },
)


@celery_app.task(name="sync_drive")
def sync_drive_task(since: str | None = None) -> dict:
    init_db()
    from dateutil.parser import isoparse

    since_dt = isoparse(since) if since else None
    with SessionLocal() as db:
        return DriveIngestor(db).sync(since=since_dt)


@celery_app.task(name="sync_calls")
def sync_calls_task(since: str | None = None) -> dict:
    init_db()
    since_date = date.fromisoformat(since) if since else None
    with SessionLocal() as db:
        return TranscriptIngestor(db).sync(since=since_date)


@celery_app.task(name="sync_chorus")
def sync_chorus_task(since: str | None = None) -> dict:
    # Legacy alias for existing schedules/integrations.
    return sync_calls_task(since=since)


@celery_app.task(name="daily_ingestion")
def daily_ingestion_task() -> dict:
    init_db()
    with SessionLocal() as db:
        drive = DriveIngestor(db).sync()
        calls = TranscriptIngestor(db).sync()
    return {"drive": drive, "calls": calls}
