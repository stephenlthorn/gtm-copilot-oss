"""Tests for chunking optimization changes."""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Task 1: Migration / model tests
# ---------------------------------------------------------------------------

def test_chorus_call_has_call_outcome_field():
    """ChorusCall model must expose call_outcome as a mapped attribute."""
    from app.models.entities import ChorusCall
    # Verify the column exists in the mapper (no DB needed)
    mapper = ChorusCall.__mapper__
    assert "call_outcome" in [c.key for c in mapper.column_attrs]


def test_migration_adds_call_outcome_column():
    """Migration upgrade/downgrade must not raise on SQLite (non-MySQL dialect)."""
    import importlib.util, sys
    from pathlib import Path
    migration_path = Path(__file__).parents[2] / "alembic" / "versions" / "20260324_000001_add_hnsw_index_and_call_outcome.py"
    spec = importlib.util.spec_from_file_location(
        "migration_20260324",
        migration_path,
    )
    migration = importlib.util.module_from_spec(spec)
    sys.modules["migration_20260324"] = migration
    spec.loader.exec_module(migration)

    mock_op = MagicMock()
    mock_op.get_bind.return_value.dialect.name = "sqlite"
    migration.op = mock_op

    migration.upgrade()
    mock_op.add_column.assert_called_once()
    assert mock_op.add_column.call_args[0][0] == "chorus_calls"

    migration.downgrade()
    mock_op.drop_column.assert_called_once_with("chorus_calls", "call_outcome")


# ---------------------------------------------------------------------------
# Task 2: _coerce_outcome
# ---------------------------------------------------------------------------

def test_coerce_outcome_won():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("won") == "won"

def test_coerce_outcome_closed_won():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("closed won") == "won"

def test_coerce_outcome_closed_lost_mixed_case():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("Closed Lost") == "lost"

def test_coerce_outcome_no_decision():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("no decision") == "no_decision"

def test_coerce_outcome_open_maps_to_active():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("open") == "active"

def test_coerce_outcome_in_progress_maps_to_active():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("in progress") == "active"

def test_coerce_outcome_none_returns_none():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome(None) is None

def test_coerce_outcome_unrecognized_returns_none():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("something_random") is None


# ---------------------------------------------------------------------------
# Task 3: _normalize and _upsert_call for call_outcome
# ---------------------------------------------------------------------------

def test_normalize_extracts_call_outcome_from_top_level():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    payload = {
        "chorus_call_id": "abc",
        "date": "2026-03-01",
        "account": "Acme",
        "rep_email": "rep@corp.com",
        "call_outcome": "closed won",
        "turns": [],
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] == "closed won"


def test_normalize_extracts_call_outcome_from_metadata_dict():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    # Payload has call_outcome in a nested metadata sub-dict.
    # No top-level "turns" key — so the early-return guard is NOT triggered
    # and the normalization path (lines 73-81) actually runs.
    payload = {
        "chorus_call_id": "abc",
        "metadata": {
            "date": "2026-03-01",
            "account": "Acme",
            "rep_email": "rep@corp.com",
            "call_outcome": "open",
        },
        # Note: no "turns" key — normalization runs instead of early-return
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] == "open"


def test_normalize_call_outcome_none_when_absent():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    payload = {
        "chorus_call_id": "abc",
        "date": "2026-03-01",
        "account": "Acme",
        "rep_email": "rep@corp.com",
        "turns": [],
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] is None


def test_upsert_call_persists_call_outcome():
    """_upsert_call must include call_outcome in values via _coerce_outcome."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from unittest.mock import MagicMock

    db = MagicMock()
    db.bind.dialect.name = "sqlite"
    ingestor = TranscriptIngestor.__new__(TranscriptIngestor)
    ingestor.db = db

    # sqlite path: scalar_one_or_none returns None → new row added
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalar_one.return_value = MagicMock(
        chorus_call_id="test-id", call_outcome="won"
    )

    normalized = {
        "chorus_call_id": "test-id",
        "engagement_type": "call",
        "meeting_summary": None,
        "action_items": [],
        "metadata": {
            "date": "2026-03-01",
            "account": "Acme",
            "rep_email": "rep@corp.com",
            "se_email": None,
            "stage": None,
            "call_outcome": "closed won",
        },
        "speaker_map": {},
        "recording_url": None,
        "transcript_url": None,
    }

    ingestor._upsert_call(normalized)
    # The ChorusCall was added with call_outcome coerced from "closed won" -> "won"
    added_obj = db.add.call_args[0][0]
    assert added_obj.call_outcome == "won"


# ---------------------------------------------------------------------------
# Task 4: _build_embed_text
# ---------------------------------------------------------------------------

def _make_call_metadata(**overrides):
    base = {
        "rep_email": "alice@corp.com",
        "account": "Acme Corp",
        "date": "2026-03-15",
    }
    base.update(overrides)
    return base


def test_build_embed_text_with_stage():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata(stage="Discovery")
    result = _build_embed_text("some transcript text", meta)
    assert result == "Acme Corp | Discovery | 2026-03-15 | rep:alice@corp.com\n\nsome transcript text"


def test_build_embed_text_without_stage():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata()  # no stage key
    result = _build_embed_text("some transcript text", meta)
    assert result == "Acme Corp | 2026-03-15 | rep:alice@corp.com\n\nsome transcript text"


def test_build_embed_text_empty_stage_omitted():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata(stage="")
    result = _build_embed_text("some transcript text", meta)
    # Empty string is falsy — prefix must NOT contain double-pipe
    assert " |  | " not in result
    assert "2026-03-15" in result


def test_build_embed_text_chunk_text_unchanged():
    from app.ingest.transcript_ingestor import _build_embed_text
    chunk_text = "00:01:23 AE: Let me understand your current architecture..."
    meta = _make_call_metadata(stage="Discovery")
    result = _build_embed_text(chunk_text, meta)
    assert result.endswith(chunk_text)
    # chunk_text appears verbatim after the double newline separator
    assert "\n\n" + chunk_text in result


# ---------------------------------------------------------------------------
# Task 5: _replace_chunks metadata + embedding
# ---------------------------------------------------------------------------

def _make_chorus_call(**overrides):
    from datetime import date as date_cls
    from unittest.mock import MagicMock
    call = MagicMock()
    call.rep_email = "alice@corp.com"
    call.account = "Acme Corp"
    call.date = date_cls(2026, 3, 15)
    call.se_email = None
    call.stage = None
    call.call_outcome = None
    for k, v in overrides.items():
        setattr(call, k, v)
    return call


def _make_ingestor_with_mock_db():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from unittest.mock import MagicMock
    ingestor = TranscriptIngestor.__new__(TranscriptIngestor)
    ingestor.db = MagicMock()
    ingestor.embedder = MagicMock()
    ingestor.embedder.batch_embed.return_value = [[0.1] * 1536]
    ingestor.generator = MagicMock()
    return ingestor


def _minimal_normalized_with_turns():
    return {
        "chorus_call_id": "call-001",
        "speaker_map": {"S1": {"name": "AE", "role": "ae", "email": "alice@corp.com"}},
        "turns": [
            {"speaker_id": "S1", "start_time_sec": 0, "end_time_sec": 60,
             "text": "Hello and welcome to this call about your architecture."},
        ],
        "meeting_summary": None,
        "action_items": [],
    }


def test_replace_chunks_metadata_has_rep_email_and_account():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from unittest.mock import MagicMock

    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call()

    doc = MagicMock()
    doc.id = "doc-001"

    normalized = _minimal_normalized_with_turns()

    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append

    ingestor._replace_chunks(doc, normalized, call)

    assert len(added_chunks) >= 1
    for chunk in added_chunks:
        assert chunk.metadata_json["rep_email"] == "alice@corp.com"
        assert chunk.metadata_json["account"] == "Acme Corp"
        assert chunk.metadata_json["date"] == "2026-03-15"


def test_replace_chunks_stage_absent_when_call_stage_none():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage=None)
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert "stage" not in chunk.metadata_json


def test_replace_chunks_call_outcome_absent_when_none():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(call_outcome=None)
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert "call_outcome" not in chunk.metadata_json


def test_replace_chunks_call_outcome_present_when_set():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(call_outcome="won")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert chunk.metadata_json["call_outcome"] == "won"


def test_replace_chunks_text_is_raw_transcript_not_prefixed():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert not re.match(r"^\S.*\|.*rep:", chunk.text)


def test_replace_chunks_embed_text_is_prefixed():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    ingestor._replace_chunks(doc, normalized, call)
    embed_arg = ingestor.embedder.batch_embed.call_args.args[0][0]
    assert re.match(r"^\S.*\|.*rep:", embed_arg)


def test_replace_chunks_fallback_path_text_not_prefixed():
    """Summary-only path: KBChunk.text must not contain prefix."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = {
        "chorus_call_id": "call-001",
        "speaker_map": {},
        "turns": [],
        "meeting_summary": "Great call about architecture.",
        "action_items": [],
    }
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    assert len(added_chunks) == 1
    assert not re.match(r"^\S.*\|.*rep:", added_chunks[0].text)
    embed_arg = ingestor.embedder.batch_embed.call_args.args[0][0]
    assert re.match(r"^\S.*\|.*rep:", embed_arg)


def test_replace_chunks_preserves_time_window_keys():
    """start_time_sec / end_time_sec from chunk_transcript_turns must survive the metadata merge."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call()
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    assert len(added_chunks) >= 1
    for chunk in added_chunks:
        assert "start_time_sec" in chunk.metadata_json
        assert "end_time_sec" in chunk.metadata_json


# ---------------------------------------------------------------------------
# Task 6: _apply_filters chunk-level filters
# ---------------------------------------------------------------------------

def _make_doc(source_type="chorus"):
    from app.models.entities import KBDocument, SourceType
    from unittest.mock import MagicMock
    doc = MagicMock(spec=KBDocument)
    doc.source_type = MagicMock()
    doc.source_type.value = source_type
    doc.tags = {"account": "Acme Corp"}
    return doc


def _make_chunk(metadata_json=None):
    from app.models.entities import KBChunk
    from unittest.mock import MagicMock
    chunk = MagicMock(spec=KBChunk)
    chunk.metadata_json = metadata_json or {}
    return chunk


def test_apply_filters_rep_email_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "alice@corp.com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_rep_email_case_insensitive():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "Alice@Corp.Com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_rep_email_mismatch_excluded():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "bob@corp.com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is False


def test_apply_filters_rep_email_missing_key_excluded():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({})  # no rep_email key
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is False


def test_apply_filters_rep_email_noop_for_non_chorus():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc(source_type="google_drive")
    chunk = _make_chunk({})  # no rep_email, but not CHORUS
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_stage_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"stage": "Discovery"})
    assert HybridRetriever._apply_filters(doc, {"stage": ["discovery", "Demo"]}, chunk) is True


def test_apply_filters_stage_mismatch():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"stage": "Closed"})
    assert HybridRetriever._apply_filters(doc, {"stage": ["discovery"]}, chunk) is False


def test_apply_filters_call_outcome_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"call_outcome": "won"})
    assert HybridRetriever._apply_filters(doc, {"call_outcome": ["won"]}, chunk) is True


def test_apply_filters_call_outcome_mismatch():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"call_outcome": "lost"})
    assert HybridRetriever._apply_filters(doc, {"call_outcome": ["won"]}, chunk) is False


def test_apply_filters_no_filters_all_pass():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({})
    assert HybridRetriever._apply_filters(doc, {}, chunk) is True


def test_apply_filters_account_still_uses_doc_tags_for_non_chorus():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc(source_type="google_drive")
    doc.tags = {"account": "acme corp"}
    chunk = _make_chunk({})
    assert HybridRetriever._apply_filters(doc, {"account": ["Acme Corp"]}, chunk) is True
