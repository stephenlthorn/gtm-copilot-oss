from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)

    # Seed prompt registry with factory defaults (idempotent)
    from app.db.seed_prompts import seed_prompts  # local import avoids circular dependency at module load
    try:
        with SessionLocal() as db:
            seed_prompts(db)
    except Exception as e:
        logger.warning("seed_prompts failed on startup: %s", e)
