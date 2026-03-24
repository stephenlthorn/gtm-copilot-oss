from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import account_intelligence, accounts, admin, calls, chat, feedback, kb, marketing, messaging, rep, se, slack, user_prefs
from app.api.routes.prompts import router as prompts_router
from app.api.routes.templates import router as templates_router, user_router as user_templates_router

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(account_intelligence.router, prefix="/account-intelligence", tags=["account-intelligence"])
api_router.include_router(kb.router, prefix="/kb", tags=["kb"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(messaging.router, prefix="/messages", tags=["messages"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(rep.router, prefix="/rep", tags=["rep"])
api_router.include_router(se.router, prefix="/se", tags=["se"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
api_router.include_router(slack.router, prefix="/slack", tags=["slack"])
api_router.include_router(user_prefs.router, prefix="/user", tags=["user"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(user_templates_router, prefix="/user/templates", tags=["templates"])
api_router.include_router(prompts_router, prefix="/prompts", tags=["prompts"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
