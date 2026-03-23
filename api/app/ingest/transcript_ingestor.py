from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import delete, select
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


class TranscriptIngestor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connector = ChorusConnector()
        self.embedder = EmbeddingService()
        self.generator = ArtifactGenerator()

    @staticmethod
    def _normalize(payload: dict) -> dict:
        # Supports already-normalized test fixtures and light transformation from API payloads.
        if "metadata" in payload and "turns" in payload:
            return payload

        participants = payload.get("participants", [])
        speaker_map = {}
        for idx, p in enumerate(participants, start=1):
            speaker_map[f"S{idx}"] = {
                "name": p.get("name", f"Speaker {idx}"),
                "role": p.get("role", "other"),
                "email": p.get("email"),
            }

        turns = payload.get("turns", [])
        if turns and "speaker_id" not in turns[0]:
            normalized_turns = []
            for t in turns:
                normalized_turns.append(
                    {
                        "speaker_id": t.get("speaker", "S1"),
                        "start_time_sec": t.get("start_time_sec", 0),
                        "end_time_sec": t.get("end_time_sec", t.get("start_time_sec", 0) + 10),
                        "text": t.get("text", ""),
                    }
                )
            turns = normalized_turns

        md = {
            "date": payload.get("date") or payload.get("metadata", {}).get("date"),
            "account": payload.get("account") or payload.get("metadata", {}).get("account") or "Unknown",
            "opportunity": payload.get("opportunity") or payload.get("metadata", {}).get("opportunity"),
            "stage": payload.get("stage") or payload.get("metadata", {}).get("stage"),
            "rep_email": payload.get("rep_email") or payload.get("metadata", {}).get("rep_email") or "unknown@example.com",
            "se_email": payload.get("se_email") or payload.get("metadata", {}).get("se_email"),
            "call_outcome": payload.get("call_outcome") or payload.get("metadata", {}).get("call_outcome"),
        }

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
        call_metadata: dict = {
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
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.db.add(
                KBChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=emb,
                    metadata_json={**chunk.metadata, **call_metadata},
                    content_hash=sha256_text(chunk.text),
                )
            )
            snippets.append(chunk.text[:250])
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
