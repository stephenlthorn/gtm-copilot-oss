from __future__ import annotations

from sqlalchemy import text

from app.db.base import Base
from app.db.session import SessionLocal, engine


def init_db() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)

    # Seed prompt registry with factory defaults (idempotent)
    from app.db.seed_prompts import seed_prompts  # local import avoids circular dependency at module load
    with SessionLocal() as db:
        seed_prompts(db)
