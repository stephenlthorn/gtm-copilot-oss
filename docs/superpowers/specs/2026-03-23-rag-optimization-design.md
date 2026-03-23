# RAG Optimization Design

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Three coordinated improvements to retrieval quality, context window management, and feedback loops — targeting beta launch on Vercel Pro + TiDB Cloud.

---

## Background

The current `HybridRetriever` pipeline retrieves 200–320 candidates, scores them with a weighted hybrid formula (`0.50*vec + 0.30*kw + 0.10*title + source_bias + domain_boost`), and returns up to 20 chunks to the LLM. Three problems exist before beta:

1. **Noise in LLM context:** Chunks 10–20 frequently score 0.10–0.15 (tangentially related) and still reach the prompt, diluting the answer.
2. **Uncontrolled token injection:** Context assembly uses hard-coded slice patterns (`hits[:8]`, `hits[:10]`, `hits[:20]`) with no token budget — silent truncation occurs when model context limits are hit.
3. **No chunk-level quality signal:** `AuditLog` captures which chunks were retrieved per query and `AIFeedback` captures ratings, but nothing connects them — it's unknown which specific chunks help vs. hurt output quality.

**Infrastructure constraint:** All logic must be stateless and Vercel Pro-compatible (no background jobs, no local model inference, no long-running processes). Storage is TiDB Cloud (MySQL-compatible).

---

## Area 1: Score Threshold Filter

### Goal
Prevent low-signal chunks from reaching the LLM context window.

### Implementation

**Location:** `api/app/retrieval/service.py` — `HybridRetriever.search()`, after the scoring loop and before the `scored[:top_k]` slice.

**Logic:**
```python
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.12"))
scored = [(s, c, d) for s, c, d in scored if s >= MIN_SCORE]
```

Call-focused primary-doc chunks score `1.0 - (chunk_index * 0.0001)` and always pass. The threshold only eliminates tail noise from secondary sources.

**Configuration:** `RAG_MIN_SCORE` environment variable, default `0.12`. Allows tuning without code changes based on observed score distributions in `AuditLog`.

**Zero-results guard:** If all chunks are filtered out (e.g., highly specific query with no relevant corpus), `search()` returns an empty list — existing behavior, no special handling needed.

### Metrics
- **Avg chunks reaching LLM per query** — target: reduce from 20 → 8–12
- **Zero-results rate** — alert if > 5% of queries (threshold too aggressive)
- Both readable from `AuditLog.retrieval_json` (existing field, already logs chunk count)

---

## Area 2: Context Window Management

### Goal
Enforce token budgets on retrieved context before LLM injection, and ensure most-relevant chunks appear earliest in the prompt.

### Implementation

**Location:** `api/app/services/llm.py` — all context assembly functions. There are eleven context-injection slice sites across the file using three different patterns:
- `hits[:20]` — one occurrence (`answer_oracle`, line ~1203)
- `hits[:10]` — one occurrence (`answer_marketing_intelligence`)
- `hits[:8]` — nine occurrences (all other `answer_*` functions)

Note: there is also a `hits[:3]` at line ~1271 inside `answer_call_assistant`'s LLM-failure fallback path — this extracts short text quotes for a degraded structured return value and is **not** an LLM context-injection site. It is intentionally excluded from this change.

All eleven context-injection sites are replaced by calls to a new shared `_assemble_context()` helper.

**`token_count` on `RetrievedChunk`:** The assembler needs per-chunk token counts. `KBChunk.token_count` exists in the ORM model but is not currently copied into `RetrievedChunk`. Add `token_count: int` to the `RetrievedChunk` dataclass (`api/app/retrieval/types.py`) and populate it from `chunk.token_count` in the `HybridRetriever.search()` result-assembly loop (`service.py` lines ~419–438).

**Assembler helper:**
```python
def _assemble_context(hits: list[RetrievedChunk], token_budget: int) -> list[RetrievedChunk]:
    used = 0
    selected = []
    for chunk in hits:  # already sorted by score descending
        if used + chunk.token_count > token_budget:
            break
        selected.append(chunk)
        used += chunk.token_count
    return selected
```

**Token budgets per function:**

| Function(s) | Token budget |
|---|---|
| `answer_oracle` | 6,000 tokens |
| `answer_rep_account_brief`, `answer_rep_discovery_questions`, `answer_rep_follow_up_draft`, `answer_rep_deal_risk` | 10,000 tokens |
| `answer_se_poc_plan`, `answer_se_poc_readiness`, `answer_se_architecture_fit`, `answer_se_competitor_coach` | 10,000 tokens |
| `answer_marketing_intelligence` | 10,000 tokens |
| Call-focused primary doc chunks | Unlimited (existing no-cap behavior preserved — prepended before budget loop) |

**Relevance-first ordering:** All `answer_*` functions consume `hits` in the order returned by `search()`, which is already score-descending — no change needed. Call-focused chunks are score-encoded via `1.0 - index*0.0001` so transcript order is preserved as a sort tiebreaker.

**Token count source:** `chunk.token_count` on `RetrievedChunk` (populated from `KBChunk.token_count`, stored at ingest as `max(1, int(len(text.split()) * 1.3))`). No re-computation at query time.

### Metrics
- **Context token utilization per query** — tokens used / budget (log in `AuditLog.retrieval_json`)
- **Truncation events** — count of queries where assembler stopped before exhausting `hits` (previously silent, now observable)

---

## Area 3: Feedback Loop (Closed Loop)

### Goal
Connect chunk-level retrieval events to query outcome ratings, surface which chunks consistently help vs. hurt, and apply a small quality adjustment to future retrieval scores.

### New Table: `ChunkQualitySignal`

**Location:** `api/app/models/feedback.py` — alongside `AIFeedback`, which is the related model. The FK target (`kb_chunks.id`) lives in `entities.py`; cross-file FKs are already used in this codebase.

```python
class ChunkQualitySignal(Base):
    __tablename__ = "chunk_quality_signals"

    id: Mapped[UUID_TYPE] = mapped_column(UUID_TYPE, primary_key=True, default=_uuid)
    chunk_id: Mapped[UUID_TYPE] = mapped_column(UUID_TYPE, ForeignKey("kb_chunks.id", ondelete="CASCADE"), index=True)
    signal: Mapped[str] = mapped_column(String(32))   # "cited_positive" | "cited_negative" | "retrieved_unused"
    query_mode: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

Use `UUID_TYPE` and `_uuid` imported from `app.models.entities` — the same pattern used by `AIFeedback` and every other model in this codebase. Raw `Mapped[UUID]` / `default=uuid4` will fail on TiDB Cloud (MySQL-compatible) which requires explicit binary/string UUID column typing.

New Alembic migration: `20260324_000002_add_chunk_quality_signals.py`.

### Schema Changes Required

`FeedbackCreate` (`api/app/schemas/feedback.py`) must be extended with two new optional fields:

```python
citations: list[str] | None = None   # chunk UUIDs cited in the response
audit_id: str | None = None          # UUID of the AuditLog row for this query
```

These fields are added client-side when the UI submits a rating — the chat response already returns `citations[]` with `chunk_id`. The `audit_id` is returned alongside the chat response for correlation. Both fields are optional to preserve backwards compatibility with existing rating submissions.

### Write Path

**Location:** `api/app/api/routes/feedback.py` — the route that writes `AIFeedback`.

At rating time:

1. If `audit_id` is provided, load that `AuditLog` row directly. Otherwise look up by `AuditLog.actor = user_email AND AuditLog.timestamp BETWEEN created_at - 60s AND created_at + 60s` (fallback for older clients).
2. For each chunk UUID in `request.citations`: write `cited_positive` or `cited_negative` based on `request.rating`.
3. For each chunk UUID in `AuditLog.retrieval_json["results"]` not in `request.citations`: write `retrieved_unused`.

All writes are synchronous at rating time — no background job needed, Vercel-compatible.

### Read Path (Closed Loop)

**Location:** `HybridRetriever.search()`, applied to the `scored` list after the scoring loop but before the threshold filter. Only chunks that survive `score > 0` (the existing guard in `service.py`) are in `scored` — chunks scored exactly 0 are excluded before this step and are not recoverable by quality signals (intentional: a zero hybrid score means no semantic or lexical match).

For chunks with ≥ 10 quality signals:

```python
positive_rate = cited_positive_count / (cited_positive_count + cited_negative_count)
score += 0.05 * (positive_rate - 0.5)  # range: -0.025 to +0.025
```

The nudge is capped at ±0.025 to prevent quality signals from overriding the primary hybrid score. Chunks with < 10 signals receive no adjustment (cold-start protection).

**Query:** A single bulk SQL join fetches quality signal aggregates for all candidate chunk IDs before scoring — one extra query per search call, not N per chunk.

### Passive Analytics

A SQL view `v_chunk_quality` joins `AuditLog` + `AIFeedback` on:
```sql
AuditLog.actor = AIFeedback.user_email
AND AuditLog.timestamp BETWEEN AIFeedback.created_at - INTERVAL 60 SECOND
                            AND AIFeedback.created_at + INTERVAL 60 SECOND
```

This surfaces chunks that frequently co-occur with negative ratings — useful for manual review before `ChunkQualitySignal` accumulates enough data.

Exposing this view via `/admin` requires a new route handler in `api/app/api/routes/admin.py` — it does not exist today and must be added.

### Metrics
- **Corpus coverage** — % of active chunks with ≥ 10 quality signals (target: 30% within first 2 weeks of beta)
- **Positive rate distribution** — median positive rate across scored chunks (healthy system: > 0.70)
- **Retrieved-unused rate per source_type** — high rate indicates a source type contributes noise (actionable for chunking strategy)
- All metrics derivable from `ChunkQualitySignal` table with simple GROUP BY queries

---

## Data Flow Summary

```
Search request
    ↓
HybridRetriever.search()
    ├─ Retrieve 200–320 candidates (unchanged)
    ├─ Score with hybrid formula (unchanged)
    ├─ Apply ChunkQualitySignal nudge (±0.025, score>0 chunks with ≥10 signals)  [NEW]
    ├─ Filter: drop chunks below RAG_MIN_SCORE=0.12                              [NEW]
    └─ Return top_k (or all primary-call chunks if call-focused)

Context assembly in api/app/services/llm.py
    ├─ Prepend call-focused primary chunks (existing, no token cap)
    ├─ Fill from remaining hits in score order until token budget exhausted       [NEW]
    └─ Assemble prompt string

Response returned to user (includes citations[] with chunk_id, audit_id)

Rating submitted (/feedback)
    ├─ Write AIFeedback (existing)
    └─ Write ChunkQualitySignal rows (cited_positive/negative, retrieved_unused)  [NEW]
```

---

## Files Changed

| File | Change |
|---|---|
| `api/app/retrieval/service.py` | Score threshold filter + quality signal nudge in `search()`; add `token_count` to result-assembly loop |
| `api/app/retrieval/types.py` | Add `token_count: int` to `RetrievedChunk` dataclass |
| `api/app/services/llm.py` | Add `_assemble_context()` helper; replace all 11 slice sites (`hits[:8]`, `hits[:10]`, `hits[:20]`) with budget-aware calls |
| `api/app/models/feedback.py` | Add `ChunkQualitySignal` model |
| `api/app/schemas/feedback.py` | Add `citations: list[str] | None` and `audit_id: str | None` to `FeedbackCreate` |
| `api/app/api/routes/feedback.py` | Write `ChunkQualitySignal` rows at rating time |
| `api/app/api/routes/admin.py` | Add route handler exposing `v_chunk_quality` SQL view |
| `api/alembic/versions/20260324_000002_add_chunk_quality_signals.py` | Migration for new table |
| `api/tests/unit/test_rag_optimization.py` | Unit tests for all three areas |

---

## What This Does Not Include

- Cross-encoder reranking (deferred post-beta; requires external API or local model)
- Background analytics jobs (Vercel-incompatible)
- Changes to embedding model or chunking strategy (separate concern)
- UI changes (metrics are admin/internal only)
