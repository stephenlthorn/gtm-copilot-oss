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

    # Auto-enable Chorus in KBConfig when CHORUS_API_KEY is present in the
    # environment.  This means adding the key to .env is sufficient to activate
    # call transcript retrieval without a separate DB update.
    try:
        _sync_kb_config_from_env()
    except Exception as e:
        logger.warning("_sync_kb_config_from_env failed on startup: %s", e)


def _sync_kb_config_from_env() -> None:
    from app.core.settings import get_settings
    from app.models import KBConfig
    settings = get_settings()
    has_chorus_key = bool(settings.chorus_api_key or settings.call_api_key)
    if not has_chorus_key:
        return
    with SessionLocal() as db:
        config = db.get(KBConfig, 1)
        if config is None:
            config = KBConfig(id=1, chorus_enabled=True)
            db.add(config)
            db.commit()
            logger.info("init_db: created KBConfig(id=1) with chorus_enabled=True")
        elif not config.chorus_enabled:
            config.chorus_enabled = True
            db.commit()
            logger.info("init_db: set chorus_enabled=True on KBConfig(id=1)")
