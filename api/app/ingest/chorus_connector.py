from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_CHORUS_BASE = "https://chorus.ai"
# No fields param — default response includes all fields including recording.utterances


def _project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[3], here.parents[2], Path.cwd()]
    for base in candidates:
        if (base / "data").exists():
            return base
    return here.parents[3]


@dataclass
class ChorusCallRaw:
    chorus_call_id: str
    payload: dict


class ChorusConnector:
    def __init__(self) -> None:
        self.settings = get_settings()
        base = _project_root() / "data"
        self.fake_dir = base / "fake_calls"
        self.legacy_fake_dir = base / "fake_chorus"
        self.api_key = self.settings.call_api_key or self.settings.chorus_api_key
        # Base URL is always chorus.ai; chorus_base_url only used for testing overrides
        self.base_url = (
            self.settings.call_base_url
            or self.settings.chorus_base_url
            or _CHORUS_BASE
        ).rstrip("/")

    def fetch_calls(self, since: date | None = None) -> list[ChorusCallRaw]:
        if self.api_key:
            return self._fetch_calls_api(since)
        return self._fetch_calls_fake(since)

    def _fetch_calls_fake(self, since: date | None = None) -> list[ChorusCallRaw]:
        out: list[ChorusCallRaw] = []
        directory = self.fake_dir if self.fake_dir.exists() else self.legacy_fake_dir
        if not directory.exists():
            return out
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                raw_date = payload.get("metadata", {}).get("date")
                if raw_date and since:
                    call_date = date.fromisoformat(raw_date)
                    if call_date <= since:
                        continue
                out.append(ChorusCallRaw(
                    chorus_call_id=payload["chorus_call_id"],
                    payload=payload,
                ))
            except Exception as exc:
                logger.warning("Skipping fake call file %s: %s", path, exc)
        return out

    def _fetch_calls_api(self, since: date | None = None) -> list[ChorusCallRaw]:
        """Fetch engagements from Chorus v3 API with pagination.

        Defaults to last 90 days to avoid a full history crawl on initial sync.
        Pass `since` explicitly to override.
        """
        from datetime import timedelta

        # Default to last 90 days so the initial sync doesn't pull all history
        if since is None:
            since = (datetime.utcnow() - timedelta(days=90)).date()

        # Chorus uses the plain token — NOT "Bearer <token>"
        headers = {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }

        params: dict[str, str] = {}
        if since:
            params["min_date"] = datetime.combine(since, datetime.min.time()).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )

        out: list[ChorusCallRaw] = []
        max_pages = 5  # 5 pages × 100 calls = 500 calls per sync run

        with httpx.Client(timeout=30.0) as client:
            for page in range(max_pages):
                url = f"{self.base_url}/v3/engagements"
                logger.info("Fetching Chorus engagements page %d", page)
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

                records = data.get("engagements") or []
                if not records:
                    break

                for eng in records:
                    call_id = str(eng.get("engagement_id") or eng.get("id") or "")
                    if not call_id:
                        continue
                    # Only fetch full transcripts for recorded meetings — skip emails/content_viewed
                    eng_type = eng.get("engagement_type") or ""
                    if eng_type in ("meeting",):
                        full_payload = self._fetch_conversation(client, headers, call_id, eng)
                    else:
                        full_payload = eng
                    out.append(ChorusCallRaw(chorus_call_id=call_id, payload=full_payload))

                continuation_key = data.get("continuation_key")
                if not continuation_key:
                    break
                params = {"continuation_key": continuation_key}

        logger.info("Fetched %d calls from Chorus", len(out))
        return out

    def _fetch_conversation(
        self,
        client: httpx.Client,
        headers: dict,
        call_id: str,
        engagement: dict,
    ) -> dict:
        """Fetch full conversation (with utterance transcript) from /api/v1/conversations/:id."""
        try:
            url = f"{self.base_url}/api/v1/conversations/{call_id}"
            resp = client.get(
                url,
                headers={**headers, "Accept": "application/vnd.api+json"},
                timeout=30.0,
            )
            if resp.status_code == 404:
                logger.debug("Conversation %s not found, using engagement data only", call_id)
                return engagement

            resp.raise_for_status()
            conv_data = resp.json()

            # Merge engagement metadata into conversation payload
            attrs = (conv_data.get("data") or {}).get("attributes") or {}
            result = dict(engagement)
            result["_conversation"] = attrs

            # Build utterance transcript
            utterances = (attrs.get("recording") or {}).get("utterances") or []
            if utterances:
                result["transcript"] = _build_transcript(utterances)

            result["meeting_summary"] = attrs.get("summary") or engagement.get("meeting_summary")
            result["action_items"] = attrs.get("action_items") or []

            return result

        except Exception as exc:
            logger.warning("Could not fetch conversation %s: %s", call_id, exc)
            return engagement


def _build_transcript(utterances: list[dict]) -> str:
    """Convert utterances to speaker-attributed transcript text."""
    lines: list[str] = []
    for utt in utterances:
        speaker = utt.get("speaker_name") or utt.get("speaker_type") or "Unknown"
        text = utt.get("snippet") or ""
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)
