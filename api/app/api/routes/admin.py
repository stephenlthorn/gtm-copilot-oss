from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
import logging
import re

logger = logging.getLogger(__name__)

import httpx
from dateutil.parser import isoparse
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from openai import OpenAI
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.settings import get_settings
from app.ingest.drive_ingestor import DriveIngestor
from app.ingest.feishu_ingestor import FeishuIngestor
from app.ingest.transcript_ingestor import TranscriptIngestor
from app.models import AuditLog, AuditStatus, KBConfig
from app.models.feedback import AIFeedback, PromptSuggestion
from app.prompts.personas import normalize_persona
from app.prompts.templates import (
    SYSTEM_ORACLE,
    SYSTEM_CALL_COACH,
    SYSTEM_REP_EXECUTION,
    SYSTEM_SE_EXECUTION,
    SYSTEM_MARKETING_EXECUTION,
)
from app.schemas.kb_config import KBConfigRead, KBConfigUpdate
from app.services.audit import write_audit_log
from app.services.google_drive_credentials import GoogleDriveCredentialService
from app.services.google_drive_oauth import google_drive_oauth_state_store
from app.services.feishu_credentials import FeishuCredentialService
from app.services.feishu_oauth import feishu_oauth_state_store
from app.services.drive_sync_jobs import drive_sync_jobs

router = APIRouter()


def _request_user_email(request: Request, fallback: str | None = None) -> str | None:
    raw = (request.headers.get("X-User-Email") if request else "") or fallback or ""
    email = raw.strip().lower()
    return email or None


def _parse_token_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,\n\r\t ]+", raw)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _resolve_feishu_roots(config: KBConfig | None) -> list[str]:
    roots = _parse_token_list(config.feishu_root_tokens if config else None)
    legacy = (config.feishu_folder_token if config else "") or ""
    legacy = legacy.strip()
    if legacy and legacy not in roots:
        roots.append(legacy)
    return roots


def _resolve_feishu_creds(config: KBConfig | None) -> tuple[str, str]:
    settings = get_settings()
    app_id = ((config.feishu_app_id if config else None) or settings.feishu_app_id or "").strip()
    app_secret = ((config.feishu_app_secret if config else None) or settings.feishu_app_secret or "").strip()
    return app_id, app_secret


def _feishu_scopes() -> list[str]:
    settings = get_settings()
    raw = (settings.feishu_oauth_scopes or "").strip()
    scopes = [scope.strip() for scope in raw.split(" ") if scope.strip()]
    if not scopes:
        scopes = ["offline_access", "drive:drive:readonly", "docs:document:readonly"]
    return scopes


def _exchange_feishu_oauth_code(*, app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {app_id}:{app_secret}",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    endpoints = ["/authen/v1/oidc/access_token", "/authen/v1/access_token"]
    errors: list[str] = []
    for endpoint in endpoints:
        url = f"{settings.feishu_base_url.rstrip('/')}{endpoint}"
        try:
            res = httpx.post(url, headers=headers, json=body, timeout=20.0)
            if res.status_code >= 400:
                errors.append(f"{endpoint}:HTTP{res.status_code}")
                continue
            payload = res.json()
            if payload.get("code") != 0:
                errors.append(f"{endpoint}:{payload.get('msg') or payload.get('code')}")
                continue
            data = payload.get("data") or {}
            if data.get("access_token"):
                return data
            errors.append(f"{endpoint}:missing_access_token")
        except Exception as exc:
            errors.append(f"{endpoint}:{exc}")
    raise RuntimeError(f"Feishu token exchange failed ({'; '.join(errors)})")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/security/settings")
def security_settings() -> dict:
    settings = get_settings()
    return {
        "enterprise_mode": settings.enterprise_mode,
        "security_require_private_llm_endpoint": settings.security_require_private_llm_endpoint,
        "security_allowed_llm_base_urls": settings.allowed_llm_base_urls,
        "llm_base_url_configured": bool(settings.openai_base_url),
        "llm_base_url_allowed": settings.is_allowed_llm_base_url(settings.openai_base_url)
        if settings.openai_base_url
        else None,
        "security_fail_closed_on_missing_llm_key": settings.security_fail_closed_on_missing_llm_key,
        "security_fail_closed_on_missing_embedding_key": settings.security_fail_closed_on_missing_embedding_key,
        "security_redact_before_llm": settings.security_redact_before_llm,
        "security_redact_audit_logs": settings.security_redact_audit_logs,
        "security_trusted_host_allowlist": settings.trusted_hosts,
        "internal_domain_allowlist": settings.domain_allowlist,
        "email_mode": settings.email_mode,
        "smtp_tls_configured": bool(settings.smtp_username and settings.smtp_password),
    }


@router.post("/sync/drive")
def sync_drive(
    request: Request,
    since: str | None = Query(default=None, description="ISO timestamp"),
    db: Session = Depends(db_session),
) -> dict:
    user_email = _request_user_email(request)
    since_dt = isoparse(since) if since else None
    ingestor = DriveIngestor(db)
    try:
        result = ingestor.sync(since=since_dt, user_email=user_email)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit_log(
        db,
        actor=user_email or "system",
        action="sync_drive",
        input_payload={"since": since, "user_email": user_email},
        retrieval_payload={},
        output_payload=result,
        status=AuditStatus.OK,
    )
    return result


@router.post("/sync/drive/start")
def sync_drive_start(
    request: Request,
    since: str | None = Query(default=None, description="ISO timestamp"),
) -> dict:
    user_email = _request_user_email(request)
    return drive_sync_jobs.start(since, user_email=user_email)


@router.get("/sync/drive/jobs/latest")
def sync_drive_latest_job(request: Request) -> dict:
    user_email = _request_user_email(request)
    job = drive_sync_jobs.latest(user_email=user_email)
    return {"job": job}


@router.get("/sync/drive/jobs/{job_id}")
def sync_drive_job_status(job_id: str, request: Request) -> dict:
    user_email = _request_user_email(request)
    job = drive_sync_jobs.get(job_id)
    if not job:
        return {"job": None}
    if (job.get("user_email") or None) != (user_email or None):
        return {"job": None}
    return {"job": job}


@router.get("/sync/drive/jobs")
def sync_drive_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    user_email = _request_user_email(request)
    return {"jobs": drive_sync_jobs.list(limit=limit, user_email=user_email)}


@router.get("/drive/oauth/start")
def drive_oauth_start(
    request: Request,
    redirect_uri: str = Query(...),
) -> dict:
    settings = get_settings()
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    if not settings.google_drive_client_id or not settings.google_drive_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google Drive OAuth client is not configured. Set GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET.",
        )
    payload = google_drive_oauth_state_store.create_auth_url(user_email=user_email, redirect_uri=redirect_uri)
    return {"auth_url": payload["auth_url"]}


@router.post("/drive/oauth/exchange")
def drive_oauth_exchange(
    request: Request,
    body: dict | None = Body(default=None),
    db: Session = Depends(db_session),
) -> dict:
    settings = get_settings()
    payload = body or {}
    user_email = _request_user_email(request, fallback=payload.get("user_email"))
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    code = str(payload.get("code") or "").strip()
    state = str(payload.get("state") or "").strip()
    redirect_uri = str(payload.get("redirect_uri") or "").strip()
    if not code or not state or not redirect_uri:
        raise HTTPException(status_code=400, detail="code, state, and redirect_uri are required.")

    if not settings.google_drive_client_id or not settings.google_drive_client_secret:
        raise HTTPException(status_code=500, detail="Google Drive OAuth client is not configured.")

    try:
        pending = google_drive_oauth_state_store.consume(
            state=state,
            user_email=user_email,
            redirect_uri=redirect_uri,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token_form = {
        "code": code,
        "client_id": settings.google_drive_client_id,
        "client_secret": settings.google_drive_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": pending.verifier,
    }
    token_res = httpx.post("https://oauth2.googleapis.com/token", data=token_form, timeout=20.0)
    if token_res.status_code >= 400:
        raise HTTPException(status_code=token_res.status_code, detail=f"Google token exchange failed: {token_res.text[:400]}")
    token_payload = token_res.json()

    cred_service = GoogleDriveCredentialService(db)
    previous = cred_service.get_stored_payload(user_email) or {}
    previous_refresh = previous.get("refresh_token")

    stored_payload = cred_service.token_payload_from_oauth_exchange(token_payload)
    if not stored_payload.get("refresh_token") and previous_refresh:
        stored_payload["refresh_token"] = previous_refresh
    cred_service.upsert_token_payload(user_email, stored_payload, commit=True)

    write_audit_log(
        db,
        actor=user_email,
        action="drive_oauth_exchange",
        input_payload={"user_email": user_email},
        retrieval_payload={},
        output_payload={"connected": True},
        status=AuditStatus.OK,
    )
    return {"connected": True}


@router.get("/drive/status")
def drive_status(request: Request, db: Session = Depends(db_session)) -> dict:
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    status = GoogleDriveCredentialService(db).get_status(user_email)
    return status


@router.delete("/drive/credentials")
def drive_disconnect(request: Request, db: Session = Depends(db_session)) -> dict:
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    deleted = GoogleDriveCredentialService(db).delete_for_user(user_email, commit=True)
    write_audit_log(
        db,
        actor=user_email,
        action="drive_oauth_disconnect",
        input_payload={"user_email": user_email},
        retrieval_payload={},
        output_payload={"deleted": deleted},
        status=AuditStatus.OK,
    )
    return {"connected": False, "deleted": deleted}


@router.get("/feishu/oauth/start")
def feishu_oauth_start(
    request: Request,
    redirect_uri: str = Query(...),
    db: Session = Depends(db_session),
) -> dict:
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")

    kb_config: KBConfig | None = db.get(KBConfig, 1)
    app_id, app_secret = _resolve_feishu_creds(kb_config)
    if not app_id or not app_secret:
        raise HTTPException(
            status_code=500,
            detail="Feishu OAuth app is not configured. Set feishu_app_id and feishu_app_secret.",
        )

    payload = feishu_oauth_state_store.create_auth_url(
        user_email=user_email,
        redirect_uri=redirect_uri,
        app_id=app_id,
        scopes=_feishu_scopes(),
    )
    return {"auth_url": payload["auth_url"]}


@router.post("/feishu/oauth/exchange")
def feishu_oauth_exchange(
    request: Request,
    body: dict | None = Body(default=None),
    db: Session = Depends(db_session),
) -> dict:
    payload = body or {}
    user_email = _request_user_email(request, fallback=payload.get("user_email"))
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    code = str(payload.get("code") or "").strip()
    state = str(payload.get("state") or "").strip()
    redirect_uri = str(payload.get("redirect_uri") or "").strip()
    if not code or not state or not redirect_uri:
        raise HTTPException(status_code=400, detail="code, state, and redirect_uri are required.")

    kb_config: KBConfig | None = db.get(KBConfig, 1)
    app_id, app_secret = _resolve_feishu_creds(kb_config)
    if not app_id or not app_secret:
        raise HTTPException(status_code=500, detail="Feishu OAuth app is not configured.")

    try:
        feishu_oauth_state_store.consume(
            state=state,
            user_email=user_email,
            redirect_uri=redirect_uri,
            app_id=app_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        token_data = _exchange_feishu_oauth_code(
            app_id=app_id,
            app_secret=app_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cred_service = FeishuCredentialService(db)
    previous = cred_service.get_stored_payload(user_email) or {}
    previous_refresh = previous.get("refresh_token")
    stored_payload = FeishuCredentialService.token_payload_from_oauth_exchange(token_data)
    if not stored_payload.get("refresh_token") and previous_refresh:
        stored_payload["refresh_token"] = previous_refresh
    cred_service.upsert_token_payload(user_email, stored_payload, commit=True)

    write_audit_log(
        db,
        actor=user_email,
        action="feishu_oauth_exchange",
        input_payload={"user_email": user_email},
        retrieval_payload={},
        output_payload={"connected": True},
        status=AuditStatus.OK,
    )
    return {"connected": True}


@router.get("/feishu/status")
def feishu_status(request: Request, db: Session = Depends(db_session)) -> dict:
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    return FeishuCredentialService(db).get_status(user_email)


@router.delete("/feishu/credentials")
def feishu_disconnect(request: Request, db: Session = Depends(db_session)) -> dict:
    user_email = _request_user_email(request)
    if not user_email:
        raise HTTPException(status_code=400, detail="Missing signed-in user email.")
    deleted = FeishuCredentialService(db).delete_for_user(user_email, commit=True)
    write_audit_log(
        db,
        actor=user_email,
        action="feishu_oauth_disconnect",
        input_payload={"user_email": user_email},
        retrieval_payload={},
        output_payload={"deleted": deleted},
        status=AuditStatus.OK,
    )
    return {"connected": False, "deleted": deleted}


import threading as _threading
_calls_sync_lock = _threading.Lock()


def _sync_calls_impl(since: str | None, db: Session) -> dict:
    if since:
        since_date: date | None = date.fromisoformat(since)
    else:
        # Incremental: use latest call already in DB, or 2 years ago for first-ever sync
        from app.models import ChorusCall
        latest = db.execute(select(ChorusCall).order_by(ChorusCall.date.desc()).limit(1)).scalar_one_or_none()
        if latest and latest.date:
            since_date = latest.date
        else:
            since_date = date.today() - timedelta(days=730)
    ingestor = TranscriptIngestor(db)
    result = ingestor.sync(since=since_date)
    write_audit_log(
        db,
        actor="system",
        action="sync_calls",
        input_payload={"since": since},
        retrieval_payload={},
        output_payload=result,
        status=AuditStatus.OK,
    )
    return result


def _launch_calls_sync(since: str | None) -> dict:
    """Acquire lock and start background sync thread. Returns accepted/rejected dict."""
    import threading
    from app.db.session import SessionLocal

    if not _calls_sync_lock.acquire(blocking=False):
        return {"accepted": False, "reason": "sync already running"}

    def _run() -> None:
        bg_db = SessionLocal()
        try:
            _sync_calls_impl(since=since, db=bg_db)
        except Exception:
            logger.exception("Calls sync failed (since=%s)", since)
        finally:
            bg_db.close()
            _calls_sync_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"accepted": True, "since": since}


@router.post("/sync/calls")
def sync_calls(since: str | None = Query(default=None, description="YYYY-MM-DD")) -> dict:
    """Fire-and-forget sync — returns immediately, runs in background thread."""
    return _launch_calls_sync(since=since)


@router.post("/sync/calls/background")
def sync_calls_background() -> dict:
    """Incremental fire-and-forget sync (no since filter)."""
    return _launch_calls_sync(since=None)


@router.post("/sync/chorus")
def sync_chorus(since: str | None = Query(default=None, description="YYYY-MM-DD")) -> dict:
    """Legacy alias for /sync/calls — now also non-blocking."""
    return _launch_calls_sync(since=since)


@router.get("/audit")
def audit(limit: int = Query(default=100, ge=1, le=2000), db: Session = Depends(db_session)) -> list[dict]:
    rows = db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": str(row.id),
            "timestamp": row.timestamp,
            "actor": row.actor,
            "action": row.action,
            "status": row.status.value,
            "input": row.input_json,
            "retrieval": row.retrieval_json,
            "output": row.output_json,
            "error_message": row.error_message,
        }
        for row in rows
    ]


@router.get("/kb-config", response_model=KBConfigRead)
def get_kb_config(db: Session = Depends(db_session)):
    config = db.get(KBConfig, 1)
    if config is None:
        config = KBConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    normalized_persona = normalize_persona(config.persona_name)
    if normalized_persona != config.persona_name:
        config.persona_name = normalized_persona
        db.add(config)
        db.commit()
        db.refresh(config)
    if config.feature_flags_json is None:
        config.feature_flags_json = {}
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/backfill-status")
def get_backfill_status(db: Session = Depends(db_session)):
    from sqlalchemy import func, select
    from app.models.entities import KBChunk, KnowledgeIndex

    kb_count = db.execute(select(func.count()).select_from(KBChunk)).scalar() or 0
    ki_count = db.execute(select(func.count()).select_from(KnowledgeIndex)).scalar() or 0
    config = db.execute(select(KBConfig).limit(1)).scalar_one_or_none()
    cutover = config.retrieval_cutover if config is not None else False

    return {
        "kb_chunks_count": kb_count,
        "knowledge_index_count": ki_count,
        "cutover_complete": cutover,
        "kb_chunks_remaining": max(0, kb_count - ki_count),
    }


@router.put("/kb-config", response_model=KBConfigRead)
def update_kb_config(update: KBConfigUpdate, db: Session = Depends(db_session)):
    config = db.get(KBConfig, 1)
    if config is None:
        config = KBConfig(id=1)
    payload = update.model_dump(exclude_none=True)
    if "persona_name" in payload:
        payload["persona_name"] = normalize_persona(payload.get("persona_name"))
    if "persona_prompt" in payload:
        prompt = (payload.get("persona_prompt") or "").strip()
        payload["persona_prompt"] = prompt or None
    if "feishu_root_tokens" in payload:
        roots = _parse_token_list(payload.get("feishu_root_tokens"))
        payload["feishu_root_tokens"] = "\n".join(roots) if roots else None
    if "feishu_folder_token" in payload:
        token = (payload.get("feishu_folder_token") or "").strip()
        payload["feishu_folder_token"] = token or None
    if "feishu_app_id" in payload:
        app_id = (payload.get("feishu_app_id") or "").strip()
        payload["feishu_app_id"] = app_id or None
    if "feishu_app_secret" in payload:
        secret = (payload.get("feishu_app_secret") or "").strip()
        payload["feishu_app_secret"] = secret or None
    if "se_poc_kit_url" in payload:
        url = (payload.get("se_poc_kit_url") or "").strip()
        payload["se_poc_kit_url"] = url or None
    if "feature_flags_json" in payload:
        flags = payload.get("feature_flags_json") or {}
        payload["feature_flags_json"] = flags if isinstance(flags, dict) else {}

    for field, value in payload.items():
        setattr(config, field, value)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.post("/sync/feishu")
def sync_feishu(request: Request, db: Session = Depends(db_session)) -> dict:
    settings = get_settings()
    kb_config: KBConfig | None = db.get(KBConfig, 1)
    user_email = _request_user_email(request)
    app_id, app_secret = _resolve_feishu_creds(kb_config)
    roots = _resolve_feishu_roots(kb_config)
    global_mode = False
    if not roots:
        # Global mode: list all Feishu files visible to the current token.
        roots = [""]
        global_mode = True

    oauth_mode = bool(kb_config.feishu_oauth_enabled if kb_config else False)
    cred_service = FeishuCredentialService(db)

    if oauth_mode:
        if not user_email:
            return {
                "status": "error",
                "message": "Missing signed-in user email for Feishu OAuth mode.",
            }
        if not app_id or not app_secret:
            return {
                "status": "error",
                "message": "Feishu OAuth app_id / app_secret not configured.",
            }
        try:
            access_token = cred_service.get_access_token(
                user_email,
                app_id=app_id,
                app_secret=app_secret,
                base_url=settings.feishu_base_url,
            )
        except RuntimeError as exc:
            return {
                "status": "error",
                "message": f"Feishu OAuth is not connected for {user_email}. {exc}",
            }
        ingestor = FeishuIngestor(
            db,
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token,
            user_email=user_email,
        )
    else:
        if not app_id or not app_secret:
            return {"status": "error", "message": "Feishu app_id / app_secret not configured."}
        ingestor = FeishuIngestor(db, app_id=app_id, app_secret=app_secret)

    result = ingestor.sync_roots(roots, recursive=True)
    if oauth_mode and user_email:
        cred_service.update_last_synced(user_email)
    indexed = int(result.get("added", 0)) + int(result.get("updated", 0))
    errors = int(result.get("errors", 0))
    status_value = "ok"
    message: str | None = None
    if errors > 0 and indexed == 0:
        status_value = "error"
        message = "Feishu sync failed due to permissions or content access errors."
    elif errors > 0:
        status_value = "partial"
        message = "Feishu sync completed with some document-level errors."
    write_audit_log(
        db,
        actor=user_email or "system",
        action="sync_feishu",
        input_payload={
            "roots": roots,
            "oauth_mode": oauth_mode,
            "global_mode": global_mode,
            "user_email": user_email,
        },
        retrieval_payload={},
        output_payload=result,
        status=AuditStatus.OK,
    )
    return {"status": status_value, "message": message, **result}


SUGGESTION_THRESHOLD_DEFAULT = 3

BUILTIN_PROMPT_MAP = {
    "oracle": SYSTEM_ORACLE,
    "call_assistant": SYSTEM_CALL_COACH,
    "rep": SYSTEM_REP_EXECUTION,
    "se": SYSTEM_SE_EXECUTION,
    "marketing": SYSTEM_MARKETING_EXECUTION,
}


class FeedbackSuggestionRequest(PydanticBaseModel):
    mode: str
    failure_category: str
    prompt_type: str  # "persona" | "builtin"


@router.get("/feedback-alerts")
def get_feedback_alerts(db: Session = Depends(db_session)):
    """Return (mode, failure_category) combos where failure count >= threshold since last suggestion."""
    threshold = int(os.environ.get("SUGGESTION_THRESHOLD", SUGGESTION_THRESHOLD_DEFAULT))
    window_floor = datetime.now(timezone.utc) - timedelta(days=7)

    # All distinct (mode, failure_category) combos with any negative feedback
    combos = db.execute(
        select(AIFeedback.mode, AIFeedback.failure_category)
        .where(AIFeedback.rating == "negative")
        .where(AIFeedback.failure_category.isnot(None))
        .distinct()
    ).all()

    alerts = []
    for combo in combos:
        mode, category = combo.mode, combo.failure_category

        # Find most recent PromptSuggestion for this combo
        last_suggestion = db.execute(
            select(func.max(PromptSuggestion.created_at))
            .where(PromptSuggestion.mode == mode)
            .where(PromptSuggestion.failure_category == category)
        ).scalar()

        # Count failures since max(last_suggestion.created_at, now()-7days)
        since = max(last_suggestion, window_floor) if last_suggestion else window_floor

        count = db.execute(
            select(func.count(AIFeedback.id))
            .where(AIFeedback.rating == "negative")
            .where(AIFeedback.failure_category == category)
            .where(AIFeedback.mode == mode)
            .where(AIFeedback.created_at >= since)
        ).scalar()

        if count >= threshold:
            alerts.append({
                "mode": mode,
                "failure_category": category,
                "count": count,
                "threshold": threshold,
            })

    return alerts


@router.get("/feedback-patterns")
def get_feedback_patterns(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(db_session),
):
    """Aggregate negative feedback by (mode, failure_category) for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.execute(
        select(
            AIFeedback.mode,
            AIFeedback.failure_category,
            func.count(AIFeedback.id).label("count"),
            func.max(AIFeedback.created_at).label("last_seen"),
        )
        .where(AIFeedback.rating == "negative")
        .where(AIFeedback.failure_category.isnot(None))
        .where(AIFeedback.created_at >= cutoff)
        .group_by(AIFeedback.mode, AIFeedback.failure_category)
        .order_by(func.count(AIFeedback.id).desc())
        .limit(20)
    ).all()

    result = []
    for row in rows:
        examples_rows = db.execute(
            select(AIFeedback.query_text)
            .where(AIFeedback.rating == "negative")
            .where(AIFeedback.failure_category == row.failure_category)
            .where(AIFeedback.mode == row.mode)
            .where(AIFeedback.created_at >= cutoff)
            .order_by(AIFeedback.created_at.desc())
            .limit(2)
        ).scalars().all()

        result.append({
            "mode": row.mode,
            "failure_category": row.failure_category,
            "count": row.count,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            "examples": list(examples_rows),
        })

    return result


@router.get("/chunk-quality")
def chunk_quality_stats(
    limit: int = Query(default=50, ge=1, le=500),
    min_signals: int = Query(default=10, ge=1),
    db: Session = Depends(db_session),
):
    """Return chunks ranked by positive signal rate, for corpus quality review."""
    from app.models.feedback import ChunkQualitySignal
    from app.models.entities import KBChunk

    rows = db.execute(
        select(
            ChunkQualitySignal.chunk_id,
            func.sum(case((ChunkQualitySignal.signal == "cited_positive", 1), else_=0)).label("pos"),
            func.sum(case((ChunkQualitySignal.signal == "cited_negative", 1), else_=0)).label("neg"),
            func.sum(case((ChunkQualitySignal.signal == "retrieved_unused", 1), else_=0)).label("unused"),
            func.count().label("total"),
        )
        .group_by(ChunkQualitySignal.chunk_id)
        .having(func.count() >= min_signals)
        .order_by((
            func.sum(case((ChunkQualitySignal.signal == "cited_positive", 1), else_=0)) /
            func.nullif(
                func.sum(case((ChunkQualitySignal.signal == "cited_positive", 1), else_=0)) +
                func.sum(case((ChunkQualitySignal.signal == "cited_negative", 1), else_=0)),
                0
            )
        ).desc().nulls_last())
        .limit(limit)
    ).all()

    return [
        {
            "chunk_id": str(row.chunk_id),
            "cited_positive": int(row.pos),
            "cited_negative": int(row.neg),
            "retrieved_unused": int(row.unused),
            "total_signals": int(row.total),
            "positive_rate": round(row.pos / (row.pos + row.neg), 3) if (row.pos + row.neg) > 0 else None,
        }
        for row in rows
    ]


@router.post("/feedback-suggestions")
def create_feedback_suggestion(
    body: FeedbackSuggestionRequest,
    request: Request,
    db: Session = Depends(db_session),
):
    """Generate a GPT-4 prompt suggestion for a (mode, failure_category) pattern."""
    # 1. Load 5 most recent failing queries
    examples = db.execute(
        select(AIFeedback.query_text, AIFeedback.original_response)
        .where(AIFeedback.rating == "negative")
        .where(AIFeedback.failure_category == body.failure_category)
        .where(AIFeedback.mode == body.mode)
        .order_by(AIFeedback.created_at.desc())
        .limit(5)
    ).all()

    if not examples:
        raise HTTPException(status_code=404, detail="No failures found for this mode/category")

    # 2. Load current prompt
    if body.prompt_type == "persona":
        kb_config = db.get(KBConfig, 1)
        current_prompt = (kb_config.persona_prompt if kb_config else None) or ""
        if not current_prompt:
            raise HTTPException(status_code=404, detail="No persona prompt configured")
    elif body.prompt_type == "builtin":
        current_prompt = BUILTIN_PROMPT_MAP.get(body.mode)
        if not current_prompt:
            raise HTTPException(status_code=400, detail=f"No built-in prompt for mode: {body.mode}")
    else:
        raise HTTPException(status_code=422, detail="prompt_type must be 'persona' or 'builtin'")

    # 3. Build GPT-4o prompt
    formatted_examples = "\n\n".join(
        f"Query: {ex.query_text}\nResponse: {ex.original_response}"
        for ex in examples
    )
    system = (
        "You are a senior prompt engineer specializing in enterprise GTM AI systems for PingCAP (TiDB). "
        "Your job is to diagnose failure patterns in AI prompts and suggest precise, minimal edits that fix the root cause without introducing regressions.\n\n"
        "ANALYSIS FRAMEWORK:\n"
        "1. Pattern identification: What specific failure pattern do the examples share? (hallucination, wrong format, missed context, generic output, incorrect TiDB positioning, etc.)\n"
        "2. Root cause: Which section of the prompt allowed or caused this failure? (missing guardrail, ambiguous instruction, no example, wrong scoring, etc.)\n"
        "3. Minimal fix: What is the smallest edit that fixes the root cause? Do NOT rewrite the entire prompt — target the specific section that caused the failure.\n"
        "4. Regression check: Does your edit preserve all existing behavior for non-failing cases?\n\n"
        "CONSTRAINTS:\n"
        "- Preserve the prompt's existing structure, tone, and non-failing behavior.\n"
        "- Do NOT add generic instructions that don't directly address the failure pattern.\n"
        "- Do NOT remove existing guardrails or scoring rubrics unless they directly caused the failure.\n"
        "- The suggested_prompt must be the COMPLETE prompt text (not a diff), ready to deploy.\n"
        "- If the failure cannot be fixed via prompt edit alone (e.g., requires tool changes or data fixes), state this in reasoning."
    )
    user = f"""Mode: {body.mode}
Failure category: {body.failure_category}
Threshold: {len(examples)} users flagged this as '{body.failure_category}'

Recent failing queries and responses (analyze these for shared patterns):
{formatted_examples}

Current {body.prompt_type} prompt:
{current_prompt}

Return strict JSON with exactly these keys:
- "failure_pattern" (string — 1 sentence describing the shared pattern across failing examples)
- "root_cause" (string — which specific section or missing guardrail in the current prompt caused this)
- "reasoning" (string — 2-3 sentence explanation of the fix and why it addresses the root cause without regression)
- "suggested_prompt" (string — the COMPLETE revised prompt text, ready to deploy)
- "confidence" (string — "high" if pattern is clear and fix is targeted, "medium" if pattern is ambiguous, "low" if insufficient examples to diagnose)"""

    # 4. Call GPT-4o
    settings = get_settings()
    token = request.headers.get("X-OpenAI-Token") or settings.openai_api_key
    try:
        client = OpenAI(api_key=token)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw = response.choices[0].message.content
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GPT-4 call failed: {exc}")

    parsed = json.loads(raw)
    reasoning = parsed.get("reasoning")
    suggested_prompt = parsed.get("suggested_prompt")
    if not reasoning or not suggested_prompt:
        raise HTTPException(
            status_code=502,
            detail="GPT-4 returned incomplete JSON: missing 'reasoning' or 'suggested_prompt'",
        )

    # 5. Save PromptSuggestion row
    suggestion = PromptSuggestion(
        mode=body.mode,
        failure_category=body.failure_category,
        prompt_type=body.prompt_type,
        reasoning=reasoning,
        current_prompt=current_prompt,
        suggested_prompt=suggested_prompt,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)

    return {
        "id": str(suggestion.id),
        "mode": suggestion.mode,
        "failure_category": suggestion.failure_category,
        "prompt_type": suggestion.prompt_type,
        "reasoning": suggestion.reasoning,
        "current_prompt": suggestion.current_prompt,
        "suggested_prompt": suggestion.suggested_prompt,
        "applied_at": suggestion.applied_at.isoformat() if suggestion.applied_at else None,
        "dismissed_at": suggestion.dismissed_at.isoformat() if suggestion.dismissed_at else None,
        "created_at": suggestion.created_at.isoformat(),
    }


@router.post("/feedback-suggestions/{id}/apply")
def apply_feedback_suggestion(
    id: uuid.UUID,
    db: Session = Depends(db_session),
):
    """Apply a suggestion to the persona prompt (builtin suggestions return 400)."""
    suggestion = db.get(PromptSuggestion, id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.prompt_type == "builtin":
        raise HTTPException(
            status_code=400,
            detail="Built-in prompts require a code change and cannot be applied via API",
        )

    # Update KBConfig.persona_prompt
    kb_config = db.get(KBConfig, 1)
    if kb_config is None:
        raise HTTPException(status_code=404, detail="KBConfig not found")

    kb_config.persona_prompt = suggestion.suggested_prompt
    suggestion.applied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(suggestion)

    return {
        "id": str(suggestion.id),
        "mode": suggestion.mode,
        "failure_category": suggestion.failure_category,
        "prompt_type": suggestion.prompt_type,
        "reasoning": suggestion.reasoning,
        "current_prompt": suggestion.current_prompt,
        "suggested_prompt": suggestion.suggested_prompt,
        "applied_at": suggestion.applied_at.isoformat() if suggestion.applied_at else None,
        "dismissed_at": suggestion.dismissed_at.isoformat() if suggestion.dismissed_at else None,
        "created_at": suggestion.created_at.isoformat(),
    }


@router.post("/feedback-suggestions/{id}/dismiss")
def dismiss_feedback_suggestion(
    id: uuid.UUID,
    db: Session = Depends(db_session),
):
    """Dismiss a suggestion (resets the threshold counter via created_at anchor)."""
    suggestion = db.get(PromptSuggestion, id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.dismissed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "dismissed", "id": str(suggestion.id)}
