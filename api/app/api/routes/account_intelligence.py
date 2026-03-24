from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.llm import LLMService
from app.prompts.templates import TIDB_EXPERT_CONTEXT, TIDB_AI_CONTEXT

router = APIRouter()


class AccountIntelRequest(BaseModel):
    user: str
    prompt: str


@router.post("")
def generate_account_profile(req: AccountIntelRequest, request: Request) -> dict:
    openai_token = request.headers.get("X-OpenAI-Token")
    llm = LLMService(api_key=openai_token)

    system = (
        TIDB_EXPERT_CONTEXT
        + "\n\n"
        + TIDB_AI_CONTEXT
        + "\n\nYou are producing a structured account intelligence profile. "
        "Apply your full TiDB technical knowledge — architecture, HTAP, vector/AI capabilities, "
        "competitive positioning, and cloud tiers — to assess this account accurately. "
        "Return ONLY valid JSON with no markdown, code fences, or explanation."
    )

    try:
        answer = llm._responses_text(system, req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {type(exc).__name__}: {exc}")

    if not answer:
        last = getattr(llm, "last_error", None)
        raise HTTPException(
            status_code=503,
            detail=f"LLM returned no response. {last or 'No provider credentials configured.'}",
        )

    return {"answer": answer}
