import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_service(cutover: bool = False):
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.retrieval_cutover = cutover
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_config

    from app.services.indexing.retrieval import HybridRetrievalService
    mock_embedder = MagicMock()
    mock_embedder.embed_chunks = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    svc = HybridRetrievalService(db=mock_db, embedding_service=mock_embedder)
    return svc, mock_db


@pytest.mark.asyncio
async def test_search_calls_legacy_when_not_cut_over():
    svc, mock_db = _make_service(cutover=False)

    with patch.object(svc, "_vector_search", return_value=[]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[]) as mock_legacy_vec, \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]) as mock_legacy_fts:

        await svc.search("test query", org_id=1, top_k=5)

    mock_legacy_vec.assert_called_once()
    mock_legacy_fts.assert_called_once()


@pytest.mark.asyncio
async def test_search_skips_legacy_after_cutover():
    svc, mock_db = _make_service(cutover=True)

    with patch.object(svc, "_vector_search", return_value=[]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[]) as mock_legacy_vec, \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]) as mock_legacy_fts:

        await svc.search("test query", org_id=1, top_k=5)

    mock_legacy_vec.assert_not_called()
    mock_legacy_fts.assert_not_called()


@pytest.mark.asyncio
async def test_search_deduplicates_results_across_tables():
    from app.services.indexing.retrieval import RetrievalResult

    same_result = RetrievalResult(
        chunk_text="shared content",
        source_type="google_drive",
        source_ref="doc_1",
        title="Doc 1",
        score=0.9,
        metadata={},
    )

    svc, mock_db = _make_service(cutover=False)

    with patch.object(svc, "_vector_search", return_value=[same_result]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[same_result]), \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]):

        results = await svc.search("shared content", org_id=1, top_k=10)

    texts = [r.chunk_text for r in results]
    assert texts.count("shared content") == 1
