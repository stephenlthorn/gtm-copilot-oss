# Two-Stage Intelligence Brief Design

**Date:** 2026-03-23
**Status:** Approved

---

## Goal

Replace the single-pass pre-call intel flow with a two-stage pipeline: a fast, cheap summarizer model (GPT-5.4 Mini) condenses each query's raw search results into focused paragraphs, then a capable synthesis model (GPT-5.4 with medium thinking) produces the final brief from those summaries. This keeps the synthesis context window lean while preserving data richness. All four model/thinking parameters are user-configurable from the Settings page.

---

## Architecture

The two-stage flow is self-contained inside `_deep_research_pre_call()` in `api/app/services/llm.py`. No new service files are needed. The Firecrawl query logic is untouched; only the result-assembly step changes.

**Stage 1 — Per-query summarization (new)**
A new helper `_summarize_query_results()` receives the list of `(query_label, snippets)` pairs produced by the 8 Firecrawl searches. It fires one Mini call per query using `ThreadPoolExecutor`, all in parallel. Each call receives a compact system prompt ("You are a B2B research analyst...") and a user message containing the query label and its raw snippets. It returns a focused paragraph of key findings for that query. If any individual call fails, that slot falls back to the raw truncated snippets — graceful per-call degradation, not total failure.

**Stage 2 — Synthesis (existing, reconfigured)**
The 8 summary paragraphs (or raw fallbacks) are compiled into a structured markdown block that replaces the current raw-snippet input to the synthesis call. The synthesis call continues to use `_responses_text()` with streaming. Model and thinking level are now read from user preferences (`intel_brief_synthesis_model`, `intel_brief_synthesis_effort`) instead of hardcoded values.

**Toggle**
When `intel_brief_enabled` is `False`, the `_summarize_query_results()` call is skipped. Everything else in `_deep_research_pre_call()` — the Firecrawl loop, competitive-alert block construction, STRICT/ALLOWED grounding rules, verbatim-copy instructions in `synthesize_prompt`, and the `_responses_text()` synthesis call — runs exactly as it does today. Only the new summarization step and summary-block compilation are bypassed; the raw-snippet markdown block is used for the synthesis call as before.

**Parameter threading**
The 5 new intel-brief preference values are passed as explicit scalar kwargs through the call chain — matching the existing pattern for `model` and `reasoning_effort`. The orchestrator unpacks them from `user_prefs` and passes them to `answer_oracle()`, which passes them to `_deep_research_pre_call()`. No `user_pref` object is passed; only the resolved scalar values flow down. Specifically, `answer_oracle()` gains 5 new optional parameters: `intel_brief_enabled: bool = True`, `intel_brief_summarizer_model: str = "gpt-5.4-mini"`, `intel_brief_summarizer_effort: str | None = None`, `intel_brief_synthesis_model: str = "gpt-5.4"`, `intel_brief_synthesis_effort: str = "medium"`. These are forwarded to `_deep_research_pre_call()` with the same names.

---

## Data Flow

```
8 Firecrawl queries (existing, unchanged)
    ↓  list of (label, [snippets])
_summarize_query_results()          ← NEW
    ThreadPoolExecutor (8 parallel Mini calls)
    per-call fallback: raw snippets on error
    ↓  list of (label, summary_paragraph)
Compile into structured markdown block
    ↓
_responses_text(
    system=resolve_for_section("pre_call"),
    user=brief_prompt + summaries_block,
    model=intel_brief_synthesis_model,   ← scalar kwarg
    reasoning_effort=intel_brief_synthesis_effort  ← scalar kwarg
)  → streamed to client
```

---

## Database

### Migration

Add 5 columns to `user_preferences` table:

| Column | Type | Default | Nullable |
|---|---|---|---|
| `intel_brief_enabled` | Boolean | `True` | No |
| `intel_brief_summarizer_model` | String(64) | `"gpt-5.4-mini"` | Yes |
| `intel_brief_summarizer_effort` | String(16) | `None` | Yes |
| `intel_brief_synthesis_model` | String(64) | `"gpt-5.4"` | Yes |
| `intel_brief_synthesis_effort` | String(16) | `"medium"` | Yes |

Migration file: `api/alembic/versions/20260323_000002_add_intel_brief_prefs.py`

`down_revision` must be set to `"20260323_000001"` (the prompt studio migration). Before writing this migration, verify whether `retrieval_top_k` already exists in the live `user_preferences` table — it is present in `UserPreference` model but may be absent from the `20260316_000001` DDL. If missing, add it in this migration as well (`Integer, nullable=True, server_default=None`) to keep model and DB in sync.

### Model changes

`UserPreference` in `api/app/models/entities.py` — add 5 `Mapped` fields with `server_default` values matching the table defaults above.

### Schema changes

5 new fields added to both `UserPrefRead` and `UserPrefUpdate` in `api/app/schemas/user_prefs.py`. All 5 fields optional in `UserPrefUpdate` (using `| None` with `None` default). `UserPrefRead` includes them as optional with `None` default so existing records without these values deserialise cleanly.

---

## API

No new endpoints. The existing `GET /user/preferences` and `PUT /user/preferences` routes in `api/app/api/routes/user_prefs.py` pick up the new fields automatically via the updated Pydantic schemas.

The 5 new intel-brief values are unpacked from `user_prefs` by the orchestrator and passed as scalar kwargs to `answer_oracle()`, which forwards them to `_deep_research_pre_call()`. See **Parameter threading** in the Architecture section for the full parameter names and defaults.

---

## `llm.py` Changes

### New helper: `_summarize_query_results()`

```python
def _summarize_query_results(
    query_results: list[tuple[str, list[str]]],
    *,
    model: str = "gpt-5.4-mini",
    reasoning_effort: str | None = None,
    client,
) -> list[tuple[str, str]]:
    """
    For each (label, snippets) pair, fire a Mini call to produce a summary paragraph.
    Runs all calls in parallel via ThreadPoolExecutor.
    Falls back to joined raw snippets on per-call error.
    """
```

**System prompt for Mini:**
```
You are a B2B research analyst. Given a set of web search results for a specific
research query, extract and summarize the key findings into a single concise paragraph.
Focus on: company information, technical signals, pain points, business context,
and competitive indicators. Omit filler, ads, and irrelevant content.
Be specific — include company names, numbers, product names where present.
```

**User message per call:**
```
Query: {label}

Search results:
{snippet_1}
---
{snippet_2}
---
...
```

**Returns:** `(label, summary_paragraph)` — or `(label, raw_joined_snippets)` on error.

### Modified: `_deep_research_pre_call()`

After collecting all 8 query results and before building the synthesis prompt:

1. Check the `intel_brief_enabled` scalar kwarg (default `True`)
2. If enabled: call `_summarize_query_results()` passing the `intel_brief_summarizer_model` and `intel_brief_summarizer_effort` scalar kwargs
3. Compile summaries into markdown block (replaces current raw-snippet assembly)
4. Pass to synthesis call using the `intel_brief_synthesis_model` and `intel_brief_synthesis_effort` scalar kwargs

---

## Settings UI

### Location

New sub-section "Intelligence Brief" inside the existing **AI Behavior** (`#ai`) section of `ui/app/(app)/settings/page.js`, below the existing model/effort pickers.

### Controls

```
Intelligence Brief
──────────────────────────────────────────
[toggle] Two-stage summarization          ← intel_brief_enabled

  (shown only when toggle is on)
  Summarizer model    [gpt-5.4-mini ▾]   ← intel_brief_summarizer_model
  Summarizer thinking [None ▾]            ← intel_brief_summarizer_effort
  Synthesis model     [gpt-5.4 ▾]        ← intel_brief_synthesis_model
  Synthesis thinking  [Medium ▾]          ← intel_brief_synthesis_effort
```

- Toggle uses the existing inline toggle pattern from the settings page
- Model dropdowns reuse `ModelPickerDropdown` (or equivalent inline select)
- Thinking dropdowns: options are `None` / `Low` / `Medium` / `High` (None only available for summarizer)
- Each control saves on change via `PUT /api/user/preferences`
- No new API endpoints or route handlers needed

---

## Error Handling

| Failure | Behaviour |
|---|---|
| Individual Mini call fails | That query slot uses raw joined snippets (logged as warning) |
| All Mini calls fail | Full fallback to raw-snippet assembly (existing behaviour) |
| `intel_brief_enabled` is `False` | Stage 1 skipped entirely, existing path runs |
| Prefs not available | Defaults applied: enabled=True, summarizer=gpt-5.4-mini, synthesis=gpt-5.4+medium |

---

## Testing

### Unit tests (`tests/unit/test_intel_brief.py`)

- `test_summarize_query_results_calls_mini_per_query` — mock client, verify one call per query
- `test_summarize_query_results_fallback_on_error` — mock one call failing, verify raw fallback
- `test_summarize_query_results_all_fail` — all calls fail, all slots use raw fallback
- `test_deep_research_uses_summaries_when_enabled` — mock Firecrawl + summarizer, verify synthesis sees summary paragraphs not raw snippets
- `test_deep_research_skips_summaries_when_disabled` — `intel_brief_enabled=False`, verify synthesis sees raw snippets

### Migration test

- `test_user_preference_new_fields_have_correct_defaults` — create `UserPreference` without new fields, verify defaults apply

---

## Out of Scope

- Summarization for post-call or follow-up sections (pre-call only)
- Per-result granularity (per-query batch is the chosen approach)
- Caching Mini summaries across requests
- Streaming progress updates for Stage 1 to the client
