# Two-Stage Intelligence Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-pass pre-call intel flow with a two-stage pipeline where GPT-5.4 Mini summarizes each of 8 Firecrawl query result sets in parallel, then GPT-5.4 with medium thinking synthesizes the summaries into the final brief — all configurable per-user from Settings.

**Architecture:** A new `_summarize_query_results()` method on the LLM service runs 8 parallel Mini calls via `ThreadPoolExecutor`. Its output replaces the raw-snippet block in `_deep_research_pre_call()`. Five new `UserPreference` fields control the feature; they are unpacked in `chat_orchestrator.py` and passed as scalar kwargs down to `answer_oracle()` and `_deep_research_pre_call()`. A new `IntelBriefSettingsPanel` client component renders the toggle + 4 dropdowns in the existing AI Behavior settings section.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, Alembic, FastAPI, Pydantic v2, Next.js 14 App Router, React 18, pytest + SQLite in-memory

**Spec:** `docs/superpowers/specs/2026-03-23-two-stage-intel-brief-design.md`

---

## File Structure

### Modified files
- `api/alembic/versions/20260323_000002_add_intel_brief_prefs.py` ← **NEW** migration adding 5 columns to `user_preferences`
- `api/app/models/entities.py` ← add 5 `Mapped` fields to `UserPreference` (lines ~376–385)
- `api/app/schemas/user_prefs.py` ← add 5 fields to `UserPrefRead` and `UserPrefUpdate`
- `api/app/api/routes/user_prefs.py` ← handle 5 new fields in PUT handler (lines ~35–41)
- `api/app/services/llm.py` ← add `_summarize_query_results()` method; modify `_deep_research_pre_call()` and `answer_oracle()`
- `api/app/services/chat_orchestrator.py` ← unpack 5 new pref fields and pass to `answer_oracle()`
- `ui/components/IntelBriefSettingsPanel.js` ← **NEW** client component for toggle + 4 dropdowns
- `ui/app/(app)/settings/page.js` ← import and render `IntelBriefSettingsPanel` in `#ai` section

### Test files
- `tests/unit/test_intel_brief.py` ← **NEW** 6 unit tests for summarizer helper + wiring

---

## Task 1: DB Migration, Model Fields, Schema, and Route Handler

**Files:**
- Create: `api/alembic/versions/20260323_000002_add_intel_brief_prefs.py`
- Modify: `api/app/models/entities.py`
- Modify: `api/app/schemas/user_prefs.py`
- Modify: `api/app/api/routes/user_prefs.py`
- Test: `tests/unit/test_intel_brief.py`

### Context

`UserPreference` model is at `api/app/models/entities.py` lines 376–385. Current fields: `user_email`, `llm_model`, `reasoning_effort`, `retrieval_top_k`, `updated_at`. The model has `retrieval_top_k` but you must check whether it's in the migration chain — if absent from any migration, add it in this migration too.

Schemas are at `api/app/schemas/user_prefs.py`. `UserPrefUpdate` uses `| None = None` for all fields. `UserPrefRead` uses `from_attributes=True`.

Route handler at `api/app/api/routes/user_prefs.py` lines 35–41 — the PUT handler manually checks each field with `if body.field is not None`. Follow that same pattern for the 5 new fields.

The most recent migration is `20260323_000001`. The new migration `down_revision` must be `"20260323_000001"`.

**Check `retrieval_top_k`:** Run this command to see if it's in any existing migration:
```bash
grep -r "retrieval_top_k" /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api/alembic/versions/
```
If found: omit it from this migration. If not found: add it as a nullable Integer column alongside the 5 new columns.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_intel_brief.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py::test_user_preference_intel_brief_fields_have_correct_defaults -v
```

Expected: FAIL (AttributeError or column not found)

- [ ] **Step 3: Add 5 fields to `UserPreference` model**

In `api/app/models/entities.py`, after the `retrieval_top_k` line (~line 382), add:

```python
    intel_brief_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true())
    intel_brief_summarizer_model: Mapped[str | None] = mapped_column(String(64), nullable=True, server_default="gpt-5.4-mini")
    intel_brief_summarizer_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    intel_brief_synthesis_model: Mapped[str | None] = mapped_column(String(64), nullable=True, server_default="gpt-5.4")
    intel_brief_synthesis_effort: Mapped[str] = mapped_column(String(16), nullable=False, server_default="medium")
```

Ensure `import sqlalchemy as sa` exists at the top of `entities.py`. If `Boolean` is not already imported from `sqlalchemy`, add it.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py::test_user_preference_intel_brief_fields_have_correct_defaults -v
```

Expected: PASS

- [ ] **Step 5: Create Alembic migration**

First check if `retrieval_top_k` exists in any migration:
```bash
grep -r "retrieval_top_k" /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api/alembic/versions/
```

Create `api/alembic/versions/20260323_000002_add_intel_brief_prefs.py`:

```python
"""Add intel_brief preference columns to user_preferences

Revision ID: 20260323_000002
Revises: 20260323_000001
Create Date: 2026-03-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260323_000002"
down_revision = "20260323_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add retrieval_top_k if not already present (check grep result above)
    # If grep returned nothing, uncomment this line:
    # op.add_column("user_preferences", sa.Column("retrieval_top_k", sa.Integer(), nullable=True))

    op.add_column("user_preferences", sa.Column(
        "intel_brief_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_model", sa.String(64), nullable=True, server_default="gpt-5.4-mini"
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_summarizer_effort", sa.String(16), nullable=True
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_model", sa.String(64), nullable=True, server_default="gpt-5.4"
    ))
    op.add_column("user_preferences", sa.Column(
        "intel_brief_synthesis_effort", sa.String(16), nullable=False, server_default="medium"
    ))


def downgrade() -> None:
    op.drop_column("user_preferences", "intel_brief_synthesis_effort")
    op.drop_column("user_preferences", "intel_brief_synthesis_model")
    op.drop_column("user_preferences", "intel_brief_summarizer_effort")
    op.drop_column("user_preferences", "intel_brief_summarizer_model")
    op.drop_column("user_preferences", "intel_brief_enabled")
```

- [ ] **Step 6: Update `UserPrefUpdate` and `UserPrefRead` schemas**

Replace the contents of `api/app/schemas/user_prefs.py` with:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserPrefUpdate(BaseModel):
    llm_model: str | None = None
    reasoning_effort: str | None = None
    retrieval_top_k: int | None = None
    intel_brief_enabled: bool | None = None
    intel_brief_summarizer_model: str | None = None
    intel_brief_summarizer_effort: str | None = None
    intel_brief_synthesis_model: str | None = None
    intel_brief_synthesis_effort: str | None = None


class UserPrefRead(BaseModel):
    user_email: str
    llm_model: str | None
    reasoning_effort: str | None
    retrieval_top_k: int | None
    intel_brief_enabled: bool | None = None
    intel_brief_summarizer_model: str | None = None
    intel_brief_summarizer_effort: str | None = None
    intel_brief_synthesis_model: str | None = None
    intel_brief_synthesis_effort: str = "medium"
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Update PUT handler to save new fields**

In `api/app/api/routes/user_prefs.py`, in the `upsert_user_preferences` function, after the existing `if body.retrieval_top_k is not None:` block (line ~40), add:

```python
    if body.intel_brief_enabled is not None:
        pref.intel_brief_enabled = body.intel_brief_enabled
    if body.intel_brief_summarizer_model is not None:
        pref.intel_brief_summarizer_model = body.intel_brief_summarizer_model or None
    if body.intel_brief_summarizer_effort is not None:
        pref.intel_brief_summarizer_effort = body.intel_brief_summarizer_effort or None
    if body.intel_brief_synthesis_model is not None:
        pref.intel_brief_synthesis_model = body.intel_brief_synthesis_model or None
    if body.intel_brief_synthesis_effort is not None:
        pref.intel_brief_synthesis_effort = body.intel_brief_synthesis_effort or None
```

- [ ] **Step 8: Run all existing unit tests to confirm nothing is broken**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/ -v
```

Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  add api/alembic/versions/20260323_000002_add_intel_brief_prefs.py \
      api/app/models/entities.py \
      api/app/schemas/user_prefs.py \
      api/app/api/routes/user_prefs.py \
      tests/unit/test_intel_brief.py
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  commit -m "feat: add intel_brief preference fields — migration, model, schema, route"
```

---

## Task 2: `_summarize_query_results()` Helper

**Files:**
- Modify: `api/app/services/llm.py`
- Test: `tests/unit/test_intel_brief.py`

### Context

`_responses_text()` is a method on the `LLMService` class at line ~748. It accepts `system_prompt`, `user_prompt`, `model`, `tools`, `reasoning_effort`. It catches exceptions internally and returns `None` on failure — it does NOT raise. When it returns `None`, fall back to raw snippets.

`ThreadPoolExecutor` is in Python's standard library: `from concurrent.futures import ThreadPoolExecutor`. Check if it's already imported at the top of `llm.py`; if not, add it.

The new method belongs on the `LLMService` class, placed just before `_deep_research_pre_call()` (currently around line 930).

- [ ] **Step 1: Add 3 unit tests for the helper**

Append to `tests/unit/test_intel_brief.py`:

```python
from unittest.mock import MagicMock, patch


def test_summarize_query_results_calls_model_per_query():
    """One _responses_text call per query."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py -v -k "summarize"
```

Expected: FAIL (AttributeError: `LLMService` has no `_summarize_query_results`)

- [ ] **Step 3: Add `_summarize_query_results()` to `LLMService`**

First check if `ThreadPoolExecutor` is already imported in `llm.py`:
```bash
grep "ThreadPoolExecutor" /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api/app/services/llm.py
```
If not found, add to the imports at the top of `llm.py`:
```python
from concurrent.futures import ThreadPoolExecutor
```

Add the method to `LLMService`, just before `_deep_research_pre_call()` (around line 930):

```python
    _SUMMARIZER_SYSTEM = (
        "You are a B2B research analyst. Given a set of web search results for a specific "
        "research query, extract and summarize the key findings into a single concise paragraph. "
        "Focus on: company information, technical signals, pain points, business context, "
        "and competitive indicators. Omit filler, ads, and irrelevant content. "
        "Be specific — include company names, numbers, product names where present."
    )

    def _summarize_query_results(
        self,
        query_results: list[tuple[str, list[str]]],
        *,
        model: str = "gpt-5.4-mini",
        reasoning_effort: str | None = None,
    ) -> list[tuple[str, str]]:
        """Summarize each query's search result snippets in parallel using a fast model.
        Falls back to raw joined snippets on per-call failure or None response."""

        def _summarize_one(item: tuple[str, list[str]]) -> tuple[str, str]:
            label, snippets = item
            if not snippets:
                return label, "(no results)"
            results_text = "\n---\n".join(snippets)
            user_msg = f"Query: {label}\n\nSearch results:\n{results_text}"
            try:
                summary = self._responses_text(
                    self._SUMMARIZER_SYSTEM,
                    user_msg,
                    model=model,
                    reasoning_effort=reasoning_effort,
                )
                return label, summary if summary else "\n---\n".join(snippets)
            except Exception as exc:
                self.logger.warning("Summarizer call failed for '%s': %s", label, exc)
                return label, "\n---\n".join(snippets)

        with ThreadPoolExecutor(max_workers=8) as executor:
            return list(executor.map(_summarize_one, query_results))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py -v -k "summarize"
```

Expected: 4 PASS

- [ ] **Step 5: Run all tests to confirm nothing broken**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/ -v
```

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  add api/app/services/llm.py \
      tests/unit/test_intel_brief.py
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  commit -m "feat: add _summarize_query_results() helper to LLMService"
```

---

## Task 3: Wire Two-Stage into `_deep_research_pre_call()` and Thread Parameters

**Files:**
- Modify: `api/app/services/llm.py`
- Modify: `api/app/services/chat_orchestrator.py`
- Test: `tests/unit/test_intel_brief.py`

### Context

**`_deep_research_pre_call()` current signature** (line ~930):
```python
def _deep_research_pre_call(
    self,
    system_prompt: str,
    message: str,
    model: str | None,
    tools: list[dict] | None,
    reasoning_effort: str | None,
) -> str | None:
```

**`answer_oracle()` current signature** (line ~1047):
```python
def answer_oracle(
    self,
    message: str,
    hits: list[RetrievedChunk],
    *,
    model: str | None = None,
    tools: list[dict] | None = None,
    allow_ungrounded: bool = False,
    persona_name: str | None = None,
    persona_prompt: str | None = None,
    reasoning_effort: str | None = None,
    source_instructions: str | None = None,
    section: str | None = None,
    user_email: str | None = None,
    tidb_expert_enabled: bool = False,
    prompt_service: PromptService | None = None,
) -> dict[str, Any]:
```

**Inside `_deep_research_pre_call()`**, the current flow is:
1. Lines ~942–978: loop through 8 queries, build `research_sections` list + `competitive_hits` list
2. Lines ~980–1017: build competitive alert block; insert at `research_sections[1]` if hits found
3. Line ~1019: `research_notes = "\n".join(research_sections)`
4. Lines ~1021–1041: build `synthesize_prompt`
5. Lines ~1043–1044: call `_responses_text(system_prompt, synthesize_prompt, model=model, ...)`

**The two-stage change:**
- Also collect `query_raw_results: list[tuple[str, list[str]]]` during the loop (label + snippet strings only)
- After the loop AND after the competitive alert block, if `intel_brief_enabled`: call `_summarize_query_results()` and rebuild `research_sections` from summaries (keeping the header at index 0 and the already-inserted competitive alert at index 1 if present)
- The synthesis call uses `intel_brief_synthesis_model` and `intel_brief_synthesis_effort` instead of `model` and `reasoning_effort`

**`chat_orchestrator.py`** — `user_pref` is fetched at line ~353. `resolved_model` and `resolved_reasoning` are set at lines ~355–361. The `answer_oracle()` call is at line ~450. The 5 new fields must be extracted from `user_pref` and passed to `answer_oracle()`.

- [ ] **Step 1: Add 2 wiring tests**

Append to `tests/unit/test_intel_brief.py`:

```python
def test_deep_research_uses_summaries_when_enabled():
    """When intel_brief_enabled=True, synthesis prompt contains summary paragraphs, not raw snippets."""
    from app.services.llm import LLMService

    svc = LLMService.__new__(LLMService)
    svc.logger = MagicMock()

    # Mock Firecrawl search to return predictable snippets
    svc._firecrawl_search = MagicMock(return_value=[
        {"url": "https://example.com", "title": "Title", "snippet": "raw snippet content"}
    ])
    svc._extract_company_contact = MagicMock(return_value=("Acme Corp", "Jane Doe"))

    # Mock summarizer to return identifiable summaries
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
    # Synthesis used the new model/effort, not the old ones
    assert synthesis_calls[0]["model"] == "gpt-5.4"
    assert synthesis_calls[0]["effort"] == "medium"
    # Synthesis prompt contains summaries, not raw snippets
    assert "SUMMARY:" in synthesis_calls[0]["prompt"]
    assert "raw snippet content" not in synthesis_calls[0]["prompt"]
    # Summarizer was called with all 8 query results
    svc._summarize_query_results.assert_called_once()
    call_args = svc._summarize_query_results.call_args
    assert len(call_args[0][0]) == 8


def test_deep_research_skips_summaries_when_disabled():
    """When intel_brief_enabled=False, synthesis prompt contains raw snippets, summarizer not called."""
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
    # Summarizer was NOT called
    svc._summarize_query_results.assert_not_called()
    # Raw snippets present in synthesis prompt
    assert "raw snippet content" in synthesis_calls[0]["prompt"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py -v -k "deep_research"
```

Expected: FAIL (TypeError: `_deep_research_pre_call()` missing keyword arguments)

- [ ] **Step 3: Add 5 params to `_deep_research_pre_call()` and wire the two-stage logic**

Modify `_deep_research_pre_call()` in `api/app/services/llm.py`:

**3a. Update the signature** — add 5 new params after `reasoning_effort`:

```python
    def _deep_research_pre_call(
        self,
        system_prompt: str,
        message: str,
        model: str | None,
        tools: list[dict] | None,
        reasoning_effort: str | None,
        *,
        intel_brief_enabled: bool = True,
        intel_brief_summarizer_model: str = "gpt-5.4-mini",
        intel_brief_summarizer_effort: str | None = None,
        intel_brief_synthesis_model: str = "gpt-5.4",
        intel_brief_synthesis_effort: str = "medium",
    ) -> str | None:
```

**3b. In the main query loop**, add 4 targeted lines — do NOT rewrite the loop or touch the competitive hit detection code:

Add `query_raw_results: list[tuple[str, list[str]]] = []` immediately before `research_sections: list[str] = ...`.

Inside the existing `for query, label in queries:` loop, make these additions:
- Before `for r in results:` inside the `if results:` block, add: `snippets_for_query: list[str] = []`
- As the FIRST line inside `for r in results:`, add: `snippets_for_query.append(r["snippet"])`
- After the `for r in results:` block closes (but still inside `if results:`), add: `query_raw_results.append((label, snippets_for_query))`
- In the `else:` branch (after `research_sections.append("- No results returned")`), add: `query_raw_results.append((label, []))`

All existing lines — `research_sections.append(...)`, the `DOCS_PATTERNS` check, `is_company_specific`, `matched_competitor`, `competitive_hits.append(...)` — remain completely unchanged.

**3c. After the loop and competitive alert block** (after `research_sections.insert(1, instruction)` and before `research_notes = "\n".join(research_sections)`), add:

```python
        # Two-stage: replace raw-snippet sections with Mini summaries
        if intel_brief_enabled:
            summaries = self._summarize_query_results(
                query_raw_results,
                model=intel_brief_summarizer_model,
                reasoning_effort=intel_brief_summarizer_effort,
            )
            # Rebuild research_sections: keep header (index 0) and competitive alert if inserted (index 1)
            summary_body = [f"### {lbl}\n{para}" for lbl, para in summaries]
            if competitive_hits:
                # competitive alert was inserted at index 1; keep header + alert, replace rest
                research_sections = research_sections[:2] + summary_body
            else:
                research_sections = research_sections[:1] + summary_body
```

**3d. Update the final synthesis call** to use the intel-brief model/effort kwargs:

```python
        return self._responses_text(
            system_prompt,
            synthesize_prompt,
            model=intel_brief_synthesis_model if intel_brief_enabled else model,
            tools=None,
            reasoning_effort=intel_brief_synthesis_effort if intel_brief_enabled else reasoning_effort,
        )
```

- [ ] **Step 4: Add 5 params to `answer_oracle()` and forward them**

In `answer_oracle()` signature, add after `prompt_service`:

```python
        intel_brief_enabled: bool = True,
        intel_brief_summarizer_model: str = "gpt-5.4-mini",
        intel_brief_summarizer_effort: str | None = None,
        intel_brief_synthesis_model: str = "gpt-5.4",
        intel_brief_synthesis_effort: str = "medium",
```

In the body where `_deep_research_pre_call` is called (line ~1075):

```python
                answer = self._deep_research_pre_call(
                    system_prompt,
                    message,
                    model=model,
                    tools=tools,
                    reasoning_effort=reasoning_effort,
                    intel_brief_enabled=intel_brief_enabled,
                    intel_brief_summarizer_model=intel_brief_summarizer_model,
                    intel_brief_summarizer_effort=intel_brief_summarizer_effort,
                    intel_brief_synthesis_model=intel_brief_synthesis_model,
                    intel_brief_synthesis_effort=intel_brief_synthesis_effort,
                )
```

- [ ] **Step 5: Update `chat_orchestrator.py` to unpack and forward the new fields**

In `chat_orchestrator.py`, after the block that sets `resolved_reasoning` from `user_pref` (~lines 357–363), add:

```python
        intel_brief_enabled: bool = True
        intel_brief_summarizer_model: str = "gpt-5.4-mini"
        intel_brief_summarizer_effort: str | None = None
        intel_brief_synthesis_model: str = "gpt-5.4"
        intel_brief_synthesis_effort: str = "medium"
        if user_pref:
            if getattr(user_pref, "intel_brief_enabled", None) is not None:
                intel_brief_enabled = user_pref.intel_brief_enabled
            if getattr(user_pref, "intel_brief_summarizer_model", None):
                intel_brief_summarizer_model = user_pref.intel_brief_summarizer_model
            if getattr(user_pref, "intel_brief_summarizer_effort", None):
                intel_brief_summarizer_effort = user_pref.intel_brief_summarizer_effort
            if getattr(user_pref, "intel_brief_synthesis_model", None):
                intel_brief_synthesis_model = user_pref.intel_brief_synthesis_model
            if getattr(user_pref, "intel_brief_synthesis_effort", None):
                intel_brief_synthesis_effort = user_pref.intel_brief_synthesis_effort
```

Then in the `answer_oracle()` call at line ~450, add the 5 new kwargs:

```python
        data = self.llm.answer_oracle(
            message,
            hits,
            model=resolved_model,
            tools=llm_tools,
            allow_ungrounded=skip_rag,
            persona_name=persona_name,
            persona_prompt=persona_prompt,
            reasoning_effort=resolved_reasoning,
            source_instructions=source_instructions or None,
            section=section,
            intel_brief_enabled=intel_brief_enabled,
            intel_brief_summarizer_model=intel_brief_summarizer_model,
            intel_brief_summarizer_effort=intel_brief_summarizer_effort,
            intel_brief_synthesis_model=intel_brief_synthesis_model,
            intel_brief_synthesis_effort=intel_brief_synthesis_effort,
        )
```

- [ ] **Step 6: Run all wiring tests**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/test_intel_brief.py -v
```

Expected: ALL 7 PASS

- [ ] **Step 7: Run full unit suite**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/ -v
```

Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  add api/app/services/llm.py \
      api/app/services/chat_orchestrator.py \
      tests/unit/test_intel_brief.py
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  commit -m "feat: wire two-stage summarization into _deep_research_pre_call and thread params"
```

---

## Task 4: Settings UI — Intel Brief Panel

**Files:**
- Create: `ui/components/IntelBriefSettingsPanel.js`
- Modify: `ui/app/(app)/settings/page.js`

### Context

`ui/app/(app)/settings/page.js` is a **server component** (`async function SettingsPage()`). It renders client components by importing them. The `#ai` section starts at line ~128. It currently has two panels: "Intelligence Search Profiles" and "TiDB Expert Mode". The new "Intelligence Brief" panel goes after the TiDB Expert panel (after line ~198).

The settings page uses `.panel` / `.panel-header` / `.panel-body` / `.panel-title` CSS class names throughout. Follow the same pattern.

Preferences are fetched/saved via `GET /api/user/preferences` and `PUT /api/user/preferences` with the `X-User-Email` header. In Next.js, this header is set by the backend cookie session. For client components, you can call these endpoints directly — the Next.js route handler (at `ui/app/api/user/preferences/route.js`) forwards the request to the Python API with the user email from session.

Available models (from `ui/components/ModelPickerDropdown.js`):
```
gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, gpt-5.3-codex, o4-mini, o3, o3-pro, o3-mini, gpt-5.1-codex, gpt-5-codex-mini
```

Thinking effort options: `null` (None), `"low"`, `"medium"`, `"high"`. The summarizer allows None; the synthesis does not.

- [ ] **Step 1: Create `IntelBriefSettingsPanel.js`**

Create `ui/components/IntelBriefSettingsPanel.js`:

```javascript
'use client';
import { useState, useEffect } from 'react';

const MODELS = [
  'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5.3-codex',
  'o4-mini', 'o3', 'o3-pro', 'o3-mini', 'gpt-5.1-codex', 'gpt-5-codex-mini',
];
const EFFORT_OPTIONS = ['low', 'medium', 'high'];

export default function IntelBriefSettingsPanel() {
  const [enabled, setEnabled] = useState(true);
  const [summarizerModel, setSummarizerModel] = useState('gpt-5.4-mini');
  const [summarizerEffort, setSummarizerEffort] = useState('');
  const [synthesisModel, setSynthesisModel] = useState('gpt-5.4');
  const [synthesisEffort, setSynthesisEffort] = useState('medium');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/user/preferences')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        if (data.intel_brief_enabled != null) setEnabled(data.intel_brief_enabled);
        if (data.intel_brief_summarizer_model) setSummarizerModel(data.intel_brief_summarizer_model);
        setSummarizerEffort(data.intel_brief_summarizer_effort || '');
        if (data.intel_brief_synthesis_model) setSynthesisModel(data.intel_brief_synthesis_model);
        if (data.intel_brief_synthesis_effort) setSynthesisEffort(data.intel_brief_synthesis_effort);
      })
      .catch(() => {});
  }, []);

  const save = async (patch) => {
    setSaving(true);
    try {
      await fetch('/api/user/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
    } catch { /* silent */ } finally {
      setSaving(false);
    }
  };

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    save({ intel_brief_enabled: next });
  };

  const labelStyle = { fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 };
  const selectStyle = { fontSize: '0.8rem' };

  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
      {/* Toggle row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>Two-stage summarization</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginTop: '0.1rem' }}>
            GPT Mini extracts findings per search query, then synthesis model writes the brief
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={saving}
          style={{
            width: '40px', height: '22px', borderRadius: '11px', border: 'none', cursor: 'pointer',
            background: enabled ? 'var(--accent, #7c3aed)' : 'var(--border)',
            position: 'relative', flexShrink: 0, transition: 'background 0.2s',
          }}
          aria-label={enabled ? 'Disable two-stage summarization' : 'Enable two-stage summarization'}
        >
          <span style={{
            position: 'absolute', top: '3px',
            left: enabled ? '21px' : '3px',
            width: '16px', height: '16px', borderRadius: '50%',
            background: 'white', transition: 'left 0.2s',
          }} />
        </button>
      </div>

      {/* Config controls — only shown when enabled */}
      {enabled && (
        <div style={{ display: 'grid', gap: '0.6rem', paddingLeft: '0.5rem', borderLeft: '2px solid var(--border)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            {/* Summarizer model */}
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Summarizer model</label>
              <select
                className="input"
                style={selectStyle}
                value={summarizerModel}
                onChange={e => { setSummarizerModel(e.target.value); save({ intel_brief_summarizer_model: e.target.value }); }}
              >
                {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            {/* Summarizer thinking */}
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Summarizer thinking</label>
              <select
                className="input"
                style={selectStyle}
                value={summarizerEffort}
                onChange={e => { setSummarizerEffort(e.target.value); save({ intel_brief_summarizer_effort: e.target.value || null }); }}
              >
                <option value="">None</option>
                {EFFORT_OPTIONS.map(e => <option key={e} value={e}>{e.charAt(0).toUpperCase() + e.slice(1)}</option>)}
              </select>
            </div>
            {/* Synthesis model */}
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Synthesis model</label>
              <select
                className="input"
                style={selectStyle}
                value={synthesisModel}
                onChange={e => { setSynthesisModel(e.target.value); save({ intel_brief_synthesis_model: e.target.value }); }}
              >
                {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            {/* Synthesis thinking */}
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Synthesis thinking</label>
              <select
                className="input"
                style={selectStyle}
                value={synthesisEffort}
                onChange={e => { setSynthesisEffort(e.target.value); save({ intel_brief_synthesis_effort: e.target.value }); }}
              >
                {EFFORT_OPTIONS.map(e => <option key={e} value={e}>{e.charAt(0).toUpperCase() + e.slice(1)}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Import and add the panel to settings page**

In `ui/app/(app)/settings/page.js`:

**2a. Add import** at the top with the other component imports:
```javascript
import IntelBriefSettingsPanel from '../../../components/IntelBriefSettingsPanel';
```

**2b. Add panel** in the JSX, after the TiDB Expert Mode panel (after the closing `</div>` of that panel, around line ~199), before `{/* ── Prompt Studio ─────── */}`:

```jsx
        {/* Intelligence Brief panel */}
        <div className="panel" style={{ marginTop: '0.75rem' }}>
          <div className="panel-header">
            <span className="panel-title">Intelligence Brief</span>
            <span className="tag">Pre-Call Intel</span>
          </div>
          <div className="panel-body">
            <IntelBriefSettingsPanel />
          </div>
        </div>
```

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/ -v
```

Expected: ALL PASS (including the 7 intel brief tests)

- [ ] **Step 4: Commit**

```bash
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  add ui/components/IntelBriefSettingsPanel.js \
      ui/app/\(app\)/settings/page.js
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  commit -m "feat: add IntelBriefSettingsPanel to Settings AI Behavior section"
```

---

## Task 5: Final Test and Push

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/api
.venv/bin/pytest /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb/tests/unit/ -v
```

Expected: ALL PASS

- [ ] **Step 2: Push branch**

```bash
git -C /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb \
  push origin feature/intelligence-models-feedback-tidb
```
