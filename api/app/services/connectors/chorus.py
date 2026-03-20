from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_CHORUS_BASE = "https://chorus.ai"

# Fields to request from the conversations API for full transcript + metadata
_CONVERSATION_FIELDS = (
    "recording.utterances,recording.trackers,recording.duration,"
    "recording.start_time,recording.clusters,"
    "participants,name,owner,owner.email,account,deal,status,"
    "action_items,summary,language,_created_at"
)


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
    duration_seconds: float | None = None
    language: str | None = None


class ChorusConnector:
    """HTTP client for the Chorus.ai REST API.

    Authentication uses a plain API token in the Authorization header
    (not Bearer — Chorus uses Basic Auth or raw token).

    Endpoints used:
      List calls:      GET https://chorus.ai/v3/engagements
      Full transcript: GET https://chorus.ai/api/v1/conversations/:id
                           ?fields=recording.utterances,...
    """

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        # Chorus always lives at chorus.ai; base_url override for testing only
        self.base_url = (base_url or _CHORUS_BASE).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                # Chorus uses the plain token — NOT "Bearer <token>"
                "Authorization": api_key,
                "Accept": "application/json",
            },
            timeout=_DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def list_calls(
        self, since: datetime | None = None, max_pages: int = 50
    ) -> list[ChorusCallData]:
        """List all engagements, paginating via continuation_key."""
        params: dict[str, str] = {}
        if since is not None:
            # Chorus v3 accepts ISO date string for min_date
            params["min_date"] = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        calls: list[ChorusCallData] = []
        pages = 0

        while pages < max_pages:
            resp = await self._client.get("/v3/engagements", params=params)
            resp.raise_for_status()
            data = resp.json()

            records = data.get("engagements") or []
            if not records:
                logger.info("Chorus /v3/engagements returned 0 records (page %d)", pages)
                break

            logger.info("Chorus page %d: %d engagements", pages, len(records))
            calls.extend(self._parse_engagement(r) for r in records)

            continuation_key = data.get("continuation_key")
            if not continuation_key:
                break

            params = {"continuation_key": continuation_key}
            pages += 1

        return calls

    async def get_full_call(self, call_id: str) -> ChorusCallData:
        """Fetch the full conversation including utterance-level transcript."""
        resp = await self._client.get(
            f"/api/v1/conversations/{call_id}",
            params={"fields": _CONVERSATION_FIELDS},
            headers={"Accept": "application/vnd.api+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse_conversation(call_id, data)

    async def get_transcript(self, call_id: str) -> str:
        """Return full utterance-level transcript text for a call."""
        try:
            call_data = await self.get_full_call(call_id)
            return call_data.transcript or ""
        except Exception as exc:
            logger.warning("Could not fetch full transcript for call %s: %s", call_id, exc)
            return ""

    async def get_call_details(self, call_id: str) -> ChorusCallData:
        return await self.get_full_call(call_id)

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Parsing helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_engagement(data: dict) -> ChorusCallData:
        """Parse a flat /v3/engagements record (no transcript)."""
        raw_date = data.get("date_time") or data.get("start_time") or data.get("date") or ""
        parsed_date = _parse_date(raw_date) or datetime.utcnow()

        account_name = data.get("account_name") or "Unknown"
        opp_name = data.get("opportunity_name") or None
        rep_email = data.get("user_email") or None

        return ChorusCallData(
            call_id=str(data.get("engagement_id") or data.get("id") or ""),
            date=parsed_date,
            account=str(account_name),
            opportunity=str(opp_name) if opp_name else None,
            stage=None,
            rep_email=rep_email,
            se_email=None,
            participants=data.get("participants") or [],
            recording_url=data.get("url") or None,
            transcript=None,
            meeting_summary=None,
            action_items=[],
            subject=data.get("subject"),
            duration_seconds=data.get("duration"),
            language=data.get("language"),
        )

    @staticmethod
    def _parse_conversation(call_id: str, raw: dict) -> ChorusCallData:
        """Parse a full /api/v1/conversations/:id response with utterances."""
        attrs = (raw.get("data") or {}).get("attributes") or raw.get("attributes") or raw

        # Date from recording start_time or _created_at
        recording = attrs.get("recording") or {}
        raw_date = recording.get("start_time") or attrs.get("_created_at") or ""
        parsed_date = _parse_date(raw_date) or datetime.utcnow()

        # Account
        acct = attrs.get("account") or {}
        account_name = (acct.get("name") if isinstance(acct, dict) else str(acct)) or "Unknown"

        # Opportunity/deal
        deal = attrs.get("deal") or {}
        opp_name = (deal.get("name") if isinstance(deal, dict) else None) or None
        stage = (deal.get("current_stage") if isinstance(deal, dict) else None) or None

        # Owner / rep
        owner = attrs.get("owner") or {}
        rep_email = (owner.get("email") if isinstance(owner, dict) else None) or None

        # Participants
        participants = attrs.get("participants") or []

        # Subject / name
        subject = attrs.get("name") or None

        # Duration
        duration_seconds = recording.get("duration")

        # Language
        language = attrs.get("language") or None

        # Summary & action items
        meeting_summary = attrs.get("summary") or None
        action_items = attrs.get("action_items") or []
        if not isinstance(action_items, list):
            action_items = []

        # Utterance-level transcript
        utterances = recording.get("utterances") or []
        transcript = _build_transcript(utterances, meeting_summary, action_items)

        # Recording URL (no direct URL in conversation response; build from call_id)
        recording_url = f"https://chorus.ai/meeting/{call_id}"

        return ChorusCallData(
            call_id=call_id,
            date=parsed_date,
            account=str(account_name),
            opportunity=str(opp_name) if opp_name else None,
            stage=stage,
            rep_email=rep_email,
            se_email=None,
            participants=participants,
            recording_url=recording_url,
            transcript=transcript,
            meeting_summary=meeting_summary,
            action_items=action_items,
            subject=subject,
            duration_seconds=float(duration_seconds) if duration_seconds else None,
            language=language,
        )


# ------------------------------------------------------------------ #
# Module-level helpers                                               #
# ------------------------------------------------------------------ #

def _parse_date(raw: object) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e10:
            ts /= 1000
        try:
            return datetime.utcfromtimestamp(ts)
        except (ValueError, OSError, OverflowError):
            return None
    raw_str = str(raw).strip()
    if raw_str.replace(".", "", 1).isdigit():
        try:
            ts = float(raw_str)
            if ts > 1e10:
                ts /= 1000
            return datetime.utcfromtimestamp(ts)
        except (ValueError, OSError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _build_transcript(
    utterances: list[dict],
    meeting_summary: str | None,
    action_items: list[str],
) -> str | None:
    """Convert utterances array into a readable transcript string.

    Each utterance has: snippet (text), speaker_name, speaker_type, snippet_time.
    """
    parts: list[str] = []

    if utterances:
        for utt in utterances:
            speaker = utt.get("speaker_name") or utt.get("speaker_type") or "Unknown"
            text = utt.get("snippet") or ""
            if text:
                parts.append(f"{speaker}: {text}")

    if meeting_summary:
        parts.append(f"\n[Meeting Summary]\n{meeting_summary}")

    if action_items:
        items_text = "\n".join(f"- {a}" for a in action_items if a)
        parts.append(f"\n[Action Items]\n{items_text}")

    return "\n".join(parts) if parts else None
