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
    meeting_summary: str | None = None
    action_items: list[str] = field(default_factory=list)
    subject: str | None = None


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
            # Chorus v3 accepts both ISO date strings and Unix timestamps for filtering
            params["from"] = since.strftime("%Y-%m-%d")

        # Chorus v3 API uses /engagements
        resp = await self._client.get("/engagements", params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Chorus /engagements raw keys: %s | top-level type: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__, type(data).__name__)
        # v3 returns {"engagements": [...]} or {"calls": [...]}
        records = data.get("engagements") or data.get("calls") or []
        if not records and isinstance(data, dict):
            logger.warning("Chorus returned 0 records. Full response (truncated): %s", str(data)[:500])
        elif records:
            logger.info("Chorus first record keys: %s", list(records[0].keys()) if isinstance(records[0], dict) else records[0])
            logger.info("Chorus first record (truncated): %s", str(records[0])[:600])
        return [self._parse_call(r) for r in records]

    async def get_transcript(self, call_id: str) -> str:
        """Try multiple endpoint patterns; return first non-empty transcript found."""
        candidate_paths = [
            f"/engagements/{call_id}/transcript",
            f"/engagements/{call_id}/transcription",
            f"/calls/{call_id}/transcript",
            f"/transcripts/{call_id}",
            f"/transcriptions/{call_id}",
        ]
        for path in candidate_paths:
            try:
                resp = await self._client.get(path)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("transcript")
                    or data.get("transcription")
                    or data.get("text")
                    or data.get("content")
                    or ""
                )
                if text:
                    return str(text)
            except Exception:
                continue
        # Fall back to engagement detail which may carry transcript inline
        try:
            resp = await self._client.get(f"/engagements/{call_id}")
            if resp.status_code != 404:
                resp.raise_for_status()
                return self._parse_call(resp.json()).transcript or ""
        except Exception:
            pass
        return ""

    async def get_call_details(self, call_id: str) -> ChorusCallData:
        resp = await self._client.get(f"/engagements/{call_id}")
        resp.raise_for_status()
        return self._parse_call(resp.json())

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse_call(data: dict) -> ChorusCallData:
        # Chorus v3 uses date_time as Unix seconds float.
        # Fall back to ISO string fields used by older/other API versions.
        raw_date = (
            data.get("date_time") or
            data.get("startTime") or data.get("start_time") or
            data.get("date") or data.get("scheduledStart") or ""
        )
        parsed_date = None
        if raw_date:
            if isinstance(raw_date, (int, float)):
                # Unix seconds (v3) or milliseconds (>1e10)
                ts = float(raw_date)
                if ts > 1e10:
                    ts /= 1000
                try:
                    parsed_date = datetime.utcfromtimestamp(ts)
                except (ValueError, OSError, OverflowError):
                    pass
            if parsed_date is None:
                raw_str = str(raw_date)
                if raw_str.replace(".", "", 1).isdigit():
                    try:
                        ts = float(raw_str)
                        if ts > 1e10:
                            ts /= 1000
                        parsed_date = datetime.utcfromtimestamp(ts)
                    except (ValueError, OSError, OverflowError):
                        pass
            if parsed_date is None:
                try:
                    parsed_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
        if parsed_date is None:
            parsed_date = datetime.utcnow()

        # v3 flat fields: account_name, opportunity_name
        _acct = data.get("account") or {}
        account_name = (
            data.get("account_name") or
            (_acct.get("name") if isinstance(_acct, dict) else str(_acct)) or
            "Unknown"
        )

        _opp = data.get("opportunity") or {}
        opp_name = (
            data.get("opportunity_name") or
            (_opp.get("name") if isinstance(_opp, dict) else str(_opp) if _opp else None)
        ) or None

        rep_email = (
            data.get("user_email") or
            data.get("rep_email") or
            (data.get("owner") or {}).get("email") or
            (data.get("assignee") or {}).get("email")
        )

        meeting_summary = data.get("meeting_summary") or None
        action_items = data.get("action_items") or []
        if not isinstance(action_items, list):
            action_items = []

        # Build a synthesized transcript from available inline content
        inline_transcript = data.get("transcript")
        if not inline_transcript:
            parts = []
            if meeting_summary:
                parts.append(f"Meeting Summary:\n{meeting_summary}")
            if action_items:
                parts.append("Action Items:\n" + "\n".join(f"- {a}" for a in action_items if a))
            inline_transcript = "\n\n".join(parts) if parts else None

        return ChorusCallData(
            call_id=str(
                data.get("engagement_id") or data.get("id") or data.get("chorus_call_id") or ""
            ),
            date=parsed_date,
            account=str(account_name),
            opportunity=str(opp_name) if opp_name else None,
            stage=data.get("stage"),
            rep_email=rep_email,
            se_email=data.get("se_email"),
            participants=data.get("participants", []),
            recording_url=data.get("url") or data.get("recording_url") or data.get("recordingUrl"),
            transcript=inline_transcript,
            meeting_summary=meeting_summary,
            action_items=action_items,
            subject=data.get("subject"),
        )
