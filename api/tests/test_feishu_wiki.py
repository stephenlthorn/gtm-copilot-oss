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
