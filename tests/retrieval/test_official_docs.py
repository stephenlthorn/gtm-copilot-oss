"""Tests for OfficialDocsRetriever — exercises the HTML parser and fallback."""
from unittest.mock import MagicMock, patch

from app.retrieval.official_docs import OfficialDocsRetriever, _extract_official_doc_urls, _extract_text_from_html


SAMPLE_DDG_HTML = """
<html><body>
  <div class="results">
    <div class="result">
      <a href="https://docs.example.com/product/stable/architecture" class="result__a">Product Architecture</a>
      <a href="https://docs.example.com/product/stable/overview">Overview</a>
      <a href="https://example.com/not-docs">Other</a>
    </div>
  </div>
</body></html>
"""

SAMPLE_DOC_HTML = """
<html><body>
  <main>
    <h1>Product Architecture</h1>
    <p>This is a distributed SQL database.</p>
    <p>It supports HTAP workloads.</p>
    <ul><li>Horizontal scalability</li><li>MySQL compatibility</li></ul>
  </main>
</body></html>
"""


def test_extract_official_doc_urls_only_returns_docs_links():
    urls = _extract_official_doc_urls(SAMPLE_DDG_HTML)
    assert all("docs.example.com" in u for u in urls)
    assert all("not-docs" not in u for u in urls)


def test_extract_official_doc_urls_deduplicates():
    html = SAMPLE_DDG_HTML + SAMPLE_DDG_HTML
    urls = _extract_official_doc_urls(html)
    assert len(urls) == len(set(urls))


def test_extract_text_from_html_returns_article_text():
    text = _extract_text_from_html(SAMPLE_DOC_HTML)
    assert "distributed SQL database" in text
    assert "Horizontal scalability" in text


def test_extract_text_from_html_empty_on_garbage():
    text = _extract_text_from_html("<html></html>")
    assert text == "" or len(text) < 10


def test_search_returns_empty_list_on_network_error():
    retriever = OfficialDocsRetriever()
    with patch("app.retrieval.official_docs.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = Exception("network error")
        result = retriever.search("distributed storage engine")
    assert result == []


def test_search_returns_chunks_on_success():
    retriever = OfficialDocsRetriever()

    def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "duckduckgo" in url:
            resp.text = SAMPLE_DDG_HTML
        else:
            resp.text = SAMPLE_DOC_HTML
        return resp

    with patch("app.retrieval.official_docs.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = fake_get

        chunks = retriever.search("architecture", max_results=2)

    assert len(chunks) > 0
    chunk = chunks[0]
    assert chunk.source_type == "official_docs_online"
    assert chunk.url is not None
    assert "docs.example.com" in chunk.url
    assert len(chunk.text) > 10


def test_search_skips_pages_that_return_non_200():
    retriever = OfficialDocsRetriever()

    def fake_get(url, **kwargs):
        resp = MagicMock()
        if "duckduckgo" in url:
            resp.status_code = 200
            resp.text = SAMPLE_DDG_HTML
        else:
            resp.status_code = 404
            resp.text = ""
        return resp

    with patch("app.retrieval.official_docs.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = fake_get

        chunks = retriever.search("architecture", max_results=2)

    assert chunks == []


def test_search_caps_at_max_results():
    retriever = OfficialDocsRetriever()
    many_urls_html = "\n".join(
        [f'<a href="https://docs.example.com/product/stable/page-{i}">page {i}</a>' for i in range(5)]
    )

    def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = many_urls_html if "duckduckgo" in url else SAMPLE_DOC_HTML
        return resp

    with patch("app.retrieval.official_docs.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = fake_get

        chunks = retriever.search("architecture", max_results=2)

    assert len(chunks) <= 2
