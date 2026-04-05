"""Unit tests for the query rewriter."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.query_rewrite import QueryRewriter


class TestQueryRewriter:
    def test_expand_without_client_returns_original(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key=None)
        rewriter._client = None
        result = rewriter.expand("test query", "oracle")
        assert result["variants"] == ["test query"]
        assert result["hyde"] == "test query"

    def test_rewrite_without_client_returns_original(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key=None)
        rewriter._client = None
        result = rewriter.rewrite("test query", "oracle")
        assert result == "test query"

    def test_expand_with_valid_response(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key="test")
        client = MagicMock()
        rewriter._client = client

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({
            "variants": ["variant 1", "variant 2", "variant 3"],
            "hyde": "This is a hypothetical document about the query topic."
        })
        client.chat.completions.create.return_value = resp

        result = rewriter.expand("test query", "oracle")
        assert len(result["variants"]) == 3
        assert result["hyde"] != "test query"

    def test_expand_with_empty_variants_falls_back(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key="test")
        client = MagicMock()
        rewriter._client = client

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({
            "variants": [],
            "hyde": ""
        })
        client.chat.completions.create.return_value = resp

        result = rewriter.expand("test query", "oracle")
        assert result["variants"] == ["test query"]
        assert result["hyde"] == "test query"

    def test_expand_handles_exception(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key="test")
        client = MagicMock()
        rewriter._client = client
        client.chat.completions.create.side_effect = RuntimeError("API error")

        result = rewriter.expand("test query", "call_assistant")
        assert result["variants"] == ["test query"]
        assert result["hyde"] == "test query"

    def test_expand_truncates_to_three_variants(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key="test")
        client = MagicMock()
        rewriter._client = client

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({
            "variants": ["a", "b", "c", "d", "e"],
            "hyde": "doc"
        })
        client.chat.completions.create.return_value = resp

        result = rewriter.expand("test query", "oracle")
        assert len(result["variants"]) == 3

    def test_expand_unknown_mode_uses_oracle_context(self):
        rewriter = QueryRewriter()
        rewriter.settings = MagicMock(openai_api_key="test")
        client = MagicMock()
        rewriter._client = client

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps({
            "variants": ["v1"],
            "hyde": "doc"
        })
        client.chat.completions.create.return_value = resp

        result = rewriter.expand("test query", "unknown_mode")
        assert result["variants"] == ["v1"]
