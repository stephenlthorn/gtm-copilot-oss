from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

router = APIRouter()


@router.post("/chorus")
def chorus_webhook(body: dict = Body(...)) -> dict:
    event = body.get("event", "")
    if event != "recording.completed":
        return {"status": "ignored", "event": event}

    call_id = body.get("call_id")
    if not call_id:
        raise HTTPException(status_code=400, detail="Missing call_id in webhook payload")

    account_name = body.get("account_name", "")
    duration_seconds = body.get("duration_seconds")

    from app.tasks.research_tasks import run_postcall_research

    # org_id defaults to 1; a future version may derive it from a webhook secret
    # or a lookup on call_id / account_name.
    run_postcall_research.delay(
        chorus_call_id=str(call_id),
        org_id=1,
    )

    return {"status": "queued", "call_id": call_id}
