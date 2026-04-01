from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_oracle_allowed_sources_excludes_feishu_and_includes_official_docs_default():
    from app.services.chat_orchestrator import ChatOrchestrator

    sources, source_priority = ChatOrchestrator._resolve_allowed_sources(None, "oracle")
    assert "feishu" not in sources
    assert "official_docs_online" in sources
    assert source_priority["official_docs_online"] > source_priority["memory"]


def test_oracle_allowed_sources_excludes_feishu_when_config_enabled():
    from app.services.chat_orchestrator import ChatOrchestrator

    config = SimpleNamespace(
        google_drive_enabled=True,
        chorus_enabled=True,
        feishu_enabled=True,  # legacy field should not be used anymore
    )
    sources, source_priority = ChatOrchestrator._resolve_allowed_sources(config, "oracle")
    assert "feishu" not in sources
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
