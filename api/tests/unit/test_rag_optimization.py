"""Tests for RAG optimization: score threshold filter, context assembler, chunk quality signals."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retrieved_chunk(score=0.5, token_count=100, text="some text"):
    from app.retrieval.types import RetrievedChunk
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        score=score,
        token_count=token_count,
        text=text,
        metadata={},
        source_type="chorus",
        source_id="src-1",
        title="Test Doc",
        url=None,
        file_id=None,
    )


# ---------------------------------------------------------------------------
# Area 2: _assemble_context token budget
# ---------------------------------------------------------------------------

def test_assemble_context_fits_all_within_budget():
    from app.services.llm import LLMService
    hits = [_make_retrieved_chunk(token_count=100) for _ in range(5)]
    result = LLMService._assemble_context(hits, token_budget=600)
    assert len(result) == 5


def test_assemble_context_stops_at_budget():
    from app.services.llm import LLMService
    hits = [_make_retrieved_chunk(token_count=300) for _ in range(5)]
    result = LLMService._assemble_context(hits, token_budget=700)
    assert len(result) == 2  # 300 + 300 = 600 ≤ 700; 300*3=900 > 700


def test_assemble_context_empty_hits():
    from app.services.llm import LLMService
    result = LLMService._assemble_context([], token_budget=6000)
    assert result == []


def test_assemble_context_single_chunk_exceeds_budget():
    from app.services.llm import LLMService
    hits = [_make_retrieved_chunk(token_count=10000)]
    result = LLMService._assemble_context(hits, token_budget=6000)
    assert len(result) == 0


def test_assemble_context_preserves_order():
    from app.services.llm import LLMService
    hits = [_make_retrieved_chunk(score=0.9, token_count=100, text=f"chunk-{i}") for i in range(3)]
    result = LLMService._assemble_context(hits, token_budget=6000)
    assert [h.text for h in result] == [h.text for h in hits]


# ---------------------------------------------------------------------------
# Area 3: FeedbackCreate schema with new fields
# ---------------------------------------------------------------------------

def test_feedback_create_accepts_citations_and_audit_id():
    from app.schemas.feedback import FeedbackCreate
    fb = FeedbackCreate(
        mode="oracle",
        query_text="test query",
        original_response="test response",
        rating="positive",
        citations=["abc-123", "def-456"],
        audit_id="audit-789",
    )
    assert fb.citations == ["abc-123", "def-456"]
    assert fb.audit_id == "audit-789"


def test_feedback_create_citations_optional():
    from app.schemas.feedback import FeedbackCreate
    fb = FeedbackCreate(
        mode="oracle",
        query_text="test query",
        original_response="test response",
        rating="negative",
    )
    assert fb.citations is None
    assert fb.audit_id is None


# ---------------------------------------------------------------------------
# Area 3: ChunkQualitySignal model
# ---------------------------------------------------------------------------

def test_chunk_quality_signal_model_fields():
    from app.models.feedback import ChunkQualitySignal
    assert hasattr(ChunkQualitySignal, "chunk_id")
    assert hasattr(ChunkQualitySignal, "signal")
    assert hasattr(ChunkQualitySignal, "query_mode")
    assert hasattr(ChunkQualitySignal, "created_at")


def test_chunk_quality_signal_table_name():
    from app.models.feedback import ChunkQualitySignal
    assert ChunkQualitySignal.__tablename__ == "chunk_quality_signals"


# ---------------------------------------------------------------------------
# Area 1: RetrievedChunk has token_count
# ---------------------------------------------------------------------------

def test_retrieved_chunk_has_token_count():
    from app.retrieval.types import RetrievedChunk
    chunk = _make_retrieved_chunk(token_count=42)
    assert chunk.token_count == 42


def test_retrieved_chunk_token_count_used_in_assembly():
    from app.services.llm import LLMService
    # Chunk with 50 tokens fits in budget of 100, second chunk (60) does not
    hits = [
        _make_retrieved_chunk(token_count=50),
        _make_retrieved_chunk(token_count=60),
    ]
    result = LLMService._assemble_context(hits, token_budget=100)
    assert len(result) == 1
    assert result[0].token_count == 50
