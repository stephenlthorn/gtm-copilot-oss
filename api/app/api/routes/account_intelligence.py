from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.llm import LLMService

router = APIRouter()


class AccountIntelRequest(BaseModel):
    user: str
    prompt: str


@router.post("")
def generate_account_profile(req: AccountIntelRequest, request: Request) -> dict:
    openai_token = request.headers.get("X-OpenAI-Token")
    llm = LLMService(api_key=openai_token)

    system = (
        "You are a TiDB Cloud sales engineering expert. "
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
