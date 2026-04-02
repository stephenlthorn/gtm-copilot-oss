from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_oracle_allowed_sources_includes_official_docs_with_priority():
    from app.services.chat_orchestrator import ChatOrchestrator

    sources, source_priority = ChatOrchestrator._resolve_allowed_sources(None, "oracle")
    assert "official_docs_online" in sources
    assert source_priority["official_docs_online"] > source_priority["memory"]


def test_oracle_allowed_sources_with_config_returns_priority():
    from app.services.chat_orchestrator import ChatOrchestrator

    config = SimpleNamespace(
        google_drive_enabled=True,
        chorus_enabled=True,
    )
    sources, source_priority = ChatOrchestrator._resolve_allowed_sources(config, "oracle")
    assert "official_docs_online" in sources
    assert isinstance(source_priority, dict)


def test_hybrid_retriever_search_mysql_semantic_path_handles_query_variants():
    from app.retrieval.service import HybridRetriever

    db = MagicMock()
    db.bind.dialect.name = "mysql"
    db.execute.return_value.all.return_value = []

    retriever = HybridRetriever(db)
    retriever.embedder = MagicMock()
    retriever.embedder.client = object()  # semantic path enabled
    retriever.embedder.embed.return_value = [0.1, 0.2, 0.3]
    retriever.rewriter = MagicMock()
    retriever.rewriter.expand.return_value = {
        "variants": ["query variant one", "query variant two"],
        "hyde": "ideal answer passage",
    }
    retriever.reranker = MagicMock()
    retriever.reranker.rerank.side_effect = lambda _q, hits, top_k: hits[:top_k]

    hits = retriever.search("tiflash replication lag", top_k=6, filters={}, mode="oracle")
    assert hits == []


def _make_hit(score: float, title: str, text: str = "content", source_type: str = "official_docs_online"):
    hit = MagicMock()
    hit.score = score
    hit.title = title
    hit.text = text
    hit.source_type = source_type
    return hit


def test_nav_pages_demoted_not_removed():
    """TOC/overview pages should be sorted lower but not dropped from results."""
    from app.services.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator(db=None)
    # toc (0.9 - 0.30 = 0.60), overview (0.7 - 0.16 = 0.54), architecture (0.65, no penalty)
    hits = [
        _make_hit(0.9, "tidb/toc.md", "table of contents"),
        _make_hit(0.7, "tidb/tiflash/overview.md", "overview content"),
        _make_hit(0.65, "tidb/tiflash/architecture.md", "real content about tiflash"),
    ]

    result = orchestrator._apply_nav_penalty(hits)

    assert len(result) == 3
    titles = [h.title for h in result]
    assert "tidb/tiflash/architecture.md" in titles
    assert result[0].title == "tidb/tiflash/architecture.md"


def test_llm_reranked_hits_returned_even_with_low_overlap():
    """When LLM reranker returns results, they must not be discarded based on
    lexical overlap — semantic matches are valid even with few shared words."""
    from app.services.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator(db=None)
    hits = [
        _make_hit(0.85, "tidb/scalability.md", "distributed SQL horizontal scaling clusters"),
        _make_hit(0.72, "tidb/architecture.md", "consensus replication Raft protocol nodes"),
    ]

    result = orchestrator._apply_nav_penalty(hits)

    assert len(result) == 2
    assert result[0].title == "tidb/scalability.md"


def test_hits_never_emptied_due_to_quality_gate():
    """If search returns hits, they must be passed through — no quality gate
    should set hits=[] when the LLM reranker has already scored them."""
    from app.services.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator(db=None)
    hits = [_make_hit(0.5, "tidb/some-page.md", "some content")]

    result = orchestrator._apply_nav_penalty(hits)

    assert len(result) == 1
