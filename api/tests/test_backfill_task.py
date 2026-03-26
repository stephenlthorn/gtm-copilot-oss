import json
from unittest.mock import MagicMock, patch


def _make_chunk(text="hello", chunk_index=0, embedding=None, source_type="google_drive", source_id="doc1"):
    chunk = MagicMock()
    chunk.text = text
    chunk.chunk_index = chunk_index
    chunk.embedding = embedding or [0.1, 0.2, 0.3]
    chunk.metadata_json = {}
    return chunk, source_type, source_id, "Test Doc", None


def test_backfill_inserts_chunks_into_knowledge_index():
    chunk, source_type, source_id, title, url = _make_chunk()

    mock_db = MagicMock()
    # First execute().all() returns 1 row
    mock_db.execute.return_value.all.return_value = [(chunk, source_type, source_id, title, url)]
    # execute().scalar_one_or_none() returns None (no existing KI row)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"), \
         patch("app.tasks.indexing_tasks.backfill_knowledge_index.apply_async") as mock_chain:

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    mock_db.add_all.assert_called_once()
    mock_chain.assert_called_once()
    assert result["status"] == "running"


def test_backfill_flips_cutover_when_no_rows_remain():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = []  # empty batch = done

    mock_config = MagicMock()
    mock_config.retrieval_cutover = False
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_config

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"):

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    assert mock_config.retrieval_cutover is True
    mock_db.commit.assert_called()
    assert result["status"] == "complete"


def test_backfill_skips_already_indexed_chunks():
    chunk, source_type, source_id, title, url = _make_chunk(source_id="already_indexed")

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [(chunk, source_type, source_id, title, url)]
    # Simulate: chunk already exists in knowledge_index
    existing_ki = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_ki

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"), \
         patch("app.tasks.indexing_tasks.backfill_knowledge_index.apply_async"):

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    # add_all should be called with empty list
    call_args = mock_db.add_all.call_args
    assert call_args is None or len(call_args[0][0]) == 0
