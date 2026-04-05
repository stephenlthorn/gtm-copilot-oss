from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db


# FastAPI dependency wrapper

def db_session() -> Generator[Session, None, None]:
    yield from get_db()


def require_auth(request: Request) -> str:
    """Extract and validate the X-User-Email header.

    Returns the lowercase email. Raises 401 if missing.
    """
    email = (request.headers.get("X-User-Email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Authentication required: X-User-Email header missing")
    return email
