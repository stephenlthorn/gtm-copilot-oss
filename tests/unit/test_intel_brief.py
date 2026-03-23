import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.entities import UserPreference


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_user_preference_intel_brief_fields_have_correct_defaults(db):
    pref = UserPreference(user_email="test@example.com")
    db.add(pref)
    db.commit()
    db.refresh(pref)
    assert pref.intel_brief_enabled is True
    assert pref.intel_brief_summarizer_model == "gpt-5.4-mini"
    assert pref.intel_brief_summarizer_effort is None
    assert pref.intel_brief_synthesis_model == "gpt-5.4"
    assert pref.intel_brief_synthesis_effort == "medium"


from unittest.mock import MagicMock, patch


def test_summarize_query_results_calls_model_per_query():
    """One _responses_text call per query (skips empty snippet lists)."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()

    call_count = 0

    def fake_responses_text(system, user, model=None, tools=None, reasoning_effort=None):
        nonlocal call_count
        call_count += 1
        return f"summary for {user[:20]}"

    svc._responses_text = fake_responses_text

    query_results = [
        ("Contact background", ["snippet A", "snippet B"]),
        ("Tech stack", ["snippet C"]),
        ("Financials", []),
    ]
    results = svc._summarize_query_results(query_results, model="gpt-5.4-mini")

    assert len(results) == 3
    assert call_count == 2  # empty snippets list skipped
    assert results[2] == ("Financials", "(no results)")


def test_summarize_query_results_fallback_on_none_response():
    """When _responses_text returns None, falls back to raw joined snippets."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()
    svc._responses_text = MagicMock(return_value=None)

    query_results = [("DB signals", ["raw snippet one", "raw snippet two"])]
    results = svc._summarize_query_results(query_results, model="gpt-5.4-mini")

    assert results[0][0] == "DB signals"
    assert "raw snippet one" in results[0][1]


def test_summarize_query_results_fallback_on_exception():
    """When _responses_text raises, falls back to raw joined snippets."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()
    svc._responses_text = MagicMock(side_effect=RuntimeError("network error"))

    query_results = [("Revenue", ["revenue snippet"])]
    results = svc._summarize_query_results(query_results, model="gpt-5.4-mini")

    assert results[0][1] == "revenue snippet"


def test_summarize_query_results_all_fail():
    """When all _responses_text calls fail, all slots fall back to raw snippets."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()
    svc._responses_text = MagicMock(side_effect=RuntimeError("network error"))

    query_results = [
        ("Contact background", ["snippet A"]),
        ("Tech stack", ["snippet B"]),
        ("Financials", ["snippet C"]),
    ]
    results = svc._summarize_query_results(query_results, model="gpt-5.4-mini")

    assert len(results) == 3
    assert results[0][1] == "snippet A"
    assert results[1][1] == "snippet B"
    assert results[2][1] == "snippet C"


def test_deep_research_uses_summaries_when_enabled():
    """When intel_brief_enabled=True, synthesis uses summary paragraphs not raw snippets."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()

    svc._firecrawl_search = MagicMock(return_value=[
        {"url": "https://example.com", "title": "Title", "snippet": "raw snippet content"}
    ])
    svc._extract_company_contact = MagicMock(return_value=("Acme Corp", "Jane Doe"))

    svc._summarize_query_results = MagicMock(return_value=[
        ("Contact background", "SUMMARY: Jane Doe is a VP Engineering"),
        ("YugabyteDB competitive signal", "SUMMARY: no YugabyteDB signal found"),
        ("Other competitive DB moves", "SUMMARY: no other signals"),
        ("DB migration news", "SUMMARY: recent migration news"),
        ("Recent financials", "SUMMARY: financials"),
        ("DB tech stack — Vitess/MySQL", "SUMMARY: uses MySQL"),
        ("Engineering blog DB posts", "SUMMARY: blog posts"),
        ("Cloud provider", "SUMMARY: uses AWS"),
    ])

    synthesis_calls = []

    def fake_responses_text(system, user, model=None, tools=None, reasoning_effort=None):
        synthesis_calls.append({"model": model, "effort": reasoning_effort, "prompt": user})
        return "final brief"

    svc._responses_text = fake_responses_text

    result = svc._deep_research_pre_call(
        system_prompt="system",
        message="prepare for Jane Doe at Acme",
        model="gpt-old",
        tools=None,
        reasoning_effort="low",
        intel_brief_enabled=True,
        intel_brief_summarizer_model="gpt-5.4-mini",
        intel_brief_summarizer_effort=None,
        intel_brief_synthesis_model="gpt-5.4",
        intel_brief_synthesis_effort="medium",
    )

    assert result == "final brief"
    assert len(synthesis_calls) == 1
    assert synthesis_calls[0]["model"] == "gpt-5.4"
    assert synthesis_calls[0]["effort"] == "medium"
    assert "SUMMARY:" in synthesis_calls[0]["prompt"]
    assert "raw snippet content" not in synthesis_calls[0]["prompt"]
    svc._summarize_query_results.assert_called_once()
    call_args = svc._summarize_query_results.call_args
    assert len(call_args[0][0]) == 8


def test_deep_research_skips_summaries_when_disabled():
    """When intel_brief_enabled=False, summarizer is not called, raw snippets used."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()
    svc._firecrawl_search = MagicMock(return_value=[
        {"url": "https://example.com", "title": "Title", "snippet": "raw snippet content"}
    ])
    svc._extract_company_contact = MagicMock(return_value=("Acme Corp", "Jane Doe"))
    svc._summarize_query_results = MagicMock()

    synthesis_calls = []

    def fake_responses_text(system, user, model=None, tools=None, reasoning_effort=None):
        synthesis_calls.append({"model": model, "prompt": user})
        return "final brief"

    svc._responses_text = fake_responses_text

    result = svc._deep_research_pre_call(
        system_prompt="system",
        message="prepare for Jane Doe at Acme",
        model="gpt-old",
        tools=None,
        reasoning_effort="low",
        intel_brief_enabled=False,
        intel_brief_summarizer_model="gpt-5.4-mini",
        intel_brief_summarizer_effort=None,
        intel_brief_synthesis_model="gpt-5.4",
        intel_brief_synthesis_effort="medium",
    )

    assert result == "final brief"
    svc._summarize_query_results.assert_not_called()
    assert "raw snippet content" in synthesis_calls[0]["prompt"]
