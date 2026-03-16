from __future__ import annotations

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine


def init_db(create_extension: bool = True) -> None:
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if create_extension and dialect == "postgresql":
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass
        Base.metadata.create_all(bind=conn)
