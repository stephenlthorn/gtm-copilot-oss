from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.db.init_db import init_db
from app.middleware.logging import RequestLoggingMiddleware
from app.routers.connectors import router as connectors_router

try:
    from app.routers.refinements import router as refinements_router
except ImportError:
    refinements_router = None  # type: ignore[assignment]

try:
    from app.routers.research import router as research_router
except ImportError:
    research_router = None  # type: ignore[assignment]

setup_logging()

settings = get_settings()
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.include_router(api_router)
app.include_router(connectors_router)
if research_router is not None:
    app.include_router(research_router)
if refinements_router is not None:
    app.include_router(refinements_router)


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_schema:
        init_db()


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "status": "ok"}
