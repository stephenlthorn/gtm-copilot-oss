from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

settings = get_settings()


def _normalize_database_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("mysql://"):
        return "mysql+pymysql://" + value[len("mysql://") :]
    return value


def _build_connect_args(url: str) -> dict:
    """Build SSL and connection args for TiDB Cloud Serverless."""
    args: dict = {}
    if "tidbcloud.com" in url or "tidbserverless" in url:
        ssl_ca = os.environ.get("TIDB_SSL_CA")
        if ssl_ca:
            import ssl as _ssl

            ssl_ctx = _ssl.create_default_context(cafile=ssl_ca)
            ssl_ctx.check_hostname = True
            ssl_ctx.verify_mode = _ssl.CERT_REQUIRED
            args["ssl"] = ssl_ctx
    return args


_db_url = settings.database_url or ""
connect_args = _build_connect_args(_db_url)
pool_kwargs: dict = {}
if "tidbcloud.com" in _db_url:
    pool_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 300,
    }

engine = create_engine(
    _normalize_database_url(_db_url),
    pool_pre_ping=True,
    connect_args=connect_args,
    **pool_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
