from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.services.research.account_brief_researcher import (
    AccountBriefContext,
    AccountBriefResearcher,
)


@dataclass
class _FakeScrapeResult:
    url: str
    title: str
    content: str


def _make_connector(content: str = "scraped content") -> MagicMock:
    connector = MagicMock()
    connector.scrape_url.return_value = _FakeScrapeResult(
        url="https://example.com", title="Example", content=content
    )
    return connector


# ---------------------------------------------------------------------------
# AccountBriefContext defaults
# ---------------------------------------------------------------------------


def test_account_brief_context_defaults_to_empty_strings():
    ctx = AccountBriefContext()
    assert ctx.company_homepage == ""
    assert ctx.company_about == ""
    assert ctx.crunchbase == ""
    assert ctx.stackshare == ""
    assert ctx.job_signals == ""
    assert ctx.prospect_profile == ""


# ---------------------------------------------------------------------------
# research() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_populates_company_homepage_when_website_given():
    connector = _make_connector("homepage text")
    researcher = AccountBriefResearcher(connector)
    ctx = await researcher.research("Acme Corp", website="https://acme.com", linkedin_url=None)
    assert ctx.company_homepage == "homepage text"


@pytest.mark.asyncio
async def test_research_populates_prospect_profile_when_linkedin_url_given():
    connector = _make_connector("linkedin profile text")
    researcher = AccountBriefResearcher(connector)
    ctx = await researcher.research("Acme Corp", website=None, linkedin_url="https://linkedin.com/in/jsmith")
    assert ctx.prospect_profile == "linkedin profile text"


@pytest.mark.asyncio
async def test_research_returns_empty_prospect_profile_when_no_linkedin_url():
    connector = _make_connector("some content")
    researcher = AccountBriefResearcher(connector)
    ctx = await researcher.research("Acme Corp", website=None, linkedin_url=None)
    assert ctx.prospect_profile == ""


@pytest.mark.asyncio
async def test_research_always_attempts_crunchbase_and_stackshare():
    connector = _make_connector("data")
    researcher = AccountBriefResearcher(connector)
    await researcher.research("Acme Corp", website=None, linkedin_url=None)
    urls_scraped = [call.args[0] for call in connector.scrape_url.call_args_list]
    assert any("crunchbase.com" in u for u in urls_scraped)
    assert any("stackshare.io" in u for u in urls_scraped)


@pytest.mark.asyncio
async def test_research_always_attempts_job_signals():
    connector = _make_connector("job posting data")
    researcher = AccountBriefResearcher(connector)
    await researcher.research("Acme Corp", website=None, linkedin_url=None)
    urls_scraped = [call.args[0] for call in connector.scrape_url.call_args_list]
    assert any("Acme" in u or "acme" in u.lower() for u in urls_scraped)


# ---------------------------------------------------------------------------
# research() — failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_scrape_leaves_field_empty_and_others_succeed():
    call_count = 0

    def scrape_side_effect(url: str) -> _FakeScrapeResult:
        nonlocal call_count
        call_count += 1
        if "crunchbase" in url:
            raise RuntimeError("blocked")
        return _FakeScrapeResult(url=url, title="T", content="ok content")

    connector = MagicMock()
    connector.scrape_url.side_effect = scrape_side_effect

    researcher = AccountBriefResearcher(connector)
    ctx = await researcher.research("Acme Corp", website="https://acme.com", linkedin_url=None)

    assert ctx.crunchbase == ""
    assert ctx.company_homepage == "ok content"


# ---------------------------------------------------------------------------
# Field content capping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_is_capped_at_2000_chars():
    long_content = "x" * 5000
    connector = _make_connector(long_content)
    researcher = AccountBriefResearcher(connector)
    ctx = await researcher.research("Acme", website="https://acme.com", linkedin_url=None)
    assert len(ctx.company_homepage) <= 2000


# ---------------------------------------------------------------------------
# Slug construction
# ---------------------------------------------------------------------------


def test_slug_lowercases_and_replaces_non_alphanumeric():
    researcher = AccountBriefResearcher(MagicMock())
    assert researcher._slug("Acme Corp") == "acme-corp"
    assert researcher._slug("Foo & Bar, Inc.") == "foo-bar-inc"
    assert researcher._slug("  Leading spaces  ") == "leading-spaces"
