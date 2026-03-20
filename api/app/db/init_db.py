from __future__ import annotations

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
