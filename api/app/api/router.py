from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, calls, chat, kb, marketing, messaging, notifications, rep, se, slack
from app.api.routes import accounts, auth, conversations, dashboard, mcp, sources
from app.routers import knowledge

api_router = APIRouter()

# Existing v1 routes
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(kb.router, prefix="/kb", tags=["kb"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(messaging.router, prefix="/messages", tags=["messages"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(rep.router, prefix="/rep", tags=["rep"])
api_router.include_router(se.router, prefix="/se", tags=["se"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
api_router.include_router(slack.router, prefix="/slack", tags=["slack"])

# v2 routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(mcp.router, prefix="/admin", tags=["mcp-admin"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
