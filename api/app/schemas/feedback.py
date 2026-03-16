from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    mode: str
    query_text: str
    original_response: str
    rating: str  # "positive" or "negative"
    correction: str | None = None


class FeedbackRead(BaseModel):
    id: UUID
    user_email: str
    mode: str
    rating: str
    correction: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
