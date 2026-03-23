"""Tests for feedback loop Phase 1 implementation."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Task 1: failure_category on AIFeedback schema
# ---------------------------------------------------------------------------

def test_feedback_create_accepts_failure_category():
    """FeedbackCreate must accept and store failure_category."""
    from app.schemas.feedback import FeedbackCreate
    fc = FeedbackCreate(
        mode="oracle",
        query_text="test query",
        original_response="test response",
        rating="negative",
        failure_category="wrong_info",
    )
    assert fc.failure_category == "wrong_info"


def test_feedback_create_failure_category_defaults_none():
    """FeedbackCreate failure_category defaults to None when omitted."""
    from app.schemas.feedback import FeedbackCreate
    fc = FeedbackCreate(
        mode="oracle",
        query_text="test query",
        original_response="test response",
        rating="positive",
    )
    assert fc.failure_category is None


def test_feedback_read_exposes_failure_category():
    """FeedbackRead must include failure_category field."""
    from app.schemas.feedback import FeedbackRead
    import datetime
    fr = FeedbackRead(
        id=uuid.uuid4(),
        user_email="test@example.com",
        mode="oracle",
        rating="negative",
        correction=None,
        failure_category="too_generic",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert fr.failure_category == "too_generic"


def test_feedback_read_failure_category_nullable():
    """FeedbackRead failure_category can be None."""
    from app.schemas.feedback import FeedbackRead
    import datetime
    fr = FeedbackRead(
        id=uuid.uuid4(),
        user_email="test@example.com",
        mode="oracle",
        rating="positive",
        correction=None,
        failure_category=None,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert fr.failure_category is None


def test_invalid_failure_category_slug_dropped_to_none():
    """Invalid slug must be silently dropped to None — route must pass None to AIFeedback."""
    from app.api.routes.feedback import create_feedback
    from app.schemas.feedback import FeedbackCreate

    body = FeedbackCreate(
        mode="oracle",
        query_text="test query",
        original_response="test response",
        rating="negative",
        failure_category="not_a_valid_category",
    )
    db = MagicMock()

    with patch("app.api.routes.feedback.AIFeedback") as mock_ai_feedback, \
         patch("app.api.routes.feedback.EmbeddingService") as mock_embedding_svc:
        mock_embedding_svc.return_value.embed.return_value = None
        mock_instance = MagicMock()
        mock_ai_feedback.return_value = mock_instance

        create_feedback(body=body, x_user_email="user@example.com", db=db)

        _, kwargs = mock_ai_feedback.call_args
        assert kwargs["failure_category"] is None, (
            "Invalid failure_category slug must be dropped to None before passing to AIFeedback"
        )


def test_valid_failure_category_slug_persists():
    """Valid slug must pass through unchanged to AIFeedback."""
    from app.api.routes.feedback import create_feedback
    from app.schemas.feedback import FeedbackCreate

    valid_slugs = ["wrong_info", "missing_info", "wrong_context",
                   "outdated_info", "too_generic", "wrong_tone", "incomplete"]

    for slug in valid_slugs:
        body = FeedbackCreate(
            mode="oracle",
            query_text="test query",
            original_response="test response",
            rating="negative",
            failure_category=slug,
        )
        db = MagicMock()

        with patch("app.api.routes.feedback.AIFeedback") as mock_ai_feedback, \
             patch("app.api.routes.feedback.EmbeddingService") as mock_embedding_svc:
            mock_embedding_svc.return_value.embed.return_value = None
            mock_instance = MagicMock()
            mock_ai_feedback.return_value = mock_instance

            create_feedback(body=body, x_user_email="user@example.com", db=db)

            _, kwargs = mock_ai_feedback.call_args
            assert kwargs["failure_category"] == slug, (
                f"Valid slug '{slug}' must be passed unchanged to AIFeedback"
            )


def test_aifeedback_model_has_failure_category_column():
    """AIFeedback model must expose failure_category as a mapped attribute."""
    from app.models.feedback import AIFeedback
    mapper = AIFeedback.__mapper__
    assert "failure_category" in [c.key for c in mapper.column_attrs]


# ---------------------------------------------------------------------------
# Task 2: PromptSuggestion model
# ---------------------------------------------------------------------------

def test_prompt_suggestion_model_has_correct_tablename():
    """PromptSuggestion must use 'prompt_suggestions' table."""
    from app.models.feedback import PromptSuggestion
    assert PromptSuggestion.__tablename__ == "prompt_suggestions"


def test_prompt_suggestion_model_has_required_fields():
    """PromptSuggestion must expose all required mapped attributes."""
    from app.models.feedback import PromptSuggestion
    mapper = PromptSuggestion.__mapper__
    column_keys = [c.key for c in mapper.column_attrs]
    for field in ["id", "mode", "failure_category", "prompt_type",
                  "reasoning", "current_prompt", "suggested_prompt",
                  "applied_at", "dismissed_at", "created_at"]:
        assert field in column_keys, f"Missing field: {field}"


def test_prompt_suggestion_exported_from_models_init():
    """PromptSuggestion must be importable from app.models."""
    from app.models import PromptSuggestion
    assert PromptSuggestion is not None


def test_migration_003_upgrade_creates_prompt_suggestions_table():
    """Migration 000003 upgrade must create prompt_suggestions and add failure_category."""
    import importlib.util, sys
    from pathlib import Path
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260324_000003_add_failure_category_and_prompt_suggestions.py"
    )
    spec = importlib.util.spec_from_file_location("migration_000003", migration_path)
    migration = importlib.util.module_from_spec(spec)
    sys.modules["migration_000003"] = migration
    spec.loader.exec_module(migration)

    mock_op = MagicMock()
    mock_op.get_bind.return_value.dialect.name = "sqlite"
    migration.op = mock_op

    migration.upgrade()
    from unittest.mock import ANY
    mock_op.add_column.assert_called_once_with(
        "ai_feedback", ANY
    )
    mock_op.create_table.assert_called_once()
    call_args = mock_op.create_table.call_args
    assert call_args[0][0] == "prompt_suggestions"

    migration.downgrade()
    mock_op.drop_table.assert_called_once_with("prompt_suggestions")
    mock_op.drop_column.assert_called_once_with("ai_feedback", "failure_category")


# ---------------------------------------------------------------------------
# Task 3: GET /admin/feedback-patterns
# ---------------------------------------------------------------------------


def test_feedback_patterns_endpoint_exists():
    """GET /admin/feedback-patterns route must be registered."""
    from app.api.routes.admin import router
    route_paths = [r.path for r in router.routes]
    assert "/feedback-patterns" in route_paths


def test_feedback_patterns_groups_by_mode_and_category():
    """feedback-patterns must group negative feedback by (mode, failure_category)."""
    from app.api.routes.admin import get_feedback_patterns
    import datetime

    mock_db = MagicMock()

    agg_row = MagicMock()
    agg_row.mode = "oracle"
    agg_row.failure_category = "too_generic"
    agg_row.count = 5
    agg_row.last_seen = datetime.datetime(2026, 3, 23, 10, 0, 0, tzinfo=datetime.timezone.utc)

    examples_scalars = MagicMock()
    examples_scalars.all.return_value = ["What should I say?", "Help with Acme"]

    mock_db.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[agg_row])),
        MagicMock(scalars=MagicMock(return_value=examples_scalars)),
    ]

    result = get_feedback_patterns(days=7, db=mock_db)

    assert len(result) == 1
    assert result[0]["mode"] == "oracle"
    assert result[0]["failure_category"] == "too_generic"
    assert result[0]["count"] == 5
    assert len(result[0]["examples"]) == 2


def test_feedback_patterns_returns_empty_when_no_data():
    """feedback-patterns must return empty list when no negative feedback exists."""
    from app.api.routes.admin import get_feedback_patterns

    mock_db = MagicMock()
    mock_db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

    result = get_feedback_patterns(days=7, db=mock_db)
    assert result == []


# ---------------------------------------------------------------------------
# Task 4: GET /admin/feedback-alerts
# ---------------------------------------------------------------------------

def test_feedback_alerts_endpoint_exists():
    """GET /admin/feedback-alerts route must be registered."""
    from app.api.routes.admin import router
    route_paths = [r.path for r in router.routes]
    assert "/feedback-alerts" in route_paths


def test_feedback_alerts_returns_combo_above_threshold():
    """feedback-alerts must return combos where count >= threshold."""
    import os
    import datetime
    from app.api.routes.admin import get_feedback_alerts

    mock_db = MagicMock()

    combo = MagicMock()
    combo.mode = "oracle"
    combo.failure_category = "too_generic"

    # combos query
    # last_suggestion query: returns None (no prior suggestion)
    # count query: returns 5 (above default threshold of 3)
    mock_db.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[combo])),
        MagicMock(scalar=MagicMock(return_value=None)),
        MagicMock(scalar=MagicMock(return_value=5)),
    ]

    with patch.dict(os.environ, {"SUGGESTION_THRESHOLD": "3"}):
        result = get_feedback_alerts(db=mock_db)

    assert len(result) == 1
    assert result[0]["mode"] == "oracle"
    assert result[0]["failure_category"] == "too_generic"
    assert result[0]["count"] == 5
    assert result[0]["threshold"] == 3


def test_feedback_alerts_returns_empty_below_threshold():
    """feedback-alerts must return empty list when count < threshold."""
    import os
    from app.api.routes.admin import get_feedback_alerts

    mock_db = MagicMock()

    combo = MagicMock()
    combo.mode = "oracle"
    combo.failure_category = "too_generic"

    mock_db.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[combo])),
        MagicMock(scalar=MagicMock(return_value=None)),
        MagicMock(scalar=MagicMock(return_value=2)),  # below threshold
    ]

    with patch.dict(os.environ, {"SUGGESTION_THRESHOLD": "3"}):
        result = get_feedback_alerts(db=mock_db)

    assert result == []


def test_feedback_alerts_resets_window_from_last_suggestion():
    """feedback-alerts count window starts from last PromptSuggestion.created_at."""
    import os
    import datetime
    from app.api.routes.admin import get_feedback_alerts

    mock_db = MagicMock()

    combo = MagicMock()
    combo.mode = "rep"
    combo.failure_category = "wrong_tone"

    recent_suggestion_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=12)

    mock_db.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[combo])),
        MagicMock(scalar=MagicMock(return_value=recent_suggestion_time)),
        MagicMock(scalar=MagicMock(return_value=4)),
    ]

    with patch.dict(os.environ, {"SUGGESTION_THRESHOLD": "3"}):
        result = get_feedback_alerts(db=mock_db)

    assert len(result) == 1
    assert result[0]["mode"] == "rep"
