from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.settings import get_settings

router = APIRouter()
settings = get_settings()


def _get_or_create_user(db: Session, email: str):
    from app.models.entities import User, UserRole

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            google_id=email,
            email=email,
            name=email.split("@")[0],
            role=UserRole.sales_rep,
            org_id=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class OpenAIKeyRequest(BaseModel):
    api_key: str


class PreferencesUpdate(BaseModel):
    calendar_scan_frequency: str | None = None
    prep_lookahead_days: int | None = None
    slack_notifications: dict | None = None
    default_sources: list[int] | None = None


class ConnectProviderRequest(BaseModel):
    access_token: str
    instance_url: str | None = None
    base_url: str | None = None


@router.get("/google")
def google_auth_redirect() -> dict:
    from app.services.auth.google_oauth import GoogleOAuthService

    svc = GoogleOAuthService(
        client_id=settings.google_oauth_client_id or settings.google_drive_client_id or "",
        client_secret=settings.google_oauth_client_secret or settings.google_drive_client_secret or "",
        redirect_uri=getattr(settings, "google_oauth_redirect_uri", "http://localhost:3000/auth/callback"),
    )
    url = svc.get_auth_url()
    return {"auth_url": url}


@router.get("/google/callback")
def google_auth_callback(
    code: str,
    db: Session = Depends(db_session),
) -> dict:
    from app.services.auth.google_oauth import GoogleOAuthService

    svc = GoogleOAuthService(
        client_id=settings.google_oauth_client_id or settings.google_drive_client_id or "",
        client_secret=settings.google_oauth_client_secret or settings.google_drive_client_secret or "",
        redirect_uri=getattr(settings, "google_oauth_redirect_uri", "http://localhost:3000/auth/callback"),
    )
    try:
        result = svc.handle_callback(code=code, db=db, org_id=1)
        return {
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "user": {
                "id": result.user.id if hasattr(result, "user") else None,
                "email": result.user.email if hasattr(result, "user") else None,
                "name": result.user.name if hasattr(result, "user") else None,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/openai-key")
def save_openai_key(
    req: OpenAIKeyRequest,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        from cryptography.fernet import Fernet
        import os

        key = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        user.openai_api_key_encrypted = fernet.encrypt(req.api_key.encode())
        db.commit()
        return {"status": "saved"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/me")
def get_current_user(
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = _get_or_create_user(db, user_email)

    accounts = user.connected_accounts or {}
    connected_providers = {k: bool(v.get("access_token")) for k, v in accounts.items() if isinstance(v, dict)}

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value if user.role else "sales_rep",
        "org_id": user.org_id,
        "preferences": user.preferences or {},
        "connected_providers": connected_providers,
    }


@router.put("/me/preferences")
def update_preferences(
    req: PreferencesUpdate,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = _get_or_create_user(db, user_email)

    prefs = dict(user.preferences or {})
    updates = req.model_dump(exclude_none=True)
    prefs.update(updates)
    user.preferences = prefs
    db.commit()
    return {"preferences": user.preferences}


@router.post("/connect/{provider}")
def connect_provider(
    provider: str,
    req: ConnectProviderRequest,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = _get_or_create_user(db, user_email)

    valid_providers = {"salesforce", "zoominfo", "linkedin", "chorus"}
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Must be one of: {valid_providers}")

    accounts = dict(user.connected_accounts or {})
    accounts[provider] = {
        "access_token": req.access_token,
        "instance_url": req.instance_url,
        "base_url": req.base_url,
        "connected": True,
    }
    user.connected_accounts = accounts
    db.commit()
    return {"status": "connected", "provider": provider}


@router.delete("/connect/{provider}")
def disconnect_provider(
    provider: str,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import User

    user_email = request.headers.get("X-User-Email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = _get_or_create_user(db, user_email)

    accounts = dict(user.connected_accounts or {})
    accounts.pop(provider, None)
    user.connected_accounts = accounts
    db.commit()
    return {"status": "disconnected", "provider": provider}
