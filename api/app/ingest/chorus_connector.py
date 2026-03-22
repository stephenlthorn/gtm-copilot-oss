from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_CHORUS_BASE = "https://chorus.ai"
_MAX_PAGES = 100  # safety cap


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
        # Default to chorus.ai when only the key is set (CALL_BASE_URL not required)
        self.base_url = (self.settings.call_base_url or self.settings.chorus_base_url or _CHORUS_BASE).rstrip("/")

    def fetch_calls(self, since: date | None = None) -> list[ChorusCallRaw]:
        if self.api_key:
            return self._fetch_calls_api(since)
        return self._fetch_calls_fake(since)

    def fetch_calls_pages(self, since: date | None = None):
        """Yield one page of ChorusCallRaw at a time — keeps DB connections alive during fetch."""
        if not self.api_key:
            yield self._fetch_calls_fake(since)
            return
        yield from self._fetch_calls_api_pages(since)

    def _fetch_calls_fake(self, since: date | None = None) -> list[ChorusCallRaw]:
        out: list[ChorusCallRaw] = []
        directory = self.fake_dir if self.fake_dir.exists() else self.legacy_fake_dir
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            call_date = date.fromisoformat(payload.get("metadata", {}).get("date"))
            if since and call_date <= since:
                continue
            out.append(ChorusCallRaw(chorus_call_id=payload["chorus_call_id"], payload=payload))
        return out

    def _fetch_calls_api(self, since: date | None = None) -> list[ChorusCallRaw]:
        """Fetch all calls from Chorus v3/engagements API with continuation_key pagination."""
        out: list[ChorusCallRaw] = []
        for page in self._fetch_calls_api_pages(since):
            out.extend(page)
        return out

    def _fetch_calls_api_pages(self, since: date | None = None):
        """Yield one page (list[ChorusCallRaw]) at a time."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params: dict = {}
        if since:
            params["min_date"] = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        pages = 0
        with httpx.Client(timeout=30.0) as client:
            while pages < _MAX_PAGES:
                resp = client.get(f"{self.base_url}/v3/engagements", headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

                records = data.get("engagements") or []
                if not records:
                    break

                logger.info("Chorus page %d: %d engagements", pages, len(records))
                page_out = []
                for record in records:
                    call_id = str(record.get("engagement_id") or record.get("id") or "")
                    if not call_id:
                        continue
                    page_out.append(ChorusCallRaw(chorus_call_id=call_id, payload=self._to_ingestor_payload(call_id, record)))

                if page_out:
                    yield page_out

                continuation_key = data.get("continuation_key")
                if not continuation_key:
                    break

                params = {"continuation_key": continuation_key}
                pages += 1

        logger.info("Chorus fetch complete: %d pages", pages + 1)

    @staticmethod
    def _to_ingestor_payload(call_id: str, record: dict) -> dict:
        """Convert a /v3/engagements record to the shape TranscriptIngestor._normalize expects."""
        raw_date = record.get("date_time") or record.get("start_time") or record.get("date")
        date_str = date.today().isoformat()
        if raw_date is not None:
            try:
                from datetime import datetime as _dt
                if isinstance(raw_date, (int, float)):
                    date_str = _dt.utcfromtimestamp(raw_date / 1000 if raw_date > 1e10 else raw_date).strftime("%Y-%m-%d")
                else:
                    date_str = _dt.fromisoformat(str(raw_date).replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                pass

        participants = record.get("participants") or []
        speaker_map = {}
        for idx, p in enumerate(participants, start=1):
            name = p.get("name") or p.get("email") or f"Speaker {idx}"
            speaker_map[f"S{idx}"] = {
                "name": name,
                "role": p.get("role") or "other",
                "email": p.get("email"),
            }

        return {
            "chorus_call_id": call_id,
            "metadata": {
                "date": date_str,
                "account": record.get("account_name") or "Unknown",
                "opportunity": record.get("opportunity_name"),
                "stage": None,
                "rep_email": record.get("user_email") or "unknown@example.com",
                "se_email": None,
            },
            "speaker_map": speaker_map,
            "turns": [],  # engagement list has no transcript; full transcript fetched separately if needed
            "recording_url": record.get("url"),
            "transcript_url": record.get("url"),
        }
