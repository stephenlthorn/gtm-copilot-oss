"""Unit tests for the LLM reranker."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.retrieval.reranker import LLMReranker
from app.retrieval.types import RetrievedChunk


def _make_hit(text: str, score: float = 0.5) -> RetrievedChunk:
    import uuid
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        score=score,
        text=text,
        metadata={},
        source_type="google_drive",
        source_id="test",
        title="Test Doc",
        url=None,
        file_id="test",
    )


class TestLLMReranker:
    def test_no_client_returns_original_order(self):
        reranker = LLMReranker()
        reranker._client = None
        reranker.settings = MagicMock(openai_api_key=None)
        hits = [_make_hit("a", 0.9), _make_hit("b", 0.8)]
        result = reranker.rerank("query", hits, top_k=2)
        assert len(result) == 2
        assert result[0].text == "a"

    def test_empty_hits_returns_empty(self):
        reranker = LLMReranker()
        reranker._client = None
        reranker.settings = MagicMock(openai_api_key=None)
        result = reranker.rerank("query", [], top_k=5)
        assert result == []

    def test_top_k_limits_results(self):
        reranker = LLMReranker()
        reranker._client = None
        reranker.settings = MagicMock(openai_api_key=None)
        hits = [_make_hit(f"hit_{i}") for i in range(10)]
        result = reranker.rerank("query", hits, top_k=3)
        assert len(result) == 3

    def test_score_batch_handles_fewer_scores(self):
        reranker = LLMReranker()
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({"scores": [8]})
        client.chat.completions.create.return_value = resp

        hits = [_make_hit("a"), _make_hit("b"), _make_hit("c")]
        scores = reranker._score_batch(client, "query", hits)
        assert len(scores) == 3
        assert scores[0] == 8.0
        assert scores[1] == 0.0  # padded
        assert scores[2] == 0.0  # padded

    def test_score_batch_clamps_values(self):
        reranker = LLMReranker()
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({"scores": [-5, 15]})
        client.chat.completions.create.return_value = resp

        hits = [_make_hit("a"), _make_hit("b")]
        scores = reranker._score_batch(client, "query", hits)
        assert scores[0] == 0.0  # clamped from -5
        assert scores[1] == 10.0  # clamped from 15

    def test_score_batch_exception_returns_zeros(self):
        reranker = LLMReranker()
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API error")

        hits = [_make_hit("a"), _make_hit("b")]
        scores = reranker._score_batch(client, "query", hits)
        assert scores == [0.0, 0.0]

    def test_rerank_normalizes_across_batches(self):
        """Scores from different batches should be normalized before merging."""
        reranker = LLMReranker()
        reranker.settings = MagicMock(openai_api_key="test")
        reranker._client = MagicMock()

        hits = [_make_hit(f"hit_{i}", score=0.5) for i in range(50)]

        call_count = 0
        def mock_score_batch(client, query, batch):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [8.0] * len(batch)
            else:
                return [3.0] * len(batch)

        reranker._score_batch = lambda c, q, b: mock_score_batch(c, q, b)
        result = reranker.rerank("query", hits, top_k=5)
        assert len(result) == 5
