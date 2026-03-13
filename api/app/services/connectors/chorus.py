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
            params["since"] = since.isoformat()

        resp = await self._client.get("/calls", params=params)
        resp.raise_for_status()
        records = resp.json().get("calls", [])
        return [self._parse_call(r) for r in records]

    async def get_transcript(self, call_id: str) -> str:
        resp = await self._client.get(f"/calls/{call_id}/transcript")
        resp.raise_for_status()
        data = resp.json()
        return data.get("transcript", "")

    async def get_call_details(self, call_id: str) -> ChorusCallData:
        resp = await self._client.get(f"/calls/{call_id}")
        resp.raise_for_status()
        return self._parse_call(resp.json())

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse_call(data: dict) -> ChorusCallData:
        raw_date = data.get("date") or data.get("start_time", "")
        try:
            parsed_date = datetime.fromisoformat(raw_date)
        except (ValueError, TypeError):
            parsed_date = datetime.utcnow()

        return ChorusCallData(
            call_id=data.get("id") or data.get("chorus_call_id", ""),
            date=parsed_date,
            account=data.get("account", "Unknown"),
            opportunity=data.get("opportunity"),
            stage=data.get("stage"),
            rep_email=data.get("rep_email"),
            se_email=data.get("se_email"),
            participants=data.get("participants", []),
            recording_url=data.get("recording_url"),
            transcript=data.get("transcript"),
        )
