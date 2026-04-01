from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ingest.chorus_connector import ChorusConnector
from app.models import CallArtifact, ChorusCall, KBDocument, KBChunk, SourceType
from app.services.artifact_generator import ArtifactGenerator
from app.services.embedding import EmbeddingService
from app.utils.chunking import TextChunk, chunk_transcript_turns
from app.utils.hashing import sha256_text

logger = logging.getLogger(__name__)


_OUTCOME_MAP: dict[str, str] = {
    "won": "won",
    "closed won": "won",
    "loss": "lost",
    "lost": "lost",
    "closed lost": "lost",
    "no decision": "no_decision",
    "no_decision": "no_decision",
    "active": "active",
    "open": "active",
    "in progress": "active",
}


def _coerce_outcome(raw: str | None) -> str | None:
    return _OUTCOME_MAP.get((raw or "").strip().lower())


def _build_embed_text(chunk_text: str, call_metadata: dict) -> str:
    parts = [call_metadata["account"]]
    stage = call_metadata.get("stage")
    if stage:
        parts.append(stage)
    parts.append(call_metadata["date"])
    parts.append(f"rep:{call_metadata['rep_email']}")
    prefix = " | ".join(parts)
    return f"{prefix}\n\n{chunk_text}"


def _to_date_str(raw_date: object) -> str:
    if raw_date is None:
        return date.today().isoformat()
    try:
        from datetime import datetime, timezone

        if isinstance(raw_date, (int, float)):
            timestamp = raw_date / 1000 if raw_date > 1e10 else raw_date
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        raw = str(raw_date).strip()
        if not raw:
            return date.today().isoformat()
        if len(raw) == 10 and raw.count("-") == 2:
            return raw
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return date.today().isoformat()


def _to_seconds(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
        text = str(raw).strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None


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

        md = {
            "date": date_str,
            "account": payload.get("account") or payload.get("metadata", {}).get("account") or "Unknown",
            "opportunity": payload.get("opportunity") or payload.get("metadata", {}).get("opportunity"),
            "stage": payload.get("stage") or payload.get("metadata", {}).get("stage"),
            "rep_email": payload.get("rep_email") or payload.get("metadata", {}).get("rep_email") or "unknown@example.com",
            "se_email": payload.get("se_email") or payload.get("metadata", {}).get("se_email"),
            "call_outcome": payload.get("call_outcome") or payload.get("metadata", {}).get("call_outcome"),
        }

        speaker_map = payload.get("speaker_map") or conv.get("speaker_map") or {}
        if not isinstance(speaker_map, dict):
            speaker_map = {}

        if not speaker_map:
            participants = payload.get("participants") or conv.get("participants") or []
            for idx, participant in enumerate(participants, start=1):
                if not isinstance(participant, dict):
                    continue
                speaker_map[f"S{idx}"] = {
                    "name": participant.get("name") or participant.get("email") or f"Speaker {idx}",
                    "role": participant.get("role") or "other",
                    "email": participant.get("email"),
                }

        raw_turns = (
            payload.get("turns")
            or payload.get("speaker_turns")
            or payload.get("transcript_turns")
            or conv.get("turns")
            or []
        )
        turns: list[dict] = []
        if isinstance(raw_turns, list):
            for turn in raw_turns:
                if not isinstance(turn, dict):
                    continue
                text = (turn.get("text") or turn.get("utterance") or "").strip()
                if not text:
                    continue
                speaker_id = (
                    turn.get("speaker_id")
                    or turn.get("speaker")
                    or turn.get("participant_id")
                    or "S1"
                )
                turns.append(
                    {
                        "speaker_id": str(speaker_id),
                        "start_time_sec": _to_seconds(
                            turn.get("start_time_sec")
                            if turn.get("start_time_sec") is not None
                            else turn.get("start_time")
                            if turn.get("start_time") is not None
                            else turn.get("start")
                        ),
                        "end_time_sec": _to_seconds(
                            turn.get("end_time_sec")
                            if turn.get("end_time_sec") is not None
                            else turn.get("end_time")
                            if turn.get("end_time") is not None
                            else turn.get("end")
                        ),
                        "text": text,
                    }
                )

        return {
            "chorus_call_id": payload.get("chorus_call_id") or payload.get("id"),
            "engagement_type": payload.get("engagement_type"),
            "meeting_summary": payload.get("meeting_summary"),
            "action_items": payload.get("action_items") or [],
            "metadata": md,
            "speaker_map": speaker_map,
            "turns": turns,
            "recording_url": payload.get("recording_url"),
            "transcript_url": payload.get("transcript_url"),
        }

    def _upsert_call(self, normalized: dict) -> ChorusCall:
        from sqlalchemy.dialects.mysql import insert as _mysql_insert

        md = normalized.get("metadata", {})
        call_id = normalized["chorus_call_id"]
        participants = list((normalized.get("speaker_map") or {}).values())
        values = {
            "chorus_call_id": call_id,
            "engagement_type": normalized.get("engagement_type") or "call",
            "meeting_summary": normalized.get("meeting_summary"),
            "action_items": normalized.get("action_items") or [],
            "date": date.fromisoformat(md.get("date")),
            "account": md.get("account", "Unknown"),
            "opportunity": md.get("opportunity"),
            "stage": md.get("stage"),
            "rep_email": md.get("rep_email", "unknown@example.com"),
            "se_email": md.get("se_email"),
            "call_outcome": _coerce_outcome(md.get("call_outcome")),
            "participants": participants,
            "recording_url": normalized.get("recording_url"),
            "transcript_url": normalized.get("transcript_url"),
        }

        dialect = self.db.bind.dialect.name if self.db.bind else ""
        if dialect == "mysql":
            # Atomic upsert — safe for concurrent threads, no lock contention
            stmt = _mysql_insert(ChorusCall).values(**values)
            stmt = stmt.on_duplicate_key_update(**{k: stmt.inserted[k] for k in values if k != "chorus_call_id"})
            self.db.execute(stmt)
            self.db.flush()
        else:
            existing = self.db.execute(select(ChorusCall).where(ChorusCall.chorus_call_id == call_id)).scalar_one_or_none()
            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                row = ChorusCall(**values)
                self.db.add(row)
            self.db.flush()

        return self.db.execute(select(ChorusCall).where(ChorusCall.chorus_call_id == call_id)).scalar_one()

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

    def _replace_chunks(self, doc: KBDocument, normalized: dict, call: ChorusCall) -> list[str]:
        self.db.execute(delete(KBChunk).where(KBChunk.document_id == doc.id))

        turns = normalized.get("turns", [])
        meeting_summary = normalized.get("meeting_summary") or ""
        action_items = normalized.get("action_items") or []

        # Assemble call-level metadata to merge into each chunk's metadata_json
        call_metadata: dict[str, str] = {
            "rep_email": call.rep_email,
            "account": call.account,
            "date": call.date.isoformat(),
        }
        if call.se_email:
            call_metadata["se_email"] = call.se_email
        if call.stage:
            call_metadata["stage"] = call.stage
        if call.call_outcome:
            call_metadata["call_outcome"] = call.call_outcome

        if turns:
            chunks = chunk_transcript_turns(turns, normalized.get("speaker_map", {}))
        elif meeting_summary or action_items:
            # No transcript — embed the Chorus-generated summary + action items instead
            parts = []
            if meeting_summary:
                parts.append(f"Meeting Summary:\n{meeting_summary}")
            if action_items:
                parts.append("Action Items:\n" + "\n".join(f"- {a}" for a in action_items))
            text = "\n\n".join(parts)
            chunks = [TextChunk(text=text, token_count=len(text.split()), metadata={})]
        else:
            return []

        embed_texts = [_build_embed_text(c.text, call_metadata) for c in chunks]
        embeddings = self.embedder.batch_embed(embed_texts)
        snippets: list[str] = []
        for idx, (chunk, emb, store_text) in enumerate(zip(chunks, embeddings, embed_texts)):
            self.db.add(
                KBChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=store_text,
                    token_count=chunk.token_count,
                    embedding=emb,
                    metadata_json={**chunk.metadata, **call_metadata},
                    content_hash=sha256_text(store_text),
                )
            )
            snippets.append(store_text[:250])
        return snippets

    def _replace_artifact(self, call_id: str, normalized: dict, snippets: list[str]) -> None:
        self.db.execute(delete(CallArtifact).where(CallArtifact.chorus_call_id == call_id))

        meeting_summary = normalized.get("meeting_summary") or ""
        action_items = normalized.get("action_items") or []

        if meeting_summary or action_items:
            # Use Chorus's pre-generated summary — no OpenAI call needed
            self.db.add(
                CallArtifact(
                    chorus_call_id=call_id,
                    summary=meeting_summary or "No summary available.",
                    objections=[],
                    competitors_mentioned=[],
                    risks=[],
                    next_steps=action_items,
                    recommended_collateral=[],
                    follow_up_questions=[],
                    model_info={"source": "chorus_ai"},
                )
            )
        else:
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
        snippets = self._replace_chunks(doc, normalized, call)
        self._replace_artifact(normalized["chorus_call_id"], normalized, snippets)

    def sync(self, since: date | None = None) -> dict:
        from app.db.session import SessionLocal

        processed = 0
        total_seen = 0

        # Warm up TiDB Serverless before the first write (auto-pause wakeup can take 30-60s)
        warmup_db = SessionLocal()
        try:
            from sqlalchemy import text as _text
            warmup_db.execute(_text("SELECT 1"))
            warmup_db.execute(_text("SET SESSION innodb_lock_wait_timeout = 120"))
        except Exception:
            pass
        finally:
            warmup_db.close()

        for page in self.connector.fetch_calls_pages(since=since):
            total_seen += len(page)
            # Fresh DB session per page — avoids idle connection timeout during Chorus fetch
            page_db = SessionLocal()
            try:
                # Extend lock wait timeout for this session
                from sqlalchemy import text as _text
                try:
                    page_db.execute(_text("SET SESSION innodb_lock_wait_timeout = 120"))
                except Exception:
                    pass
                page_ingestor = TranscriptIngestor(page_db)
                for raw in page:
                    normalized = self._normalize(raw.payload)
                    call = page_ingestor._upsert_call(normalized)
                    doc = page_ingestor._upsert_document(normalized, call)
                    snippets = page_ingestor._replace_chunks(doc, normalized, call)
                    if normalized.get("turns") or normalized.get("meeting_summary") or normalized.get("action_items"):
                        page_ingestor._replace_artifact(normalized["chorus_call_id"], normalized, snippets)
                    processed += 1
                page_db.commit()
                logger.info("Chorus sync: committed %d/%d calls", processed, total_seen)
            except Exception:
                page_db.rollback()
                raise
            finally:
                page_db.close()

        return {"calls_seen": total_seen, "processed": processed}
