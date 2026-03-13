from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class ChorusCallData:
    call_id: str
    date: datetime
    account: str
    opportunity: str | None = None
    stage: str | None = None
    rep_email: str | None = None
    se_email: str | None = None
    participants: list[dict] = field(default_factory=list)
    recording_url: str | None = None
    transcript: str | None = None


class ChorusConnector:
    """HTTP client for the Chorus (or generic call-recording) API."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=_DEFAULT_TIMEOUT,
        )

    async def list_calls(
        self, since: datetime | None = None
    ) -> list[ChorusCallData]:
        params: dict[str, str] = {}
        if since is not None:
            params["from"] = since.strftime("%Y-%m-%d")

        # Chorus v3 API uses /engagements
        resp = await self._client.get("/engagements", params=params)
        resp.raise_for_status()
        data = resp.json()
        # v3 returns {"engagements": [...]} or {"calls": [...]}
        records = data.get("engagements") or data.get("calls") or []
        return [self._parse_call(r) for r in records]

    async def get_transcript(self, call_id: str) -> str:
        resp = await self._client.get(f"/engagements/{call_id}/transcript")
        resp.raise_for_status()
        data = resp.json()
        return data.get("transcript", "")

    async def get_call_details(self, call_id: str) -> ChorusCallData:
        resp = await self._client.get(f"/engagements/{call_id}")
        resp.raise_for_status()
        return self._parse_call(resp.json())

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse_call(data: dict) -> ChorusCallData:
        # Support both v3 field names and legacy field names
        raw_date = (
            data.get("startTime") or data.get("start_time") or
            data.get("date") or data.get("scheduledStart") or ""
        )
        try:
            parsed_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            parsed_date = datetime.utcnow()

        # v3: account info may be nested
        account_info = data.get("account") or {}
        account_name = (
            account_info.get("name") if isinstance(account_info, dict)
            else str(account_info or "Unknown")
        )

        # v3: opportunity may be nested
        opp_info = data.get("opportunity") or {}
        opp_name = (
            opp_info.get("name") if isinstance(opp_info, dict)
            else str(opp_info) if opp_info else None
        )

        # rep email: may be under owner/assignee
        rep_email = (
            data.get("rep_email") or
            (data.get("owner") or {}).get("email") or
            (data.get("assignee") or {}).get("email")
        )

        return ChorusCallData(
            call_id=str(data.get("id") or data.get("chorus_call_id") or ""),
            date=parsed_date,
            account=account_name or "Unknown",
            opportunity=opp_name,
            stage=data.get("stage") or (opp_info.get("stage") if isinstance(opp_info, dict) else None),
            rep_email=rep_email,
            se_email=data.get("se_email"),
            participants=data.get("participants", []),
            recording_url=data.get("recording_url") or data.get("recordingUrl"),
            transcript=data.get("transcript"),
        )
