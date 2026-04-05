"""Unit tests for the hybrid retrieval scoring pipeline.

Tests cover: _cosine, _keyword_score, _source_bias, _domain_term_boost,
_apply_filters, _query_terms, and the shared text_matching utilities.
"""
from __future__ import annotations

import math
import uuid
from unittest.mock import MagicMock

import pytest

from app.retrieval.service import HybridRetriever
from app.utils.text_matching import contains_term, lexical_overlap, query_terms


# ── _cosine ───────────────────────────────────────────────────────────────────

class TestCosine:
    def test_identical_vectors_return_one(self):
        v = [1.0, 0.0, 0.0]
        assert HybridRetriever._cosine(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert HybridRetriever._cosine(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_return_negative_one(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert HybridRetriever._cosine(a, b) == pytest.approx(-1.0)

    def test_none_inputs_return_zero(self):
        assert HybridRetriever._cosine(None, [1.0]) == 0.0
        assert HybridRetriever._cosine([1.0], None) == 0.0
        assert HybridRetriever._cosine(None, None) == 0.0

    def test_empty_vectors_return_zero(self):
        assert HybridRetriever._cosine([], [1.0]) == 0.0
        assert HybridRetriever._cosine([1.0], []) == 0.0

    def test_dimension_mismatch_still_computes(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0]
        result = HybridRetriever._cosine(a, b)
        assert result == pytest.approx(1.0)

    def test_normalized_vectors(self):
        a = [0.6, 0.8]
        b = [0.8, 0.6]
        expected = (0.6 * 0.8 + 0.8 * 0.6) / (1.0 * 1.0)
        assert HybridRetriever._cosine(a, b) == pytest.approx(expected)


# ── _keyword_score ───────────────────────────────────────���────────────────────

class TestKeywordScore:
    def test_empty_terms_return_zero(self):
        assert HybridRetriever._keyword_score("some text", []) == 0.0

    def test_no_matches_return_zero(self):
        assert HybridRetriever._keyword_score("hello world", ["missing"]) == 0.0

    def test_single_match_scores_positive(self):
        score = HybridRetriever._keyword_score("The TiFlash engine is fast", ["tiflash"])
        assert score > 0.0

    def test_term_frequency_affects_score(self):
        terms = ["tiflash", "migration", "replication", "aurora", "performance", "latency", "benchmark"]
        text_sparse = "tiflash is a columnar engine used for analytics workloads"
        text_dense = "tiflash tiflash tiflash is a columnar engine used for tiflash analytics"
        score_sparse = HybridRetriever._keyword_score(text_sparse, terms)
        score_dense = HybridRetriever._keyword_score(text_dense, terms)
        assert score_dense > score_sparse

    def test_longer_terms_score_higher(self):
        text = "replication lag migration"
        score_short = HybridRetriever._keyword_score(text, ["lag"])
        score_long = HybridRetriever._keyword_score(text, ["replication"])
        assert score_long > score_short

    def test_multiple_terms_all_matching(self):
        text = "tikv replication lag is high"
        score = HybridRetriever._keyword_score(text, ["tikv", "replication", "lag"])
        assert score > 0.5

    def test_score_capped_at_one(self):
        text = "word " * 100
        score = HybridRetriever._keyword_score(text, ["word"])
        assert score <= 1.0

    def test_word_boundary_respected(self):
        score_no_match = HybridRetriever._keyword_score("prefixed_term_suffixed", ["term"])
        score_match = HybridRetriever._keyword_score("the term is here", ["term"])
        assert score_match > score_no_match


# ── _source_bias ──────────────────────────────────────────────────────────────

class TestSourceBias:
    def _make_doc(self, title: str) -> MagicMock:
        doc = MagicMock()
        doc.title = title
        return doc

    def test_docs_markdown_gets_positive_bias(self):
        doc = self._make_doc("github/project/docs/guide.md")
        bias = HybridRetriever._source_bias(doc)
        assert bias > 0

    def test_test_files_get_negative_bias(self):
        doc = self._make_doc("project/tests/test_something.py")
        bias = HybridRetriever._source_bias(doc)
        assert bias < 0

    def test_toc_files_get_large_negative_bias(self):
        doc = self._make_doc("docs/toc.md")
        bias = HybridRetriever._source_bias(doc)
        assert bias <= -0.20

    def test_plain_markdown_gets_small_positive(self):
        doc = self._make_doc("notes.md")
        bias = HybridRetriever._source_bias(doc)
        assert bias > 0

    def test_source_code_gets_negative(self):
        doc = self._make_doc("app/service.py")
        bias = HybridRetriever._source_bias(doc)
        assert bias < 0

    def test_release_notes_get_negative(self):
        doc = self._make_doc("project/releases/v3.0.md")
        bias = HybridRetriever._source_bias(doc)
        assert bias < 0

    def test_neutral_title_returns_zero(self):
        doc = self._make_doc("A plain document")
        bias = HybridRetriever._source_bias(doc)
        assert bias == 0.0


# ── _domain_term_boost ────────────────────────────────────────────────────────

class TestDomainTermBoost:
    def test_no_domain_terms_return_zero(self):
        boost = HybridRetriever._domain_term_boost(["something"], "title", "text about nothing")
        assert boost == 0.0

    def test_domain_term_in_query_and_text(self):
        boost = HybridRetriever._domain_term_boost(["tiflash"], "TiFlash Guide", "tiflash engine details")
        assert boost > 0.0

    def test_domain_term_in_query_but_not_text(self):
        boost = HybridRetriever._domain_term_boost(["tiflash"], "Unrelated", "nothing relevant here")
        assert boost == 0.0

    def test_multiple_domain_terms_boost_higher(self):
        boost_one = HybridRetriever._domain_term_boost(["tikv"], "TiKV Guide", "tikv storage layer")
        boost_two = HybridRetriever._domain_term_boost(
            ["tikv", "replication"], "TiKV Replication", "tikv replication protocol"
        )
        assert boost_two > boost_one

    def test_boost_capped_at_024(self):
        terms = ["tiflash", "tikv", "htap", "replication", "mpp", "ddl"]
        boost = HybridRetriever._domain_term_boost(
            terms, "Everything", " ".join(terms) * 10
        )
        assert boost <= 0.24

    def test_empty_query_terms_return_zero(self):
        assert HybridRetriever._domain_term_boost([], "title", "text") == 0.0


# ── _apply_filters ────────────────────────────────────────────────────────────

class TestApplyFilters:
    def _make_doc(self, source_type: str, tags: dict | None = None) -> MagicMock:
        doc = MagicMock()
        doc.source_type = MagicMock()
        doc.source_type.value = source_type
        doc.tags = tags or {}
        return doc

    def test_no_filters_passes_all(self):
        doc = self._make_doc("google_drive")
        assert HybridRetriever._apply_filters(doc, {})

    def test_source_type_filter_matches(self):
        doc = self._make_doc("google_drive")
        assert HybridRetriever._apply_filters(doc, {"source_type": ["google_drive"]})

    def test_source_type_filter_rejects(self):
        doc = self._make_doc("feishu")
        assert not HybridRetriever._apply_filters(doc, {"source_type": ["google_drive"]})

    def test_viewer_email_allows_own_docs(self):
        doc = self._make_doc("google_drive", {"user_email": "alice@example.com"})
        assert HybridRetriever._apply_filters(doc, {"viewer_email": "alice@example.com"})

    def test_viewer_email_blocks_other_users_docs(self):
        doc = self._make_doc("google_drive", {"user_email": "bob@example.com"})
        assert not HybridRetriever._apply_filters(doc, {"viewer_email": "alice@example.com"})

    def test_shared_drive_docs_without_user_email_are_visible(self):
        doc = self._make_doc("google_drive", {})
        assert HybridRetriever._apply_filters(doc, {"viewer_email": "anyone@example.com"})

    def test_memory_docs_require_matching_email(self):
        doc = self._make_doc("memory", {"user_email": "alice@example.com"})
        assert HybridRetriever._apply_filters(doc, {"viewer_email": "alice@example.com"})

    def test_memory_docs_without_email_blocked(self):
        doc = self._make_doc("memory", {})
        assert not HybridRetriever._apply_filters(doc, {"viewer_email": "alice@example.com"})

    def test_memory_docs_block_other_users(self):
        doc = self._make_doc("memory", {"user_email": "bob@example.com"})
        assert not HybridRetriever._apply_filters(doc, {"viewer_email": "alice@example.com"})

    def test_chorus_docs_ignore_viewer_email(self):
        doc = self._make_doc("chorus", {"rep_email": "alice@example.com"})
        assert HybridRetriever._apply_filters(doc, {"viewer_email": "bob@example.com"})

    def test_account_filter_matches(self):
        doc = self._make_doc("chorus", {"account": "Acme"})
        assert HybridRetriever._apply_filters(doc, {"account": ["acme"]})

    def test_account_filter_rejects(self):
        doc = self._make_doc("chorus", {"account": "Other"})
        assert not HybridRetriever._apply_filters(doc, {"account": ["acme"]})


# ── shared text_matching utilities ────────────────────────────────────────────

class TestTextMatching:
    def test_contains_term_basic(self):
        assert contains_term("hello world", "hello")
        assert not contains_term("helloworld", "hello")

    def test_contains_term_case_sensitive_on_lowered(self):
        assert contains_term("the tiflash engine", "tiflash")

    def test_query_terms_filters_stop_words(self):
        terms = query_terms("what is the migration process")
        assert "what" not in terms
        assert "the" not in terms
        assert "migration" in terms
        assert "process" in terms

    def test_query_terms_filters_short_tokens(self):
        terms = query_terms("an is at migration")
        assert "an" not in terms
        assert "is" not in terms
        assert "migration" in terms

    def test_query_terms_deduplicates(self):
        terms = query_terms("migration migration migration")
        assert terms.count("migration") == 1

    def test_lexical_overlap_full_match(self):
        overlap = lexical_overlap("tikv replication lag details", "tikv replication lag")
        assert overlap > 0.8

    def test_lexical_overlap_no_match(self):
        overlap = lexical_overlap("completely unrelated text", "tikv replication")
        assert overlap == 0.0

    def test_lexical_overlap_partial(self):
        overlap = lexical_overlap("tikv is fast", "tikv replication lag")
        assert 0.0 < overlap < 1.0
