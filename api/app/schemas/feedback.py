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
    citations: list[str] | None = None   # chunk UUIDs cited in the response
    audit_id: str | None = None          # UUID of the AuditLog row for this query


class FeedbackRead(BaseModel):
    id: UUID
    user_email: str
    mode: str
    rating: str
    correction: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
