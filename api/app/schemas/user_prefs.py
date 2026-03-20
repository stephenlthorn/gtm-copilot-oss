from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserPrefUpdate(BaseModel):
    llm_model: str | None = None
    reasoning_effort: str | None = None


class UserPrefRead(BaseModel):
    user_email: str
    llm_model: str | None
    reasoning_effort: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}
