import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def connector():
    from app.ingest.feishu_connector import FeishuConnector
    c = FeishuConnector(app_id="test_id", app_secret="test_secret")
    c._tenant_token = "fake_token"  # skip auth
    return c


def test_list_wiki_spaces_returns_space_list(connector):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"space_id": "sp_abc", "name": "Sales Wiki"}],
            "has_more": False,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        spaces = connector.list_wiki_spaces()

    assert len(spaces) == 1
    assert spaces[0]["space_id"] == "sp_abc"


def test_list_wiki_nodes_returns_flat_node_list(connector):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [
                {"node_token": "n1", "obj_token": "doc_abc", "obj_type": "docx", "title": "My Doc"},
                {"node_token": "n2", "obj_token": "doc_xyz", "obj_type": "docx", "title": "Other Doc"},
            ],
            "has_more": False,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        nodes = connector.list_wiki_nodes("sp_abc")

    assert len(nodes) == 2
    assert nodes[0]["obj_token"] == "doc_abc"


def test_list_wiki_documents_collects_docx_from_all_spaces(connector):
    spaces_response = MagicMock()
    spaces_response.raise_for_status = MagicMock()
    spaces_response.json.return_value = {
        "code": 0,
        "data": {"items": [{"space_id": "sp1"}, {"space_id": "sp2"}], "has_more": False},
    }

    nodes_response = MagicMock()
    nodes_response.raise_for_status = MagicMock()
    nodes_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"obj_token": "doc_1", "obj_type": "docx", "title": "Doc 1"}],
            "has_more": False,
        },
    }

    with patch("httpx.get", side_effect=[spaces_response, nodes_response, nodes_response]):
        docs = connector.list_wiki_documents()

    assert any(d["token"] == "doc_1" for d in docs)


def test_list_wiki_documents_skips_non_docx_nodes(connector):
    spaces_response = MagicMock()
    spaces_response.raise_for_status = MagicMock()
    spaces_response.json.return_value = {
        "code": 0,
        "data": {"items": [{"space_id": "sp1"}], "has_more": False},
    }

    nodes_response = MagicMock()
    nodes_response.raise_for_status = MagicMock()
    nodes_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [
                {"obj_token": "sheet_1", "obj_type": "sheet", "title": "Spreadsheet"},
                {"obj_token": "doc_1", "obj_type": "docx", "title": "Doc 1"},
            ],
            "has_more": False,
        },
    }

    with patch("httpx.get", side_effect=[spaces_response, nodes_response]):
        docs = connector.list_wiki_documents()

    assert len(docs) == 1
    assert docs[0]["token"] == "doc_1"


def test_feishu_indexer_sync_includes_wiki_docs():
    """Indexer should call list_wiki_documents and index those docs too."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None  # no KBConfig

    with patch("app.services.indexing.feishu_indexer.FeishuConnector") as MockConnector, \
         patch("app.services.indexing.feishu_indexer.IndexManager") as MockIndexManager:

        instance = MockConnector.return_value
        instance.list_documents.return_value = []
        instance.list_wiki_documents.return_value = [
            {"token": "wiki_doc_1", "name": "Wiki Page 1", "_source": "wiki"}
        ]
        instance.get_doc_content.return_value = "Some wiki content"

        mock_index = MockIndexManager.return_value
        mock_index.update_sync_status = MagicMock()
        mock_index.index_document = AsyncMock(return_value=2)

        from app.services.indexing.feishu_indexer import FeishuIndexer
        indexer = FeishuIndexer(db=mock_db)

        result = asyncio.run(indexer.sync(org_id=1))

    instance.list_wiki_documents.assert_called_once()
    mock_index.index_document.assert_called_once()
    assert result.docs_indexed == 1
