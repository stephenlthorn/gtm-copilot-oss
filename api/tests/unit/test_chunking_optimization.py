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
    payload = {
        "chorus_call_id": "abc",
        "metadata": {
            "date": "2026-03-01",
            "account": "Acme",
            "rep_email": "rep@corp.com",
            "call_outcome": "open",
        },
        "turns": [],
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
