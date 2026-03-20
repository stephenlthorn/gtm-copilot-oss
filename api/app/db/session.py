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
        value = "mysql+pymysql://" + value[len("mysql://"):]
    # Strip ssl_verify_* params — we handle SSL via connect_args to avoid pymysql hang
    if "tidbcloud.com" in value:
        import re as _re
        value = _re.sub(r"[&?]ssl_verify_\w+=\w+", "", value)
        value = _re.sub(r"\?&", "?", value).rstrip("?")
    return value


def _build_connect_args(url: str) -> dict:
    """Build SSL and connection args for TiDB Cloud Serverless."""
    args: dict = {}
    if "tidbcloud.com" in url or "tidbserverless" in url:
        # Prevent pymysql from hanging indefinitely if TiDB drops the TCP connection.
        args["read_timeout"] = 30
        args["write_timeout"] = 30
        args["connect_timeout"] = 10
        import ssl as _ssl

        ssl_ca = os.environ.get("TIDB_SSL_CA")
        if ssl_ca:
            ssl_ctx = _ssl.create_default_context(cafile=ssl_ca)
        else:
            # Use system CA bundle — TiDB Cloud uses a publicly trusted cert
            ssl_ctx = _ssl.create_default_context()
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
