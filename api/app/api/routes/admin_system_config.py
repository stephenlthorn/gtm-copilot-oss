from __future__ import annotations

import os
import re

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import db_session

router = APIRouter()

# Keys whose values are secrets (encrypt on write, mask on read).
_SECRET_PATTERNS = [
    re.compile(r"^api_key\."),
    re.compile(r"\.token$"),
]

_MASKED = "***"


def _is_secret_key(config_key: str) -> bool:
    return any(pattern.search(config_key) for pattern in _SECRET_PATTERNS)


def _get_fernet():
    from cryptography.fernet import Fernet
    import base64
    import hashlib

    raw = os.environ.get("ENCRYPTION_KEY", "")
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
            if len(decoded) == 32:
                key = raw.encode("utf-8")
            else:
                key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
        except Exception:
            key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    else:
        # Dev-safe fallback — mirrors the pattern used in auth.py
        seed = "gtm-copilot|dev-only"
        key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(key)


@router.get("/system-config")
def list_system_config(
    request: Request,
    db: Session = Depends(db_session),
) -> list[dict]:
    from app.models.entities import SystemConfig

    org_id = int(request.headers.get("X-Org-Id", "1"))
    rows = db.query(SystemConfig).filter(SystemConfig.org_id == org_id).order_by(SystemConfig.config_key).all()
    result = []
    for row in rows:
        is_secret = _is_secret_key(row.config_key)
        if is_secret:
            value = _MASKED if row.config_value_encrypted else None
        else:
            value = row.config_value_plain
        result.append(
            {
                "config_key": row.config_key,
                "value": value,
                "is_secret": is_secret,
                "updated_at": str(row.updated_at) if row.updated_at else None,
            }
        )
    return result


@router.put("/system-config/{config_key}")
def upsert_system_config(
    config_key: str,
    request: Request,
    body: dict = Body(...),
    db: Session = Depends(db_session),
) -> dict:
    from app.models.entities import SystemConfig

    org_id = int(request.headers.get("X-Org-Id", "1"))
    is_secret = _is_secret_key(config_key)

    plain_value = body.get("value")
    secret_value = body.get("secret")

    if plain_value is None and secret_value is None:
        raise HTTPException(
            status_code=400,
            detail="Body must contain either 'value' (plain) or 'secret' (encrypted).",
        )

    row = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key,
        SystemConfig.org_id == org_id,
    ).first()

    if row is None:
        row = SystemConfig(config_key=config_key, org_id=org_id)
        db.add(row)

    if secret_value is not None:
        fernet = _get_fernet()
        row.config_value_encrypted = fernet.encrypt(str(secret_value).encode("utf-8"))
        row.config_value_plain = None
    else:
        row.config_value_plain = plain_value
        row.config_value_encrypted = None

    db.commit()
    db.refresh(row)

    masked_value = _MASKED if row.config_value_encrypted else row.config_value_plain
    return {
        "config_key": row.config_key,
        "value": masked_value,
        "is_secret": is_secret,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }
