from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserPrefUpdate(BaseModel):
    llm_model: str | None = None
    reasoning_effort: str | None = None
    retrieval_top_k: int | None = None
    intel_brief_enabled: bool | None = None
    intel_brief_summarizer_model: str | None = None
    intel_brief_summarizer_effort: str | None = None
    intel_brief_synthesis_model: str | None = None
    intel_brief_synthesis_effort: str | None = None


class UserPrefRead(BaseModel):
    user_email: str
    llm_model: str | None
    reasoning_effort: str | None
    retrieval_top_k: int | None
    intel_brief_enabled: bool | None = None
    intel_brief_summarizer_model: str | None = None
    intel_brief_summarizer_effort: str | None = None
    intel_brief_synthesis_model: str | None = None
    intel_brief_synthesis_effort: str = "medium"
    updated_at: datetime

    model_config = {"from_attributes": True}
