from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ingest.chorus_connector import ChorusConnector
from app.models import CallArtifact, ChorusCall, KBDocument, KBChunk, SourceType
from app.services.artifact_generator import ArtifactGenerator
from app.services.embedding import EmbeddingService
from app.utils.chunking import chunk_transcript_turns
from app.utils.hashing import sha256_text

logger = logging.getLogger(__name__)


class TranscriptIngestor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connector = ChorusConnector()
        self.embedder = EmbeddingService()
        self.generator = ArtifactGenerator()

    @staticmethod
    def _normalize(payload: dict) -> dict:
        # Already-normalized test fixtures
        if "metadata" in payload and "turns" in payload:
            return payload

        # Chorus API live format: engagement from /v3/engagements +
        # conversation attributes merged in from /api/v1/conversations/:id
        conv = payload.get("_conversation") or {}

        # Date: date_time is Unix seconds from Chorus v3
        raw_date = (
            payload.get("date_time")
            or conv.get("_created_at")
            or payload.get("date")
            or payload.get("metadata", {}).get("date")
        )
        date_str = _to_date_str(raw_date)

        # Account
        acct = conv.get("account") or {}
        account = (
            payload.get("account_name")
            or (acct.get("name") if isinstance(acct, dict) else None)
            or payload.get("account")
            or "Unknown"
        )

        # Opportunity / stage
        deal = conv.get("deal") or {}
        opportunity = (
            payload.get("opportunity_name")
            or (deal.get("name") if isinstance(deal, dict) else None)
        )
        stage = deal.get("current_stage") if isinstance(deal, dict) else None

        # Rep email
        owner = conv.get("owner") or {}
        rep_email = (
            payload.get("user_email")
            or (owner.get("email") if isinstance(owner, dict) else None)
            or "unknown@example.com"
        )

        # Participants → speaker_map
        participants = conv.get("participants") or payload.get("participants") or []
        speaker_map: dict[str, dict] = {}
        for p in participants:
            name = p.get("name") or p.get("email") or "Unknown"
            ptype = p.get("type") or "other"
            role = "rep" if ptype == "rep" else ("cust" if ptype in ("cust", "customer") else "other")
            speaker_map[name] = {"name": name, "role": role, "email": p.get("email")}

        if not speaker_map:
            speaker_map = {"Speaker": {"name": rep_email, "role": "rep", "email": rep_email}}

        # Turns: parse from "SpeakerName: text\n..." transcript string built by _build_transcript()
        transcript_text = payload.get("transcript") or ""
        turns: list[dict] = []
        for i, line in enumerate(transcript_text.split("\n")):
            line = line.strip()
            if not line or line.startswith("["):
                continue
            if ": " in line:
                speaker_name, text = line.split(": ", 1)
                speaker_id = speaker_name.strip()
            else:
                speaker_id = "Speaker"
                text = line
            if text.strip():
                turns.append({
                    "speaker_id": speaker_id,
                    "start_time_sec": i * 5,
                    "end_time_sec": i * 5 + 5,
                    "text": text.strip(),
                })

        # Fallback: use meeting_summary as a single turn if no utterances
        if not turns:
            summary = payload.get("meeting_summary") or conv.get("summary") or ""
            action_items = payload.get("action_items") or []
            text_parts = []
            if summary:
                text_parts.append(f"Summary: {summary}")
            if action_items:
                text_parts.append("Action items: " + "; ".join(str(a) for a in action_items if a))
            if text_parts:
                turns = [{"speaker_id": "Speaker", "start_time_sec": 0, "end_time_sec": 10,
                          "text": " ".join(text_parts)}]

        call_id = (
            payload.get("chorus_call_id")
            or payload.get("engagement_id")
            or payload.get("id")
        )

        return {
            "chorus_call_id": call_id,
            "metadata": {
                "date": date_str,
                "account": account,
                "opportunity": opportunity,
                "stage": stage,
                "rep_email": rep_email,
                "se_email": None,
                "subject": payload.get("subject"),
            },
            "speaker_map": speaker_map,
            "turns": turns,
            "recording_url": payload.get("url") or f"https://chorus.ai/meeting/{call_id}",
        }

    def _upsert_call(self, normalized: dict) -> ChorusCall:
        md = normalized.get("metadata", {})
        call_id = normalized["chorus_call_id"]
        existing = self.db.execute(select(ChorusCall).where(ChorusCall.chorus_call_id == call_id)).scalar_one_or_none()
        participants = list((normalized.get("speaker_map") or {}).values())

        if existing:
            row = existing
        else:
            row = ChorusCall(chorus_call_id=call_id)
            self.db.add(row)

        row.date = date.fromisoformat(md.get("date"))
        row.account = md.get("account", "Unknown")
        row.opportunity = md.get("opportunity")
        row.stage = md.get("stage")
        row.rep_email = md.get("rep_email", "unknown@example.com")
        row.se_email = md.get("se_email")
        row.participants = participants
        row.recording_url = normalized.get("recording_url")
        row.transcript_url = normalized.get("transcript_url")

        self.db.flush()
        return row

    def _upsert_document(self, normalized: dict, call: ChorusCall) -> KBDocument:
        call_id = normalized["chorus_call_id"]
        doc = self.db.execute(
            select(KBDocument).where(KBDocument.source_type == SourceType.CHORUS, KBDocument.source_id == call_id)
        ).scalar_one_or_none()

        if not doc:
            doc = KBDocument(
                source_type=SourceType.CHORUS,
                source_id=call_id,
                title=f"Call Transcript: {call.account} {call.date.isoformat()}",
                url=call.transcript_url,
                mime_type="application/json",
                modified_time=None,
                owner=call.rep_email,
                path=None,
                permissions_hash=sha256_text(f"{call.rep_email}:{call.se_email or ''}"),
                tags={"account": call.account, "date": call.date.isoformat(), "source_type": "call_transcript"},
            )
            self.db.add(doc)
        else:
            doc.title = f"Call Transcript: {call.account} {call.date.isoformat()}"
            doc.url = call.transcript_url
            doc.owner = call.rep_email
            doc.tags = {"account": call.account, "date": call.date.isoformat(), "source_type": "call_transcript"}

        self.db.flush()
        return doc

    def _replace_chunks(self, doc: KBDocument, normalized: dict) -> list[str]:
        self.db.execute(delete(KBChunk).where(KBChunk.document_id == doc.id))
        chunks = chunk_transcript_turns(normalized.get("turns", []), normalized.get("speaker_map", {}))
        embeddings = self.embedder.batch_embed([c.text for c in chunks]) if chunks else []

        snippets: list[str] = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.db.add(
                KBChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=emb,
                    metadata_json=chunk.metadata,
                    content_hash=sha256_text(chunk.text),
                )
            )
            snippets.append(chunk.text[:250])
        return snippets

    def _replace_artifact(self, call_id: str, normalized: dict, snippets: list[str]) -> None:
        self.db.execute(delete(CallArtifact).where(CallArtifact.chorus_call_id == call_id))
        artifact = self.generator.generate(normalized, snippets)
        self.db.add(
            CallArtifact(
                chorus_call_id=call_id,
                summary=artifact["summary"],
                objections=artifact["objections"],
                competitors_mentioned=artifact["competitors_mentioned"],
                risks=artifact["risks"],
                next_steps=artifact["next_steps"],
                recommended_collateral=artifact["recommended_collateral"],
                follow_up_questions=artifact["follow_up_questions"],
                model_info=artifact["model_info"],
            )
        )

    def _ingest_one(self, normalized: dict) -> None:
        """Ingest a single normalized call into TiDB with rollback on failure."""
        call = self._upsert_call(normalized)
        doc = self._upsert_document(normalized, call)
        snippets = self._replace_chunks(doc, normalized)
        self._replace_artifact(normalized["chorus_call_id"], normalized, snippets)

    def sync(self, since: date | None = None) -> dict:
        raw_calls = self.connector.fetch_calls(since=since)
        processed = 0
        skipped = 0
        failed = 0
        summary_fallbacks = 0

        for raw in raw_calls:
            # Skip non-meeting engagements (emails, content_viewed, etc.)
            eng_type = raw.payload.get("engagement_type") or ""
            if eng_type and eng_type not in ("meeting", ""):
                skipped += 1
                continue

            normalized = self._normalize(raw.payload)

            # Skip if no turns — nothing to index
            if not normalized.get("turns"):
                skipped += 1
                continue

            # Track if this call is using summary fallback instead of full transcript
            transcript = raw.payload.get("transcript") or ""
            if not transcript:
                summary_fallbacks += 1
                logger.warning(
                    "Call %s (%s): no utterance transcript — using summary fallback",
                    raw.chorus_call_id,
                    raw.payload.get("account_name", "unknown"),
                )

            # Retry up to 3 times on TiDB transient errors
            for attempt in range(3):
                try:
                    self._ingest_one(normalized)
                    processed += 1
                    break
                except SQLAlchemyError as exc:
                    self.db.rollback()
                    if attempt == 2:
                        logger.error("Failed to ingest call %s after 3 attempts: %s", raw.chorus_call_id, exc)
                        failed += 1
                    else:
                        wait = 2 ** attempt
                        logger.warning("TiDB error for call %s (attempt %d), retrying in %ds: %s", raw.chorus_call_id, attempt + 1, wait, exc)
                        time.sleep(wait)

        self.db.commit()
        result = {"calls_seen": len(raw_calls), "processed": processed, "skipped": skipped}
        if failed:
            result["failed"] = failed
        if summary_fallbacks:
            result["summary_fallbacks"] = summary_fallbacks
        return result


def _to_date_str(raw: object) -> str:
    """Convert various date formats (Unix seconds, ISO string) to YYYY-MM-DD."""
    from datetime import datetime, timezone
    if not raw:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e10:
            ts /= 1000
        try:
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            pass
    raw_str = str(raw).strip()
    if raw_str.replace(".", "", 1).isdigit():
        try:
            ts = float(raw_str)
            if ts > 1e10:
                ts /= 1000
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            pass
    return raw_str[:10]  # Take YYYY-MM-DD from ISO string
