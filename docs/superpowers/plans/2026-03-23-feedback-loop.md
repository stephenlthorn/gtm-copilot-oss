# Feedback Loop Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a comprehensive feedback loop that captures failure categories on thumbs-down, aggregates patterns, auto-triggers GPT-4 prompt suggestions when thresholds are crossed, and surfaces everything in a dedicated /admin/feedback dashboard.

**Architecture:** Four layers — extended data capture (model + schema + UI chip picker), a PromptSuggestion table, five admin API endpoints, and a Next.js dashboard page with inline diff suggestion panel. All analysis runs at request time (no background jobs) for Vercel Pro compatibility.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, FastAPI, OpenAI GPT-4o, Next.js 14 (App Router), TiDB Cloud

---

## Task 1: `failure_category` on AIFeedback + migration scaffold

**Files changed:**
- `api/app/models/feedback.py`
- `api/app/schemas/feedback.py`
- `api/app/api/routes/feedback.py`
- `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py` (scaffold)
- `api/tests/unit/test_feedback_loop.py` (new)

### Steps

- [ ] **1.1** Modify `api/app/models/feedback.py` — add `failure_category` after `correction` in `AIFeedback`:

  ```python
  failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
  ```

- [ ] **1.2** Modify `api/app/schemas/feedback.py` — add `failure_category` to both schemas:

  In `FeedbackCreate`:
  ```python
  failure_category: str | None = None
  ```

  In `FeedbackRead`:
  ```python
  failure_category: str | None = None
  ```

- [ ] **1.3** Modify `api/app/api/routes/feedback.py` — add slug validation constant and pass `failure_category` to the `AIFeedback` constructor. Insert after the existing imports:

  ```python
  VALID_CATEGORIES = {
      "wrong_info", "missing_info", "wrong_context",
      "outdated_info", "too_generic", "wrong_tone", "incomplete",
  }
  ```

  In `create_feedback`, before constructing the `AIFeedback` object:

  ```python
  category = body.failure_category if body.failure_category in VALID_CATEGORIES else None
  ```

  Add `failure_category=category` to the `AIFeedback(...)` constructor call.

- [ ] **1.4** Create migration scaffold `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py`:

  ```python
  """Add failure_category to ai_feedback and create prompt_suggestions table.

  Revision ID: 20260324_000003
  Revises: 20260324_000002
  """

  from __future__ import annotations

  import sqlalchemy as sa
  from alembic import op

  revision = "20260324_000003"
  down_revision = "20260324_000002"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      bind = op.get_bind()
      dialect = bind.dialect.name
      if dialect == "mysql":
          uuid_col = sa.BINARY(16)
      else:
          uuid_col = sa.Text()

      op.add_column(
          "ai_feedback",
          sa.Column("failure_category", sa.String(64), nullable=True),
      )

      # prompt_suggestions table added in Task 2 after model exists


  def downgrade() -> None:
      # prompt_suggestions drop added in Task 2
      op.drop_column("ai_feedback", "failure_category")
  ```

  > Note: The `prompt_suggestions` table DDL is intentionally incomplete here. Task 2 completes both `upgrade()` and `downgrade()` after the model is defined.

- [ ] **1.5** Create `api/tests/unit/test_feedback_loop.py` with Task 1 tests:

  ```python
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
      """Invalid slug must be silently dropped to None in create_feedback."""
      from app.api.routes.feedback import VALID_CATEGORIES
      invalid_slug = "not_a_valid_category"
      category = invalid_slug if invalid_slug in VALID_CATEGORIES else None
      assert category is None


  def test_valid_failure_category_slug_persists():
      """Valid slug must pass through unchanged."""
      from app.api.routes.feedback import VALID_CATEGORIES
      for slug in ["wrong_info", "missing_info", "wrong_context",
                   "outdated_info", "too_generic", "wrong_tone", "incomplete"]:
          result = slug if slug in VALID_CATEGORIES else None
          assert result == slug, f"Expected {slug} to be valid"


  def test_aifeedback_model_has_failure_category_column():
      """AIFeedback model must expose failure_category as a mapped attribute."""
      from app.models.feedback import AIFeedback
      mapper = AIFeedback.__mapper__
      assert "failure_category" in [c.key for c in mapper.column_attrs]
  ```

- [ ] **1.6** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py::test_feedback_create_accepts_failure_category tests/unit/test_feedback_loop.py::test_feedback_read_exposes_failure_category tests/unit/test_feedback_loop.py::test_invalid_failure_category_slug_dropped_to_none tests/unit/test_feedback_loop.py::test_aifeedback_model_has_failure_category_column -v
  ```

- [ ] **1.7** Commit:

  ```bash
  git add api/app/models/feedback.py api/app/schemas/feedback.py api/app/api/routes/feedback.py api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add failure_category to AIFeedback model, schema, and route"
  ```

---

## Task 2: `PromptSuggestion` model + complete migration

**Files changed:**
- `api/app/models/feedback.py`
- `api/app/models/__init__.py`
- `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py`
- `api/tests/unit/test_feedback_loop.py`

### Steps

- [ ] **2.1** Modify `api/app/models/feedback.py` — append `PromptSuggestion` class after `ChunkQualitySignal`:

  ```python
  class PromptSuggestion(Base):
      __tablename__ = "prompt_suggestions"
      __table_args__ = (
          Index("ix_prompt_suggestions_mode_category", "mode", "failure_category"),
      )

      id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
      mode: Mapped[str] = mapped_column(String(64), nullable=False)
      failure_category: Mapped[str] = mapped_column(String(64), nullable=False)
      prompt_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "persona" | "builtin"
      reasoning: Mapped[str] = mapped_column(Text, nullable=False)
      current_prompt: Mapped[str] = mapped_column(Text, nullable=False)
      suggested_prompt: Mapped[str] = mapped_column(Text, nullable=False)
      applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
      dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
  ```

- [ ] **2.2** Modify `api/app/models/__init__.py` — add `PromptSuggestion` import and export:

  Change the `from app.models.feedback import ...` line to:
  ```python
  from app.models.feedback import AIFeedback, ChunkQualitySignal, PromptSuggestion
  ```

  Add `"PromptSuggestion"` to the `__all__` list.

- [ ] **2.3** Complete the migration `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py` — replace the `upgrade()` and `downgrade()` bodies:

  ```python
  def upgrade() -> None:
      bind = op.get_bind()
      dialect = bind.dialect.name
      if dialect == "mysql":
          uuid_col = sa.BINARY(16)
      else:
          uuid_col = sa.Text()

      op.add_column(
          "ai_feedback",
          sa.Column("failure_category", sa.String(64), nullable=True),
      )

      op.create_table(
          "prompt_suggestions",
          sa.Column("id", uuid_col, primary_key=True),
          sa.Column("mode", sa.String(64), nullable=False),
          sa.Column("failure_category", sa.String(64), nullable=False),
          sa.Column("prompt_type", sa.String(16), nullable=False),
          sa.Column("reasoning", sa.Text, nullable=False),
          sa.Column("current_prompt", sa.Text, nullable=False),
          sa.Column("suggested_prompt", sa.Text, nullable=False),
          sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
      )
      op.create_index(
          "ix_prompt_suggestions_mode_category",
          "prompt_suggestions",
          ["mode", "failure_category"],
      )


  def downgrade() -> None:
      op.drop_index("ix_prompt_suggestions_mode_category", table_name="prompt_suggestions")
      op.drop_table("prompt_suggestions")
      op.drop_column("ai_feedback", "failure_category")
  ```

- [ ] **2.4** Append Task 2 tests to `api/tests/unit/test_feedback_loop.py`:

  ```python
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
      mock_op.add_column.assert_called_once_with(
          "ai_feedback", MagicMock()
      )
      mock_op.create_table.assert_called_once()
      call_args = mock_op.create_table.call_args
      assert call_args[0][0] == "prompt_suggestions"

      migration.downgrade()
      mock_op.drop_table.assert_called_once_with("prompt_suggestions")
      mock_op.drop_column.assert_called_once_with("ai_feedback", "failure_category")
  ```

- [ ] **2.5** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -k "task2 or prompt_suggestion or migration_003" -v
  ```

  Actually run all Task 1+2 tests together:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

- [ ] **2.6** Commit:

  ```bash
  git add api/app/models/feedback.py api/app/models/__init__.py api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add PromptSuggestion model and complete migration 000003"
  ```

---

## Task 3: `GET /admin/feedback-patterns` endpoint

**Files changed:**
- `api/app/api/routes/admin.py`
- `api/tests/unit/test_feedback_loop.py`

### Steps

- [ ] **3.1** Modify `api/app/api/routes/admin.py` — add required imports at the top of the file (alongside existing imports):

  ```python
  import os
  import uuid
  from datetime import datetime, timedelta, timezone
  ```

  `func` and `select` are already imported from `sqlalchemy` in `admin.py` — do not re-import or alias them. The implementation below uses `func` directly (same name as the existing import).

  Also add to the existing model imports:
  ```python
  from app.models.feedback import AIFeedback, PromptSuggestion
  ```

- [ ] **3.2** Add the endpoint to `api/app/api/routes/admin.py`:

  ```python
  @router.get("/feedback-patterns")
  def get_feedback_patterns(
      days: int = Query(default=7, ge=1, le=90),
      db: Session = Depends(db_session),
  ):
      """Aggregate negative feedback by (mode, failure_category) for the last N days."""
      cutoff = datetime.now(timezone.utc) - timedelta(days=days)

      # Subquery: get 2 most recent query_text examples per (mode, failure_category)
      rows = db.execute(
          select(
              AIFeedback.mode,
              AIFeedback.failure_category,
              func.count(AIFeedback.id).label("count"),
              func.max(AIFeedback.created_at).label("last_seen"),
          )
          .where(AIFeedback.rating == "negative")
          .where(AIFeedback.failure_category.isnot(None))
          .where(AIFeedback.created_at >= cutoff)
          .group_by(AIFeedback.mode, AIFeedback.failure_category)
          .order_by(func.count(AIFeedback.id).desc())
          .limit(20)
      ).all()

      result = []
      for row in rows:
          # Fetch 2 most recent example query_text values
          examples_rows = db.execute(
              select(AIFeedback.query_text)
              .where(AIFeedback.rating == "negative")
              .where(AIFeedback.failure_category == row.failure_category)
              .where(AIFeedback.mode == row.mode)
              .where(AIFeedback.created_at >= cutoff)
              .order_by(AIFeedback.created_at.desc())
              .limit(2)
          ).scalars().all()

          result.append({
              "mode": row.mode,
              "failure_category": row.failure_category,
              "count": row.count,
              "last_seen": row.last_seen.isoformat() if row.last_seen else None,
              "examples": list(examples_rows),
          })

      return result
  ```

- [ ] **3.3** Append Task 3 tests to `api/tests/unit/test_feedback_loop.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Task 3: GET /admin/feedback-patterns
  # ---------------------------------------------------------------------------

  def _make_db_feedback_row(mode="oracle", failure_category="too_generic",
                             rating="negative", query_text="test query",
                             days_ago=1):
      """Helper: create a MagicMock row mimicking AIFeedback query result."""
      import datetime
      row = MagicMock()
      row.mode = mode
      row.failure_category = failure_category
      row.rating = rating
      row.query_text = query_text
      row.count = 3
      row.last_seen = datetime.datetime.now(datetime.timezone.utc)
      return row


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

      # Simulate .execute().all() for the aggregation query
      agg_row = MagicMock()
      agg_row.mode = "oracle"
      agg_row.failure_category = "too_generic"
      agg_row.count = 5
      agg_row.last_seen = datetime.datetime(2026, 3, 23, 10, 0, 0, tzinfo=datetime.timezone.utc)

      # First execute call: aggregation; second execute call: examples
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
  ```

- [ ] **3.4** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

- [ ] **3.5** Commit:

  ```bash
  git add api/app/api/routes/admin.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add GET /admin/feedback-patterns endpoint"
  ```

---

## Task 4: `GET /admin/feedback-alerts` endpoint

**Files changed:**
- `api/app/api/routes/admin.py`
- `api/tests/unit/test_feedback_loop.py`

### Steps

- [ ] **4.1** Add the endpoint to `api/app/api/routes/admin.py`:

  ```python
  SUGGESTION_THRESHOLD_DEFAULT = 3


  @router.get("/feedback-alerts")
  def get_feedback_alerts(db: Session = Depends(db_session)):
      """Return (mode, failure_category) combos where failure count >= threshold since last suggestion."""
      threshold = int(os.environ.get("SUGGESTION_THRESHOLD", SUGGESTION_THRESHOLD_DEFAULT))
      window_floor = datetime.now(timezone.utc) - timedelta(days=7)

      # All distinct (mode, failure_category) combos with any negative feedback
      combos = db.execute(
          select(AIFeedback.mode, AIFeedback.failure_category)
          .where(AIFeedback.rating == "negative")
          .where(AIFeedback.failure_category.isnot(None))
          .distinct()
      ).all()

      alerts = []
      for combo in combos:
          mode, category = combo.mode, combo.failure_category

          # Find most recent PromptSuggestion for this combo
          last_suggestion = db.execute(
              select(func.max(PromptSuggestion.created_at))
              .where(PromptSuggestion.mode == mode)
              .where(PromptSuggestion.failure_category == category)
          ).scalar()

          # Count failures since max(last_suggestion.created_at, now()-7days)
          since = max(last_suggestion, window_floor) if last_suggestion else window_floor

          count = db.execute(
              select(func.count(AIFeedback.id))
              .where(AIFeedback.rating == "negative")
              .where(AIFeedback.failure_category == category)
              .where(AIFeedback.mode == mode)
              .where(AIFeedback.created_at >= since)
          ).scalar()

          if count >= threshold:
              alerts.append({
                  "mode": mode,
                  "failure_category": category,
                  "count": count,
                  "threshold": threshold,
              })

      return alerts
  ```

- [ ] **4.2** Append Task 4 tests to `api/tests/unit/test_feedback_loop.py`:

  ```python
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
  ```

  Add `from unittest.mock import patch` to the top of the test file if not already present.

- [ ] **4.3** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

- [ ] **4.4** Commit:

  ```bash
  git add api/app/api/routes/admin.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add GET /admin/feedback-alerts endpoint with threshold logic"
  ```

---

## Task 5: `POST /admin/feedback-suggestions` endpoint (GPT-4 suggestion generation)

**Files changed:**
- `api/app/api/routes/admin.py`
- `api/tests/unit/test_feedback_loop.py`

### Steps

- [ ] **5.1** Add mode-to-prompt mapping and the endpoint to `api/app/api/routes/admin.py`.

  Add to imports section:
  ```python
  from openai import OpenAI
  from pydantic import BaseModel as PydanticBaseModel

  from app.prompts.templates import (
      SYSTEM_ORACLE,
      SYSTEM_CALL_COACH,
      SYSTEM_REP_EXECUTION,
      SYSTEM_SE_EXECUTION,
      SYSTEM_MARKETING_EXECUTION,
  )
  ```

  Add constant and schema after existing constants:
  ```python
  BUILTIN_PROMPT_MAP = {
      "oracle": SYSTEM_ORACLE,
      "call_assistant": SYSTEM_CALL_COACH,
      "rep": SYSTEM_REP_EXECUTION,
      "se": SYSTEM_SE_EXECUTION,
      "marketing": SYSTEM_MARKETING_EXECUTION,
  }


  class FeedbackSuggestionRequest(PydanticBaseModel):
      mode: str
      failure_category: str
      prompt_type: str  # "persona" | "builtin"
  ```

  Add endpoint:
  ```python
  @router.post("/feedback-suggestions")
  def create_feedback_suggestion(
      body: FeedbackSuggestionRequest,
      request: Request,
      db: Session = Depends(db_session),
  ):
      """Generate a GPT-4 prompt suggestion for a (mode, failure_category) pattern."""
      # 1. Load 5 most recent failing queries
      examples = db.execute(
          select(AIFeedback.query_text, AIFeedback.original_response)
          .where(AIFeedback.rating == "negative")
          .where(AIFeedback.failure_category == body.failure_category)
          .where(AIFeedback.mode == body.mode)
          .order_by(AIFeedback.created_at.desc())
          .limit(5)
      ).all()

      if not examples:
          raise HTTPException(status_code=404, detail="No failures found for this mode/category")

      # 2. Load current prompt
      if body.prompt_type == "persona":
          kb_config = db.execute(select(KBConfig)).scalar_one_or_none()
          current_prompt = (kb_config.persona_prompt if kb_config else None) or ""
          if not current_prompt:
              raise HTTPException(status_code=404, detail="No persona prompt configured")
      elif body.prompt_type == "builtin":
          current_prompt = BUILTIN_PROMPT_MAP.get(body.mode)
          if not current_prompt:
              raise HTTPException(status_code=400, detail=f"No built-in prompt for mode: {body.mode}")
      else:
          raise HTTPException(status_code=422, detail="prompt_type must be 'persona' or 'builtin'")

      # 3. Build GPT-4o prompt
      formatted_examples = "\n\n".join(
          f"Query: {ex.query_text}\nResponse: {ex.original_response}"
          for ex in examples
      )
      system = "You are a prompt engineering assistant. Analyze failure patterns and suggest precise edits to improve an AI system prompt."
      user = f"""Mode: {body.mode}
  Failure category: {body.failure_category}
  Threshold: {len(examples)} users flagged this as '{body.failure_category}'

  Recent failing queries and responses:
  {formatted_examples}

  Current {body.prompt_type} prompt:
  {current_prompt}

  Suggest a specific edit to reduce '{body.failure_category}' failures. Return JSON: {{"reasoning": "2-3 sentence explanation", "suggested_prompt": "full revised prompt text"}}"""

      # 4. Call GPT-4o
      settings = get_settings()
      token = request.headers.get("X-OpenAI-Token") or settings.openai_api_key
      try:
          client = OpenAI(api_key=token)
          response = client.chat.completions.create(
              model="gpt-4o",
              messages=[
                  {"role": "system", "content": system},
                  {"role": "user", "content": user},
              ],
              response_format={"type": "json_object"},
              temperature=0.3,
          )
          raw = response.choices[0].message.content
          import json
          parsed = json.loads(raw)
          reasoning = parsed["reasoning"]
          suggested_prompt = parsed["suggested_prompt"]
      except Exception as exc:
          raise HTTPException(status_code=502, detail=f"GPT-4 call failed: {exc}")

      # 5. Save PromptSuggestion row
      suggestion = PromptSuggestion(
          mode=body.mode,
          failure_category=body.failure_category,
          prompt_type=body.prompt_type,
          reasoning=reasoning,
          current_prompt=current_prompt,
          suggested_prompt=suggested_prompt,
      )
      db.add(suggestion)
      db.commit()
      db.refresh(suggestion)

      return {
          "id": str(suggestion.id),
          "mode": suggestion.mode,
          "failure_category": suggestion.failure_category,
          "prompt_type": suggestion.prompt_type,
          "reasoning": suggestion.reasoning,
          "current_prompt": suggestion.current_prompt,
          "suggested_prompt": suggestion.suggested_prompt,
          "applied_at": suggestion.applied_at,
          "dismissed_at": suggestion.dismissed_at,
          "created_at": suggestion.created_at.isoformat(),
      }
  ```

- [ ] **5.2** Append Task 5 tests to `api/tests/unit/test_feedback_loop.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Task 5: POST /admin/feedback-suggestions
  # ---------------------------------------------------------------------------

  def test_feedback_suggestions_endpoint_exists():
      """POST /admin/feedback-suggestions route must be registered."""
      from app.api.routes.admin import router
      route_paths = [r.path for r in router.routes]
      assert "/feedback-suggestions" in route_paths


  def test_feedback_suggestions_calls_gpt4_and_saves_row():
      """create_feedback_suggestion must call OpenAI and save PromptSuggestion to DB."""
      import json
      from app.api.routes.admin import create_feedback_suggestion, FeedbackSuggestionRequest

      mock_db = MagicMock()

      # Simulate 2 example failures
      ex1 = MagicMock()
      ex1.query_text = "What should I say on the Acme call?"
      ex1.original_response = "Here is some generic advice..."
      ex2 = MagicMock()
      ex2.query_text = "How do I position against Snowflake?"
      ex2.original_response = "You should consider..."

      # kb_config for persona prompt
      mock_kb = MagicMock()
      mock_kb.persona_prompt = "You are a helpful sales assistant."

      mock_db.execute.side_effect = [
          MagicMock(all=MagicMock(return_value=[ex1, ex2])),
          MagicMock(scalar_one_or_none=MagicMock(return_value=mock_kb)),
      ]

      suggestion_row = MagicMock()
      suggestion_row.id = uuid.uuid4()
      suggestion_row.mode = "oracle"
      suggestion_row.failure_category = "too_generic"
      suggestion_row.prompt_type = "persona"
      suggestion_row.reasoning = "The prompt is too vague."
      suggestion_row.current_prompt = "You are a helpful sales assistant."
      suggestion_row.suggested_prompt = "You are a highly specific sales assistant..."
      suggestion_row.applied_at = None
      suggestion_row.dismissed_at = None
      import datetime
      suggestion_row.created_at = datetime.datetime.now(datetime.timezone.utc)

      mock_db.refresh.side_effect = lambda obj: None

      gpt_response_content = json.dumps({
          "reasoning": "The prompt lacks specificity about account context.",
          "suggested_prompt": "You are a highly specific sales assistant...",
      })

      mock_request = MagicMock()
      mock_request.headers.get.return_value = "test-token"

      body = FeedbackSuggestionRequest(
          mode="oracle",
          failure_category="too_generic",
          prompt_type="persona",
      )

      mock_completion = MagicMock()
      mock_completion.choices[0].message.content = gpt_response_content

      with patch("app.api.routes.admin.OpenAI") as mock_openai_cls:
          mock_client = MagicMock()
          mock_openai_cls.return_value = mock_client
          mock_client.chat.completions.create.return_value = mock_completion

          # Patch db.add to capture the PromptSuggestion object
          added_objects = []
          mock_db.add.side_effect = lambda obj: added_objects.append(obj)

          # We need refresh to set fields on the added object
          def mock_refresh(obj):
              obj.id = uuid.uuid4()
              import datetime
              obj.created_at = datetime.datetime.now(datetime.timezone.utc)

          mock_db.refresh.side_effect = mock_refresh

          result = create_feedback_suggestion(body=body, request=mock_request, db=mock_db)

      # Verify OpenAI was called
      mock_client.chat.completions.create.assert_called_once()
      call_kwargs = mock_client.chat.completions.create.call_args[1]
      assert call_kwargs["model"] == "gpt-4o"

      # Verify PromptSuggestion was added to DB
      mock_db.add.assert_called_once()
      mock_db.commit.assert_called()

      added = added_objects[0]
      assert added.mode == "oracle"
      assert added.failure_category == "too_generic"
      assert added.prompt_type == "persona"
      assert added.reasoning == "The prompt lacks specificity about account context."


  def test_feedback_suggestions_returns_502_on_openai_failure():
      """create_feedback_suggestion must return 502 when GPT-4 call raises."""
      from fastapi import HTTPException
      from app.api.routes.admin import create_feedback_suggestion, FeedbackSuggestionRequest

      mock_db = MagicMock()

      ex1 = MagicMock()
      ex1.query_text = "test"
      ex1.original_response = "test"

      mock_kb = MagicMock()
      mock_kb.persona_prompt = "You are a sales assistant."

      mock_db.execute.side_effect = [
          MagicMock(all=MagicMock(return_value=[ex1])),
          MagicMock(scalar_one_or_none=MagicMock(return_value=mock_kb)),
      ]

      mock_request = MagicMock()
      mock_request.headers.get.return_value = "test-token"

      body = FeedbackSuggestionRequest(
          mode="oracle",
          failure_category="too_generic",
          prompt_type="persona",
      )

      with patch("app.api.routes.admin.OpenAI") as mock_openai_cls:
          mock_client = MagicMock()
          mock_openai_cls.return_value = mock_client
          mock_client.chat.completions.create.side_effect = Exception("API error")

          import pytest
          with pytest.raises(HTTPException) as exc_info:
              create_feedback_suggestion(body=body, request=mock_request, db=mock_db)

      assert exc_info.value.status_code == 502
      # Verify no row was committed on failure
      mock_db.commit.assert_not_called()
  ```

- [ ] **5.3** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

- [ ] **5.4** Commit:

  ```bash
  git add api/app/api/routes/admin.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add POST /admin/feedback-suggestions endpoint with GPT-4o integration"
  ```

---

## Task 6: `POST /admin/feedback-suggestions/{id}/apply` and `/{id}/dismiss`

**Files changed:**
- `api/app/api/routes/admin.py`
- `api/tests/unit/test_feedback_loop.py`

### Steps

- [ ] **6.1** Add both endpoints to `api/app/api/routes/admin.py`:

  ```python
  @router.post("/feedback-suggestions/{id}/apply")
  def apply_feedback_suggestion(
      id: uuid.UUID,
      db: Session = Depends(db_session),
  ):
      """Apply a suggestion to the persona prompt (builtin suggestions return 400)."""
      suggestion = db.get(PromptSuggestion, id)
      if suggestion is None:
          raise HTTPException(status_code=404, detail="Suggestion not found")

      if suggestion.prompt_type == "builtin":
          raise HTTPException(
              status_code=400,
              detail="Built-in prompts require a code change and cannot be applied via API",
          )

      # Update KBConfig.persona_prompt
      kb_config = db.execute(select(KBConfig)).scalar_one_or_none()
      if kb_config is None:
          raise HTTPException(status_code=404, detail="KBConfig not found")

      kb_config.persona_prompt = suggestion.suggested_prompt
      suggestion.applied_at = datetime.now(timezone.utc)
      db.commit()
      db.refresh(suggestion)

      return {
          "id": str(suggestion.id),
          "mode": suggestion.mode,
          "failure_category": suggestion.failure_category,
          "prompt_type": suggestion.prompt_type,
          "reasoning": suggestion.reasoning,
          "current_prompt": suggestion.current_prompt,
          "suggested_prompt": suggestion.suggested_prompt,
          "applied_at": suggestion.applied_at.isoformat() if suggestion.applied_at else None,
          "dismissed_at": suggestion.dismissed_at,
          "created_at": suggestion.created_at.isoformat(),
      }


  @router.post("/feedback-suggestions/{id}/dismiss")
  def dismiss_feedback_suggestion(
      id: uuid.UUID,
      db: Session = Depends(db_session),
  ):
      """Dismiss a suggestion (resets the threshold counter via created_at anchor)."""
      suggestion = db.get(PromptSuggestion, id)
      if suggestion is None:
          raise HTTPException(status_code=404, detail="Suggestion not found")

      suggestion.dismissed_at = datetime.now(timezone.utc)
      db.commit()

      return {"status": "dismissed", "id": str(suggestion.id)}
  ```

- [ ] **6.2** Append Task 6 tests to `api/tests/unit/test_feedback_loop.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Task 6: apply and dismiss endpoints
  # ---------------------------------------------------------------------------

  def _make_suggestion(prompt_type="persona"):
      """Helper: create a MagicMock PromptSuggestion."""
      import datetime
      s = MagicMock()
      s.id = uuid.uuid4()
      s.mode = "oracle"
      s.failure_category = "too_generic"
      s.prompt_type = prompt_type
      s.reasoning = "The prompt is too vague."
      s.current_prompt = "You are a sales assistant."
      s.suggested_prompt = "You are a highly specific sales assistant."
      s.applied_at = None
      s.dismissed_at = None
      s.created_at = datetime.datetime.now(datetime.timezone.utc)
      return s


  def test_apply_suggestion_updates_kb_config():
      """apply endpoint must update KBConfig.persona_prompt and set applied_at."""
      from app.api.routes.admin import apply_feedback_suggestion

      suggestion = _make_suggestion(prompt_type="persona")
      mock_kb = MagicMock()
      mock_db = MagicMock()
      mock_db.get.return_value = suggestion
      mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_kb))
      mock_db.refresh.side_effect = lambda obj: None

      result = apply_feedback_suggestion(id=suggestion.id, db=mock_db)

      assert mock_kb.persona_prompt == suggestion.suggested_prompt
      assert suggestion.applied_at is not None
      mock_db.commit.assert_called_once()


  def test_apply_suggestion_returns_400_for_builtin():
      """apply endpoint must return 400 when prompt_type is 'builtin'."""
      from fastapi import HTTPException
      from app.api.routes.admin import apply_feedback_suggestion
      import pytest

      suggestion = _make_suggestion(prompt_type="builtin")
      mock_db = MagicMock()
      mock_db.get.return_value = suggestion

      with pytest.raises(HTTPException) as exc_info:
          apply_feedback_suggestion(id=suggestion.id, db=mock_db)

      assert exc_info.value.status_code == 400


  def test_apply_suggestion_returns_404_when_not_found():
      """apply endpoint must return 404 when suggestion does not exist."""
      from fastapi import HTTPException
      from app.api.routes.admin import apply_feedback_suggestion
      import pytest

      mock_db = MagicMock()
      mock_db.get.return_value = None

      with pytest.raises(HTTPException) as exc_info:
          apply_feedback_suggestion(id=uuid.uuid4(), db=mock_db)

      assert exc_info.value.status_code == 404


  def test_dismiss_suggestion_sets_dismissed_at():
      """dismiss endpoint must set dismissed_at and commit."""
      from app.api.routes.admin import dismiss_feedback_suggestion

      suggestion = _make_suggestion()
      mock_db = MagicMock()
      mock_db.get.return_value = suggestion

      result = dismiss_feedback_suggestion(id=suggestion.id, db=mock_db)

      assert suggestion.dismissed_at is not None
      mock_db.commit.assert_called_once()
      assert result["status"] == "dismissed"


  def test_dismiss_suggestion_returns_404_when_not_found():
      """dismiss endpoint must return 404 when suggestion does not exist."""
      from fastapi import HTTPException
      from app.api.routes.admin import dismiss_feedback_suggestion
      import pytest

      mock_db = MagicMock()
      mock_db.get.return_value = None

      with pytest.raises(HTTPException) as exc_info:
          dismiss_feedback_suggestion(id=uuid.uuid4(), db=mock_db)

      assert exc_info.value.status_code == 404
  ```

- [ ] **6.3** Run tests:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

- [ ] **6.4** Commit:

  ```bash
  git add api/app/api/routes/admin.py api/tests/unit/test_feedback_loop.py
  git commit -m "feat: add apply and dismiss endpoints for feedback suggestions"
  ```

---

## Task 7: FeedbackButtons.js — category chip picker

**Files changed:**
- `ui/components/FeedbackButtons.js`

### Steps

- [ ] **7.1** Replace `ui/components/FeedbackButtons.js` with the following complete implementation:

  ```js
  'use client';
  import { useState } from 'react';

  const FAILURE_CATEGORIES = [
    { slug: 'wrong_info',    label: '❌ Factually wrong' },
    { slug: 'missing_info',  label: '🔍 Missing info' },
    { slug: 'wrong_context', label: '❌ Wrong context' },
    { slug: 'outdated_info', label: '📅 Outdated info' },
    { slug: 'too_generic',   label: '🎯 Too generic' },
    { slug: 'wrong_tone',    label: '📝 Wrong tone' },
    { slug: 'incomplete',    label: '✂️ Incomplete' },
  ];

  export default function FeedbackButtons({ message, query, mode = 'oracle' }) {
    const [rating, setRating] = useState(null); // 'positive' | 'negative' | null
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [correction, setCorrection] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    const submit = async (r, correctionText = '', category = null) => {
      setSubmitting(true);
      try {
        await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode,
            query_text: query,
            original_response: message,
            rating: r,
            correction: correctionText || null,
            failure_category: category || null,
          }),
        });
        setRating(r);
        setSubmitted(true);
      } catch { /* silent */ }
      finally { setSubmitting(false); }
    };

    if (submitted) {
      return <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>✓ feedback saved</span>;
    }

    return (
      <div style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
          <button
            onClick={() => submit('positive')}
            disabled={submitting}
            title="Good response"
            style={{ fontSize: '0.72rem', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: '0.1rem 0.25rem', borderRadius: '3px' }}
          >👍</button>
          <button
            onClick={() => {
              setRating(rating === 'negative' ? null : 'negative');
              setSelectedCategory(null);
            }}
            disabled={submitting}
            title="Needs improvement"
            style={{ fontSize: '0.72rem', background: 'transparent', border: 'none', cursor: 'pointer', color: rating === 'negative' ? 'var(--danger)' : 'var(--text-3)', padding: '0.1rem 0.25rem', borderRadius: '3px' }}
          >👎</button>
        </div>

        {rating === 'negative' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {/* Category chip picker */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
              {FAILURE_CATEGORIES.map(({ slug, label }) => (
                <button
                  key={slug}
                  onClick={() => setSelectedCategory(selectedCategory === slug ? null : slug)}
                  style={{
                    fontSize: '0.68rem',
                    padding: '0.2rem 0.45rem',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    border: selectedCategory === slug
                      ? '1.5px solid var(--accent, #4f8ef7)'
                      : '1px solid var(--border)',
                    background: selectedCategory === slug
                      ? 'var(--accent-bg, rgba(79,142,247,0.1))'
                      : 'var(--bg-2)',
                    color: selectedCategory === slug
                      ? 'var(--accent, #4f8ef7)'
                      : 'var(--text-2)',
                    fontWeight: selectedCategory === slug ? '600' : '400',
                    transition: 'all 0.12s ease',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Correction textarea + submit */}
            <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'flex-start' }}>
              <textarea
                placeholder="What should the correct answer have been? (optional)"
                value={correction}
                onChange={e => setCorrection(e.target.value)}
                rows={2}
                style={{ flex: 1, fontSize: '0.72rem', padding: '0.3rem 0.5rem', border: '1px solid var(--border)', borderRadius: '4px', background: 'var(--bg)', color: 'var(--text)', resize: 'vertical', fontFamily: 'var(--font)' }}
              />
              <button
                onClick={() => submit('negative', correction, selectedCategory)}
                disabled={submitting || !selectedCategory}
                className="btn btn-primary"
                style={{ fontSize: '0.72rem', padding: '0.25rem 0.55rem', alignSelf: 'flex-end', opacity: selectedCategory ? 1 : 0.45 }}
              >
                {submitting ? '…' : 'Submit'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **7.2** Commit:

  ```bash
  git add ui/components/FeedbackButtons.js
  git commit -m "feat: add failure category chip picker to FeedbackButtons thumbs-down flow"
  ```

---

## Task 8: Next.js admin proxy routes (5 routes)

**Files to create:**
- `ui/app/api/admin/feedback-patterns/route.js`
- `ui/app/api/admin/feedback-suggestions/route.js`
- `ui/app/api/admin/feedback-suggestions/[id]/apply/route.js`
- `ui/app/api/admin/feedback-suggestions/[id]/dismiss/route.js`
- `ui/app/api/admin/feedback-alerts/route.js`

All use the `X-OpenAI-Token: session.access_token` pattern from `ui/app/api/admin/kb-config/route.js`.

### Steps

- [ ] **8.1** Create `ui/app/api/admin/feedback-patterns/route.js`:

  ```js
  import { getSession } from '@/lib/session';

  const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

  export async function GET(request) {
    const session = await getSession();
    const { searchParams } = new URL(request.url);
    const days = searchParams.get('days') || '7';
    const res = await fetch(`${API_BASE}/admin/feedback-patterns?days=${days}`, {
      headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }
  ```

- [ ] **8.2** Create `ui/app/api/admin/feedback-alerts/route.js`:

  ```js
  import { getSession } from '@/lib/session';

  const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

  export async function GET() {
    const session = await getSession();
    const res = await fetch(`${API_BASE}/admin/feedback-alerts`, {
      headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }
  ```

- [ ] **8.3** Create `ui/app/api/admin/feedback-suggestions/route.js`:

  ```js
  import { getSession } from '@/lib/session';

  const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

  export async function POST(request) {
    const session = await getSession();
    const body = await request.json();
    const res = await fetch(`${API_BASE}/admin/feedback-suggestions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session ? { 'X-OpenAI-Token': session.access_token } : {}),
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }
  ```

- [ ] **8.4** Create `ui/app/api/admin/feedback-suggestions/[id]/apply/route.js`:

  ```js
  import { getSession } from '@/lib/session';

  const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

  export async function POST(request, { params }) {
    const session = await getSession();
    const { id } = params;
    const res = await fetch(`${API_BASE}/admin/feedback-suggestions/${id}/apply`, {
      method: 'POST',
      headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }
  ```

- [ ] **8.5** Create `ui/app/api/admin/feedback-suggestions/[id]/dismiss/route.js`:

  ```js
  import { getSession } from '@/lib/session';

  const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

  export async function POST(request, { params }) {
    const session = await getSession();
    const { id } = params;
    const res = await fetch(`${API_BASE}/admin/feedback-suggestions/${id}/dismiss`, {
      method: 'POST',
      headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }
  ```

- [ ] **8.6** Commit:

  ```bash
  git add ui/app/api/admin/feedback-patterns/route.js ui/app/api/admin/feedback-alerts/route.js ui/app/api/admin/feedback-suggestions/route.js ui/app/api/admin/feedback-suggestions/
  git commit -m "feat: add Next.js admin proxy routes for feedback loop endpoints"
  ```

---

## Task 9: `/admin/feedback` dashboard page

**File to create:**
- `ui/app/(app)/admin/feedback/page.js`

### Steps

- [ ] **9.1** Create `ui/app/(app)/admin/feedback/page.js` with the complete implementation:

  ```js
  'use client';
  import { useState, useEffect } from 'react';

  // ---------------------------------------------------------------------------
  // Category display labels
  // ---------------------------------------------------------------------------
  const CATEGORY_LABELS = {
    wrong_info:    '❌ Factually wrong',
    missing_info:  '🔍 Missing info',
    wrong_context: '❌ Wrong context',
    outdated_info: '📅 Outdated info',
    too_generic:   '🎯 Too generic',
    wrong_tone:    '📝 Wrong tone',
    incomplete:    '✂️ Incomplete',
  };

  // ---------------------------------------------------------------------------
  // Simple word-diff implementation (no external library)
  // ---------------------------------------------------------------------------
  function computeInlineDiff(oldText, newText) {
    const oldWords = oldText.split(/(\s+)/);
    const newWords = newText.split(/(\s+)/);

    // Build LCS table
    const m = oldWords.length;
    const n = newWords.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (oldWords[i - 1] === newWords[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    // Backtrack to produce diff tokens
    const result = [];
    let i = m;
    let j = n;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
        result.unshift({ text: oldWords[i - 1], type: 'unchanged' });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        result.unshift({ text: newWords[j - 1], type: 'added' });
        j--;
      } else {
        result.unshift({ text: oldWords[i - 1], type: 'removed' });
        i--;
      }
    }
    return result;
  }

  // ---------------------------------------------------------------------------
  // Inline diff renderer
  // ---------------------------------------------------------------------------
  function InlineDiff({ oldText, newText }) {
    const tokens = computeInlineDiff(oldText, newText);
    return (
      <pre style={{
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '0.75rem',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '0.75rem 1rem',
        margin: 0,
      }}>
        {tokens.map((token, idx) => {
          if (token.type === 'added') {
            return (
              <mark key={idx} style={{
                background: 'rgba(34, 197, 94, 0.2)',
                color: 'var(--text)',
                borderRadius: '2px',
              }}>{token.text}</mark>
            );
          }
          if (token.type === 'removed') {
            return (
              <del key={idx} style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: 'var(--text-3)',
                textDecorationColor: 'rgba(239, 68, 68, 0.6)',
              }}>{token.text}</del>
            );
          }
          return <span key={idx}>{token.text}</span>;
        })}
      </pre>
    );
  }

  // ---------------------------------------------------------------------------
  // Suggestion panel (expands inline below a table row)
  // ---------------------------------------------------------------------------
  function SuggestionPanel({ suggestion, onApplied, onDismissed }) {
    const [applying, setApplying] = useState(false);
    const [dismissing, setDismissing] = useState(false);
    const [copyDone, setCopyDone] = useState(false);

    const handleApply = async () => {
      setApplying(true);
      try {
        const res = await fetch(`/api/admin/feedback-suggestions/${suggestion.id}/apply`, {
          method: 'POST',
        });
        if (res.ok) onApplied(suggestion.id);
      } finally {
        setApplying(false);
      }
    };

    const handleDismiss = async () => {
      setDismissing(true);
      try {
        const res = await fetch(`/api/admin/feedback-suggestions/${suggestion.id}/dismiss`, {
          method: 'POST',
        });
        if (res.ok) onDismissed(suggestion.id);
      } finally {
        setDismissing(false);
      }
    };

    const handleCopyAdvisory = () => {
      const advisory = `PROMPT ADVISORY\nMode: ${suggestion.mode}\nCategory: ${suggestion.failure_category}\nFile: api/app/prompts/templates.py\n\nReasoning:\n${suggestion.reasoning}\n\nSuggested prompt:\n${suggestion.suggested_prompt}`;
      navigator.clipboard.writeText(advisory);
      setCopyDone(true);
      setTimeout(() => setCopyDone(false), 2000);
    };

    const isBuiltin = suggestion.prompt_type === 'builtin';

    return (
      <div style={{
        padding: '1rem 1.25rem',
        background: 'var(--bg-2)',
        borderTop: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Reasoning block */}
        <div style={{
          borderLeft: '3px solid var(--accent, #4f8ef7)',
          paddingLeft: '0.75rem',
          marginBottom: '1rem',
          fontSize: '0.82rem',
          color: 'var(--text-2)',
          lineHeight: 1.5,
        }}>
          <strong style={{ color: 'var(--text)' }}>GPT-4o Analysis</strong>
          <p style={{ margin: '0.25rem 0 0' }}>{suggestion.reasoning}</p>
        </div>

        {/* Built-in advisory */}
        {isBuiltin && (
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '0.6rem 0.85rem',
            marginBottom: '1rem',
            background: 'var(--bg)',
            fontSize: '0.78rem',
            color: 'var(--text-2)',
          }}>
            <strong>Built-in prompt — requires code change</strong>
            <p style={{ margin: '0.2rem 0 0' }}>
              Constant: <code>BUILTIN_PROMPT_MAP["{suggestion.mode}"]</code> →{' '}
              <code>api/app/prompts/templates.py</code>
            </p>
          </div>
        )}

        {/* Inline diff */}
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: '0.4rem', fontWeight: 500 }}>
            Proposed changes
          </div>
          <InlineDiff
            oldText={suggestion.current_prompt}
            newText={suggestion.suggested_prompt}
          />
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleApply}
            disabled={applying || isBuiltin}
            className="btn btn-primary"
            style={{
              fontSize: '0.78rem',
              padding: '0.3rem 0.7rem',
              opacity: isBuiltin ? 0.4 : 1,
              cursor: isBuiltin ? 'not-allowed' : 'pointer',
            }}
            title={isBuiltin ? 'Built-in prompts require a code change' : 'Apply to persona prompt'}
          >
            {applying ? '…' : 'Apply to persona prompt'}
          </button>
          <button
            onClick={handleCopyAdvisory}
            className="btn"
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.7rem' }}
          >
            {copyDone ? '✓ Copied' : 'Copy advisory'}
          </button>
          <button
            onClick={handleDismiss}
            disabled={dismissing}
            className="btn"
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.7rem', color: 'var(--text-3)' }}
          >
            {dismissing ? '…' : 'Dismiss'}
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main page
  // ---------------------------------------------------------------------------
  export default function FeedbackDashboard() {
    const [alerts, setAlerts] = useState([]);
    const [patterns, setPatterns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedRow, setExpandedRow] = useState(null); // { rowKey, suggestion }
    const [generatingSuggestion, setGeneratingSuggestion] = useState(null); // rowKey

    useEffect(() => {
      Promise.all([
        fetch('/api/admin/feedback-alerts').then(r => r.json()).catch(() => []),
        fetch('/api/admin/feedback-patterns').then(r => r.json()).catch(() => []),
      ]).then(([alertsData, patternsData]) => {
        setAlerts(Array.isArray(alertsData) ? alertsData : []);
        setPatterns(Array.isArray(patternsData) ? patternsData : []);
        setLoading(false);
      });
    }, []);

    const handleSuggestFix = async (mode, failureCategory, promptType = 'persona') => {
      const rowKey = `${mode}::${failureCategory}`;
      setGeneratingSuggestion(rowKey);
      try {
        const res = await fetch('/api/admin/feedback-suggestions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode, failure_category: failureCategory, prompt_type: promptType }),
        });
        if (!res.ok) {
          const err = await res.json();
          alert(`Error generating suggestion: ${err.detail || res.statusText}`);
          return;
        }
        const suggestion = await res.json();
        setExpandedRow(prev =>
          prev?.rowKey === rowKey ? null : { rowKey, suggestion }
        );
      } finally {
        setGeneratingSuggestion(null);
      }
    };

    const handleApplied = (suggestionId) => {
      setExpandedRow(null);
    };

    const handleDismissed = (suggestionId) => {
      setExpandedRow(null);
      // Refresh alerts after dismiss
      fetch('/api/admin/feedback-alerts').then(r => r.json()).then(data => {
        setAlerts(Array.isArray(data) ? data : []);
      });
    };

    // Derived KPIs
    const totalNegative = patterns.reduce((sum, p) => sum + p.count, 0);
    const topMode = patterns.length > 0 ? patterns[0].mode : '—';
    const topCategory = patterns.length > 0 ? (CATEGORY_LABELS[patterns[0].failure_category] || patterns[0].failure_category) : '—';

    return (
      <>
        <div className="topbar">
          <div>
            <div className="topbar-title">Feedback Analytics</div>
            <div className="topbar-meta">Failure patterns · prompt suggestions · last 7 days</div>
          </div>
        </div>

        <div className="content">
          {loading && (
            <p style={{ color: 'var(--text-3)', fontSize: '0.82rem' }}>Loading…</p>
          )}

          {/* Alert banners */}
          {alerts.map((alert, idx) => (
            <div key={idx} style={{
              background: 'rgba(234, 179, 8, 0.12)',
              border: '1px solid rgba(234, 179, 8, 0.35)',
              borderRadius: '6px',
              padding: '0.65rem 1rem',
              marginBottom: '0.6rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              fontSize: '0.82rem',
            }}>
              <span>
                ⚠️ <strong>{alert.count} failures</strong> in <strong>{alert.mode}</strong> —
                "{CATEGORY_LABELS[alert.failure_category] || alert.failure_category}" since last analysis
              </span>
              <button
                className="btn btn-primary"
                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', whiteSpace: 'nowrap' }}
                onClick={() => handleSuggestFix(alert.mode, alert.failure_category, 'persona')}
                disabled={generatingSuggestion === `${alert.mode}::${alert.failure_category}`}
              >
                {generatingSuggestion === `${alert.mode}::${alert.failure_category}` ? '…' : 'View suggestion'}
              </button>
            </div>
          ))}

          {/* KPI row */}
          <div className="kpi-row" style={{ marginBottom: '1.5rem' }}>
            {[
              { label: 'Negative Feedback (7d)', value: totalNegative, sub: 'across all modes' },
              { label: 'Top Failing Mode', value: topMode, sub: 'by volume' },
              { label: 'Most Common Failure', value: topCategory, sub: 'by count' },
              { label: 'Patterns Tracked', value: patterns.length, sub: 'active categories' },
            ].map((k) => (
              <div className="kpi-card" key={k.label}>
                <div className="kpi-label">{k.label}</div>
                <div className="kpi-value">{k.value}</div>
                <div className="kpi-sub">{k.sub}</div>
              </div>
            ))}
          </div>

          {/* Failure patterns table */}
          {!loading && patterns.length === 0 && (
            <p style={{ color: 'var(--text-3)', fontSize: '0.82rem' }}>
              No failure patterns in the last 7 days.
            </p>
          )}

          {patterns.length > 0 && (
            <div style={{ border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-2)', borderBottom: '1px solid var(--border)' }}>
                    {['Mode', 'Category', 'Count (7d)', 'Last seen', 'Action'].map(h => (
                      <th key={h} style={{ padding: '0.55rem 0.85rem', textAlign: 'left', fontWeight: 600, color: 'var(--text-2)', fontSize: '0.75rem' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {patterns.map((pattern, idx) => {
                    const rowKey = `${pattern.mode}::${pattern.failure_category}`;
                    const isExpanded = expandedRow?.rowKey === rowKey;
                    const isGenerating = generatingSuggestion === rowKey;
                    return (
                      <>
                        <tr key={rowKey} style={{
                          borderBottom: isExpanded ? 'none' : '1px solid var(--border)',
                          background: isExpanded ? 'var(--bg-2)' : 'var(--bg)',
                        }}>
                          <td style={{ padding: '0.55rem 0.85rem', fontWeight: 500 }}>{pattern.mode}</td>
                          <td style={{ padding: '0.55rem 0.85rem' }}>
                            {CATEGORY_LABELS[pattern.failure_category] || pattern.failure_category}
                          </td>
                          <td style={{ padding: '0.55rem 0.85rem', fontWeight: 600 }}>{pattern.count}</td>
                          <td style={{ padding: '0.55rem 0.85rem', color: 'var(--text-3)' }}>
                            {pattern.last_seen ? new Date(pattern.last_seen).toLocaleDateString() : '—'}
                          </td>
                          <td style={{ padding: '0.55rem 0.85rem' }}>
                            <button
                              className="btn"
                              style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}
                              onClick={() => isExpanded
                                ? setExpandedRow(null)
                                : handleSuggestFix(pattern.mode, pattern.failure_category, 'persona')
                              }
                              disabled={isGenerating}
                            >
                              {isGenerating ? '…' : isExpanded ? 'Close' : 'Suggest fix'}
                            </button>
                          </td>
                        </tr>
                        {isExpanded && expandedRow?.suggestion && (
                          <tr key={`${rowKey}-panel`}>
                            <td colSpan={5} style={{ padding: 0 }}>
                              <SuggestionPanel
                                suggestion={expandedRow.suggestion}
                                onApplied={handleApplied}
                                onDismissed={handleDismissed}
                              />
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </>
    );
  }
  ```

- [ ] **9.2** Commit:

  ```bash
  git add "ui/app/(app)/admin/feedback/page.js"
  git commit -m "feat: add /admin/feedback dashboard page with inline diff suggestion panel"
  ```

---

## Task 10: Full test run + push

### Steps

- [ ] **10.1** Run the feedback loop tests in isolation:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/unit/test_feedback_loop.py -v
  ```

  Expected: all tests pass.

- [ ] **10.2** Run the full test suite to check for regressions:

  ```bash
  cd /path/to/worktree/api && .venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -30
  ```

  Expected: no new failures.

- [ ] **10.3** Fix any failing tests before proceeding.

- [ ] **10.4** Push all commits:

  ```bash
  git push
  ```

---

## Implementation Notes

### Import additions for `api/app/api/routes/admin.py`

The full set of new imports required at the top of `admin.py` (add to existing imports block):

```python
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from openai import OpenAI
from pydantic import BaseModel as PydanticBaseModel

from app.models.feedback import AIFeedback, PromptSuggestion
from app.prompts.templates import (
    SYSTEM_CALL_COACH,
    SYSTEM_MARKETING_EXECUTION,
    SYSTEM_ORACLE,
    SYSTEM_REP_EXECUTION,
    SYSTEM_SE_EXECUTION,
)
```

Note: `func` and `select` are already imported from `sqlalchemy` in `admin.py` (`from sqlalchemy import case, func, select`). Do not re-import or alias them — the endpoint implementations above use `func` directly.

### Test file header

`api/tests/unit/test_feedback_loop.py` must start with:

```python
"""Tests for feedback loop Phase 1 implementation."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
```

All task test blocks are appended to this single file in order.

### Worktree path

Replace `/path/to/worktree` in all commands with the actual path:
`/Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb`
