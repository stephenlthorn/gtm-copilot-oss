# Feedback Loop System — Phase 1 Design

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Extended thumbs-down capture with failure categories, pattern analysis backend, auto-triggered GPT-4 prompt suggestions, and a dedicated feedback analytics dashboard. All Vercel Pro + TiDB Cloud compatible.

---

## Background

The system currently captures binary thumbs-up/down feedback via `AIFeedback` with an optional free-text correction. There is no failure categorization, no pattern aggregation, and no mechanism to translate negative feedback into prompt improvements. This design adds:

1. A 7-category failure taxonomy captured at thumbs-down time
2. A pattern analysis backend that aggregates failures by mode × category
3. An auto-trigger that detects when a pattern crosses a threshold and surfaces a GPT-4–generated prompt suggestion
4. A dedicated `/admin/feedback` dashboard showing patterns, suggestions, and apply/dismiss controls

**Infrastructure constraint:** Vercel Pro + TiDB Cloud. No background jobs. All analysis runs at request time (dashboard page load triggers alert check; suggestion generation triggers on user action).

---

## Failure Category Taxonomy

Seven categories stored as short slugs in `VARCHAR(64)`. Only set on negative (`rating = 'negative'`) feedback.

| Slug | Display label |
|---|---|
| `wrong_info` | ❌ Factually wrong / hallucinated |
| `missing_info` | 🔍 Missing info (KB or transcript) |
| `wrong_context` | ❌ Wrong account / deal context |
| `outdated_info` | 📅 Outdated / wrong stage info |
| `too_generic` | 🎯 Generic — not specific enough |
| `wrong_tone` | 📝 Wrong tone or format |
| `incomplete` | ✂️ Incomplete / too long |

---

## Area 1: Extended Feedback Capture

### Model Change

**File:** `api/app/models/feedback.py` — `AIFeedback`

Add one nullable field after `correction`:

```python
failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### Schema Change

**File:** `api/app/schemas/feedback.py` — `FeedbackCreate` and `FeedbackRead`

Add to `FeedbackCreate`:
```python
failure_category: str | None = None
```

Add to `FeedbackRead` (so callers can see the stored category):
```python
failure_category: str | None = None
```

Valid slugs: `wrong_info`, `missing_info`, `wrong_context`, `outdated_info`, `too_generic`, `wrong_tone`, `incomplete`. Validation happens in the route handler — invalid slugs are silently dropped (set to None) to avoid breaking existing clients.

### Route Change

**File:** `api/app/api/routes/feedback.py` — `create_feedback`

Pass `failure_category` through to the `AIFeedback` constructor. Add slug validation:

```python
VALID_CATEGORIES = {
    "wrong_info", "missing_info", "wrong_context",
    "outdated_info", "too_generic", "wrong_tone", "incomplete",
}
category = body.failure_category if body.failure_category in VALID_CATEGORIES else None
```

### UI Change

**File:** `ui/components/FeedbackButtons.js`

On thumbs-down click: before showing the correction textarea, render a single-select chip picker with all 7 categories. Selecting a category enables the Submit button. Category is required for negative feedback submission — the chip picker is compact (flexbox wrap, one row ideally), uses existing CSS variables (`--bg-2`, `--border`, `--text-2`), and highlights the selected chip with `--accent` or a subtle border change.

The chip picker appears between the thumbs-down button and the correction textarea:

```
👎 [selected]
┌─────────────────────────────────────────────────────┐
│ ❌ Wrong info  🔍 Missing info  ❌ Wrong context     │
│ 📅 Outdated   🎯 Too generic   📝 Wrong tone  ✂️ ... │
└─────────────────────────────────────────────────────┘
[optional correction text]
[Submit — disabled until category selected]
```

The POST to `/api/feedback` adds `failure_category` to the existing payload.

### Migration

**File:** `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py`

- `revision = "20260324_000003"`, `down_revision = "20260324_000002"`
- `upgrade()`: `ALTER TABLE ai_feedback ADD COLUMN failure_category VARCHAR(64)` + create `prompt_suggestions` table
- `downgrade()`: drop `prompt_suggestions`, drop `failure_category` column

---

## Area 2: `PromptSuggestion` Table

**File:** `api/app/models/feedback.py` — append after `ChunkQualitySignal`

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

---

## Area 3: Pattern Analysis Backend

Five new endpoints added to `api/app/api/routes/admin.py`.

### `GET /admin/feedback-patterns`

**Query params:** `days: int = 7` (lookback window)

Aggregates `AIFeedback` where `rating = 'negative'` AND `failure_category IS NOT NULL` AND `created_at >= now() - days`. Groups by `(mode, failure_category)`. Returns top 20 patterns sorted by count descending. Each row includes 2 example `query_text` values (the most recent).

**Response:**
```json
[
  {
    "mode": "oracle",
    "failure_category": "too_generic",
    "count": 5,
    "last_seen": "2026-03-23T10:15:00Z",
    "examples": ["What should I say on the Acme call?", "How do I position against Snowflake?"]
  }
]
```

### `GET /admin/feedback-alerts`

Checks for patterns that have crossed the suggestion threshold since the last suggestion was created (or dismissed) for that `(mode, failure_category)` pair.

**Logic:** For each `(mode, failure_category)` with any feedback, count failures since `MAX(last PromptSuggestion.created_at for this combo, now() - 7 days)`. Return combos where count ≥ `SUGGESTION_THRESHOLD` (env var, default `3`).

**Response:**
```json
[
  {
    "mode": "oracle",
    "failure_category": "too_generic",
    "count": 5,
    "threshold": 3
  }
]
```

### `POST /admin/feedback-suggestions`

**Body:** `{mode: str, failure_category: str, prompt_type: "persona"|"builtin"}`

1. Load the 5 most recent `AIFeedback` rows matching `(mode, failure_category)` — extract `query_text` and `original_response`.
2. Load the current prompt: for `prompt_type = "persona"`, read `KBConfig.persona_prompt`; for `builtin`, read the hardcoded system prompt constant for that mode from `services/llm.py` (mapped by mode name).
3. Call GPT-4 (`gpt-4o`) with a structured prompt asking it to:
   - Explain in 2–3 sentences why the current prompt produces this failure category
   - Suggest a specific edit to the prompt text (additions and/or removals)
   - Return JSON: `{reasoning: str, suggested_prompt: str}`
4. Save a `PromptSuggestion` row with `current_prompt`, `suggested_prompt`, `reasoning`, `mode`, `failure_category`, `prompt_type`.
5. Return the saved row.

**Error handling:** If GPT-4 call fails, return 502 with detail. Do not save a partial row.

### `POST /admin/feedback-suggestions/{id}/apply`

Route signature: `id: uuid.UUID` path parameter. FastAPI receives it as a string and must declare it as `uuid.UUID` so `db.get(PromptSuggestion, id)` resolves correctly.

1. Load `PromptSuggestion` by id. Return 404 if not found.
2. If `prompt_type = "persona"`: update `KBConfig.persona_prompt` to `suggestion.suggested_prompt` using the existing KBConfig update path.
3. If `prompt_type = "builtin"`: return 400 — built-in prompts require a code change and cannot be applied via API.
4. Set `applied_at = now()`. Return the updated suggestion.

### `POST /admin/feedback-suggestions/{id}/dismiss`

Route signature: `id: uuid.UUID` path parameter (same as apply).

Set `dismissed_at = now()`. Return 200.

**Threshold reset behaviour:** `GET /admin/feedback-alerts` counts failures since the most recent `PromptSuggestion.created_at` for each `(mode, failure_category)` combo, regardless of whether that suggestion was applied or dismissed. Because dismiss sets only `dismissed_at` (not `created_at`), the existing row's `created_at` already anchors the lookback window — the counter effectively resets to zero from that timestamp. No additional query filtering by `dismissed_at` is needed in the alerts endpoint.

---

## Area 4: Dashboard UI (`/admin/feedback`)

**File:** `ui/app/(app)/admin/feedback/page.js` (new page)

**Page load:** Call `GET /api/admin/feedback-alerts` and `GET /api/admin/feedback-patterns`. Render synchronously — no client-side loading spinners needed for initial data.

### Layout (top to bottom)

**Alert banners** (one per alert from `feedback-alerts`):
- Yellow background, warning icon
- Text: `{count} failures in {mode} — "{category label}" since last analysis`
- "View suggestion" button → calls `POST /admin/feedback-suggestions` with `prompt_type="persona"` → expands the suggestion panel for that row in the table below

**Stats row** (4 KPI cards):
- Negative feedback count (last 7d)
- Top failing mode
- Most common failure category
- Suggestions applied (total count of `applied_at IS NOT NULL`)

**Failure patterns table**:
- Columns: Mode, Category, Count (7d), Last seen, Action
- "Suggest fix" action → calls `POST /admin/feedback-suggestions` → expands inline suggestion panel below the row
- Sorted by count descending

**Suggestion panel** (expands inline below its triggering row):
- Reasoning block (left-bordered, GPT-4's explanation)
- Full prompt with inline diff: additions in green highlight, removals in red strikethrough
- Built-in prompt advisory section (grey border, "requires code change", shows constant name + file path)
- Buttons: "Apply to persona prompt" (disabled for builtin), "Copy advisory", "Dismiss"

### Next.js API Proxies

```
ui/app/api/admin/feedback-patterns/route.js
ui/app/api/admin/feedback-suggestions/route.js
ui/app/api/admin/feedback-suggestions/[id]/apply/route.js
ui/app/api/admin/feedback-suggestions/[id]/dismiss/route.js
ui/app/api/admin/feedback-alerts/route.js
```

Each follows the existing admin proxy pattern: forward request to backend API with `X-OpenAI-Token: session.access_token` header, matching `ui/app/api/admin/kb-config/route.js`. Do not use the feedback proxy pattern (`X-User-Email`) for these admin routes.

---

## Mode → Built-in Prompt Mapping

Used by `POST /admin/feedback-suggestions` to read the current built-in prompt for a mode. Constants are defined in `api/app/prompts/templates.py` and imported into `services/llm.py` from there. Implementation must import from `app.prompts.templates`.

| Mode value | Constant | File |
|---|---|---|
| `oracle` | `SYSTEM_ORACLE` | `api/app/prompts/templates.py` |
| `call_assistant` | `SYSTEM_CALL_COACH` | `api/app/prompts/templates.py` |
| `rep` | `SYSTEM_REP_EXECUTION` | `api/app/prompts/templates.py` |
| `se` | `SYSTEM_SE_EXECUTION` | `api/app/prompts/templates.py` |
| `marketing` | `SYSTEM_MARKETING_EXECUTION` | `api/app/prompts/templates.py` |

Phase 1 covers these five modes. Other system prompts (`SYSTEM_SE_ANALYSIS`, `SYSTEM_PRE_CALL_INTEL`, etc.) are out of scope.

---

## Data Flow Summary

```
User clicks 👎
    ├─ Category chip picker appears
    ├─ User selects category + optional correction
    └─ POST /api/feedback {rating, failure_category, correction, citations, audit_id}
           └─ Writes AIFeedback + ChunkQualitySignal rows (existing)

Admin loads /admin/feedback
    ├─ GET /api/admin/feedback-alerts → check thresholds → show banners
    └─ GET /api/admin/feedback-patterns → show pattern table

Admin clicks "View suggestion" or "Suggest fix"
    └─ POST /api/admin/feedback-suggestions {mode, failure_category, prompt_type}
           ├─ Load recent failures + current prompt
           ├─ Call GPT-4 → {reasoning, suggested_prompt}
           ├─ Save PromptSuggestion row
           └─ Return suggestion → render inline diff panel

Admin clicks "Apply to persona prompt"
    └─ POST /api/admin/feedback-suggestions/{id}/apply
           ├─ Update KBConfig.persona_prompt
           └─ Set applied_at

Admin clicks "Dismiss"
    └─ POST /api/admin/feedback-suggestions/{id}/dismiss
           └─ Set dismissed_at → resets threshold counter
```

---

## Files Changed

| File | Change |
|---|---|
| `api/app/models/feedback.py` | `failure_category` on `AIFeedback`; new `PromptSuggestion` model |
| `api/app/schemas/feedback.py` | `failure_category` on `FeedbackCreate` |
| `api/app/api/routes/feedback.py` | Slug validation + pass `failure_category` to `AIFeedback` |
| `api/app/api/routes/admin.py` | 5 new endpoints |
| `api/alembic/versions/20260324_000003_add_failure_category_and_prompt_suggestions.py` | Migration |
| `ui/components/FeedbackButtons.js` | Category chip picker on thumbs-down |
| `ui/app/(app)/admin/feedback/page.js` | New dashboard page |
| `ui/app/api/admin/feedback-patterns/route.js` | Next.js proxy |
| `ui/app/api/admin/feedback-suggestions/route.js` | Next.js proxy |
| `ui/app/api/admin/feedback-suggestions/[id]/apply/route.js` | Next.js proxy |
| `ui/app/api/admin/feedback-suggestions/[id]/dismiss/route.js` | Next.js proxy |
| `ui/app/api/admin/feedback-alerts/route.js` | Next.js proxy |

---

## What This Does Not Include

- Background/scheduled pattern analysis (Vercel-incompatible)
- Fine-tuning or modifying the OpenAI model
- Automatic prompt application without admin review
- Phase 2: chunking strategy retraining (deferred — requires real usage data first)
