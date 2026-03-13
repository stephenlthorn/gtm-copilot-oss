from __future__ import annotations

from sqlalchemy import text

from app.core.settings import get_settings
from app.db.base import Base
from app.db.session import engine

# Import all model modules so SQLAlchemy registers every table with Base.metadata.
import app.models.entities  # noqa: F401


def init_db(create_extension: bool = True) -> None:
    settings = get_settings()
    with engine.begin() as conn:
        if create_extension and not settings.is_tidb:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                # Non-Postgres backends (e.g., sqlite tests) do not support extensions.
                pass
        Base.metadata.create_all(bind=conn)
