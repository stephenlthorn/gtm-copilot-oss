from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CallArtifact, ChorusCall, KBChunk, KBDocument, SourceType
from app.services.connectors.chorus import ChorusCallData, ChorusConnector
from app.services.embedding import EmbeddingService
from app.utils.chunking import chunk_transcript_turns
from app.utils.hashing import sha256_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    calls_fetched: int = 0
    calls_stored: int = 0
    transcripts_indexed: int = 0
    artifacts_created: int = 0
    errors: list[str] = field(default_factory=list)


class ChorusSyncService:
    """Fetches new calls from Chorus and stores them locally with indexed transcripts."""

    def __init__(self, connector: ChorusConnector, db: Session) -> None:
        self.connector = connector
        self.db = db
        self.embedder = EmbeddingService()

    async def sync_new_calls(self, org_id: int) -> SyncResult:
        last_call = self.db.execute(
            select(ChorusCall).order_by(ChorusCall.date.desc()).limit(1)
        ).scalar_one_or_none()

        since = datetime.combine(last_call.date, datetime.min.time()) if last_call else None
        calls = await self.connector.list_calls(since=since)

        stored = 0
        indexed = 0
        artifacts = 0
        errors: list[str] = []

        for call_data in calls:
            try:
                existing = self.db.execute(
                    select(ChorusCall).where(ChorusCall.chorus_call_id == call_data.call_id)
                ).scalar_one_or_none()

                if existing:
                    row = existing
                else:
                    row = self._store_call(call_data)
                    stored += 1

                # Index transcript if not yet indexed
                kb_doc = self.db.execute(
                    select(KBDocument).where(
                        KBDocument.source_type == SourceType.CHORUS,
                        KBDocument.source_id == call_data.call_id,
                    )
                ).scalar_one_or_none()

                if not kb_doc:
                    transcript = await self._fetch_and_store_transcript(call_data, row)
                    if transcript:
                        indexed += 1

                    self._create_artifact(call_data, transcript)
                    artifacts += 1

                self.db.flush()
            except Exception as exc:
                logger.exception("Failed to sync call %s", call_data.call_id)
                errors.append(f"{call_data.call_id}: {exc}")

        self.db.commit()
        return SyncResult(
            calls_fetched=len(calls),
            calls_stored=stored,
            transcripts_indexed=indexed,
            artifacts_created=artifacts,
            errors=errors,
        )

    def _store_call(self, data: ChorusCallData) -> ChorusCall:
        row = ChorusCall(
            chorus_call_id=data.call_id,
            date=data.date.date() if isinstance(data.date, datetime) else data.date,
            account=data.account,
            opportunity=data.opportunity,
            stage=data.stage,
            rep_email=data.rep_email or "unknown@example.com",
            se_email=data.se_email,
            participants=data.participants,
            recording_url=data.recording_url,
        )
        self.db.add(row)
        self.db.flush()
        return row

    async def _fetch_and_store_transcript(
        self, data: ChorusCallData, call: ChorusCall
    ) -> str | None:
        try:
            transcript = data.transcript or await self.connector.get_transcript(data.call_id)
        except Exception:
            logger.warning("Could not fetch transcript for call %s", data.call_id)
            return None

        if not transcript:
            return None

        doc = KBDocument(
            source_type=SourceType.CHORUS,
            source_id=data.call_id,
            title=f"Call Transcript: {call.account} {call.date.isoformat()}",
            url=call.recording_url,
            mime_type="text/plain",
            owner=call.rep_email,
            permissions_hash=sha256_text(f"{call.rep_email}:{call.se_email or ''}"),
            tags={
                "account": call.account,
                "date": call.date.isoformat(),
                "source_type": "call_transcript",
            },
        )
        self.db.add(doc)
        self.db.flush()

        self._index_transcript(doc, transcript, data)
        return transcript

    def _index_transcript(
        self, doc: KBDocument, transcript: str, data: ChorusCallData
    ) -> None:
        turns = [{"speaker_id": "S1", "start_time_sec": 0, "end_time_sec": 10, "text": transcript}]
        speaker_map = {"S1": {"name": data.rep_email or "Speaker", "role": "rep"}}
        chunks = chunk_transcript_turns(turns, speaker_map)
        embeddings = self.embedder.batch_embed([c.text for c in chunks]) if chunks else []

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

    async def sync_selected_calls(self, call_ids: list[str]) -> SyncResult:
        """Fetch and store a specific list of call IDs from the Chorus API."""
        stored = 0
        indexed = 0
        errors: list[str] = []

        # Refetch from list to get inline meeting_summary/action_items
        id_set = set(call_ids)
        all_calls = await self.connector.list_calls()
        call_map: dict[str, ChorusCallData] = {c.call_id: c for c in all_calls if c.call_id in id_set}

        for call_id in call_ids:
            try:
                call_data = call_map.get(call_id)
                if not call_data:
                    errors.append(f"{call_id}: not found in Chorus list")
                    continue

                existing = self.db.execute(
                    select(ChorusCall).where(ChorusCall.chorus_call_id == call_id)
                ).scalar_one_or_none()

                if existing:
                    row = existing
                else:
                    row = self._store_call(call_data)
                    stored += 1

                kb_doc = self.db.execute(
                    select(KBDocument).where(
                        KBDocument.source_type == SourceType.CHORUS,
                        KBDocument.source_id == call_id,
                    )
                ).scalar_one_or_none()

                if not kb_doc:
                    transcript = await self._fetch_and_store_transcript(call_data, row)
                    if transcript:
                        indexed += 1
                    self._create_artifact(call_data, transcript)

                self.db.flush()
            except Exception as exc:
                logger.exception("Failed to sync call %s", call_id)
                errors.append(f"{call_id}: {exc}")

        self.db.commit()
        return SyncResult(calls_fetched=len(call_ids), calls_stored=stored, transcripts_indexed=indexed, errors=errors)

    def _create_artifact(self, data: ChorusCallData, transcript: str | None) -> None:
        self.db.add(
            CallArtifact(
                chorus_call_id=data.call_id,
                summary=f"Call with {data.account}" + (f" - {data.opportunity}" if data.opportunity else ""),
                objections=[],
                competitors_mentioned=[],
                risks=[],
                next_steps=[],
                recommended_collateral=[],
                follow_up_questions=[],
                model_info={"source": "chorus_sync", "has_transcript": transcript is not None},
            )
        )
