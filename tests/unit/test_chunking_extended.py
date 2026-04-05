"""Extended unit tests for chunking functions covering edge cases."""
from __future__ import annotations

import pytest

from app.utils.chunking import (
    chunk_markdown_heading_aware,
    chunk_pdf_pages,
    chunk_slides,
    chunk_transcript_turns,
    estimate_tokens,
    _split_long_block,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 1

    def test_single_word(self):
        assert estimate_tokens("hello") >= 1

    def test_proportional_to_word_count(self):
        short = estimate_tokens("one two three")
        long = estimate_tokens("one two three four five six seven eight nine ten")
        assert long > short


class TestSplitLongBlock:
    def test_short_text_returns_single_chunk(self):
        result = _split_long_block("hello world")
        assert len(result) == 1

    def test_long_text_splits_into_overlapping_chunks(self):
        words = " ".join(f"word{i}" for i in range(1500))
        result = _split_long_block(words, chunk_size=700, overlap=100)
        assert len(result) > 1
        first_words = set(result[0].split())
        second_words = set(result[1].split())
        overlap = first_words & second_words
        assert len(overlap) > 0

    def test_exact_chunk_size_returns_single(self):
        words = " ".join(f"w{i}" for i in range(700))
        result = _split_long_block(words, chunk_size=700)
        assert len(result) == 1


class TestChunkMarkdownHeadingAware:
    def test_empty_document(self):
        assert chunk_markdown_heading_aware("") == []

    def test_no_headings(self):
        chunks = chunk_markdown_heading_aware("Just some plain text content.")
        assert len(chunks) == 1
        assert chunks[0].metadata["heading"] == "Document"

    def test_heading_text_included_in_chunk(self):
        md = "# Competitive Analysis\n\nWe are better than them."
        chunks = chunk_markdown_heading_aware(md)
        assert len(chunks) == 1
        assert "Competitive Analysis" in chunks[0].text

    def test_multiple_headings(self):
        md = "# Section A\nContent A\n# Section B\nContent B"
        chunks = chunk_markdown_heading_aware(md)
        assert len(chunks) == 2
        assert chunks[0].metadata["heading"] == "Section A"
        assert chunks[1].metadata["heading"] == "Section B"

    def test_empty_section_skipped(self):
        md = "# Empty Section\n# Real Section\nContent here"
        chunks = chunk_markdown_heading_aware(md)
        assert len(chunks) == 1
        assert chunks[0].metadata["heading"] == "Real Section"

    def test_content_before_first_heading(self):
        md = "Preamble text\n# First Heading\nBody text"
        chunks = chunk_markdown_heading_aware(md)
        assert len(chunks) == 2
        assert chunks[0].metadata["heading"] == "Document"


class TestChunkPdfPages:
    def test_empty_pages(self):
        assert chunk_pdf_pages([]) == []

    def test_blank_pages_skipped(self):
        assert chunk_pdf_pages(["", "   ", "\n"]) == []

    def test_single_page(self):
        chunks = chunk_pdf_pages(["This is page one content."])
        assert len(chunks) == 1
        assert chunks[0].metadata["page"] == 1

    def test_multiple_pages(self):
        chunks = chunk_pdf_pages(["Page 1", "Page 2", "Page 3"])
        assert len(chunks) == 3
        assert chunks[2].metadata["page"] == 3


class TestChunkSlides:
    def test_empty_slides(self):
        assert chunk_slides([]) == []

    def test_blank_slides_skipped(self):
        assert chunk_slides(["", "  "]) == []

    def test_normal_slide(self):
        chunks = chunk_slides(["Slide 1 content"])
        assert len(chunks) == 1
        assert chunks[0].metadata["slide"] == 1

    def test_large_slide_is_split(self):
        large_slide = " ".join(f"word{i}" for i in range(1500))
        chunks = chunk_slides([large_slide])
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["slide"] == 1


class TestChunkTranscriptTurns:
    def test_empty_turns(self):
        assert chunk_transcript_turns([], {}) == []

    def test_single_short_turn(self):
        turns = [{"speaker_id": "A", "start_time_sec": 0, "end_time_sec": 10, "text": "Hello"}]
        chunks = chunk_transcript_turns(turns, {"A": {"name": "Alice", "role": "rep"}})
        assert len(chunks) == 1

    def test_long_conversation_splits(self):
        turns = [
            {"speaker_id": "A", "start_time_sec": i * 10, "end_time_sec": i * 10 + 10, "text": f"Turn {i} content goes here."}
            for i in range(30)
        ]
        chunks = chunk_transcript_turns(turns, {"A": {"name": "Alice", "role": "rep"}})
        assert len(chunks) > 1

    def test_metadata_contains_timestamps(self):
        turns = [
            {"speaker_id": "A", "start_time_sec": 0, "end_time_sec": 50, "text": "Hello"},
            {"speaker_id": "B", "start_time_sec": 50, "end_time_sec": 100, "text": "World"},
        ]
        chunks = chunk_transcript_turns(turns, {}, min_seconds=45, max_seconds=90)
        assert chunks[0].metadata["start_time_sec"] == 0
