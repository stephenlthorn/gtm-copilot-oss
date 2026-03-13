from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

settings = get_settings()


def _normalize_database_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("mysql://"):
        return "mysql+pymysql://" + value[len("mysql://"):]
    return value


def _build_engine_kwargs(url: str) -> dict:
    """Build engine keyword arguments appropriate for the database backend."""
    import os

    kwargs: dict = {"pool_pre_ping": True}
    # Only enable SSL when a CA cert path is set AND the file exists on disk.
    # Skipped for local TiDB (no SSL) or when the cert hasn't been mounted yet.
    if "pymysql" in url and settings.tidb_ssl_ca and os.path.isfile(settings.tidb_ssl_ca):
        import ssl as _ssl

        ssl_ctx = _ssl.create_default_context(cafile=settings.tidb_ssl_ca)
        kwargs["connect_args"] = {"ssl": ssl_ctx}
    return kwargs


_url = _normalize_database_url(settings.effective_database_url)
engine = create_engine(_url, **_build_engine_kwargs(_url))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
