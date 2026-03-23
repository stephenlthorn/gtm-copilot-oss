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
