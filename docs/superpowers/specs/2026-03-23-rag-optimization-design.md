# RAG Optimization Design

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Three coordinated improvements to retrieval quality, context window management, and feedback loops — targeting beta launch on Vercel Pro + TiDB Cloud.

---

## Background

The current `HybridRetriever` pipeline retrieves 200–320 candidates, scores them with a weighted hybrid formula (`0.50*vec + 0.30*kw + 0.10*title + source_bias + domain_boost`), and returns up to 20 chunks to the LLM. Three problems exist before beta:

1. **Noise in LLM context:** Chunks 10–20 frequently score 0.10–0.15 (tangentially related) and still reach the prompt, diluting the answer.
2. **Uncontrolled token injection:** Context assembly does `hits[:20]` with no token budget — silent truncation occurs when model context limits are hit.
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

**Location:** `api/app/llm.py` — context assembly functions that currently do `hits[:20]`.

**Token budgets per mode:**

| Mode | Token budget |
|---|---|
| oracle, chat | 6,000 tokens |
| account-brief, discovery-questions, follow-up, deal-risk | 10,000 tokens |
| poc-plan, poc-readiness, architecture-fit, competitor-coach | 10,000 tokens |
| call-focused primary doc | Unlimited (existing no-cap behavior preserved) |

**Assembler logic (replaces `hits[:20]`):**
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

Call-focused primary-doc chunks are prepended before the budget loop (they already bubble to the top via the `1.0 - index*0.0001` score). The token budget applies only to the secondary chunks that follow.

**Relevance-first ordering:** `answer_oracle()` currently consumes `hits` in score order — correct, no change needed. Call-focused chunks return in `chunk_index` (transcript) order from the DB; these are already score-ordered via the `1.0 - index*0.0001` encoding, so transcript order is preserved as the sort tiebreaker at no extra cost.

**Token count source:** `KBChunk.token_count` (already stored at ingest time as `max(1, int(len(text.split()) * 1.3))`). No additional computation at query time.

### Metrics
- **Context token utilization per query** — tokens used / budget (log in `AuditLog.retrieval_json`)
- **Truncation events** — count of queries where assembler stopped before exhausting `hits` (previously silent, now observable)

---

## Area 3: Feedback Loop (Closed Loop)

### Goal
Connect chunk-level retrieval events to query outcome ratings, surface which chunks consistently help vs. hurt, and apply a small quality adjustment to future retrieval scores.

### New Table: `ChunkQualitySignal`

**Location:** `api/app/models/entities.py`

```python
class ChunkQualitySignal(Base):
    __tablename__ = "chunk_quality_signals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("kb_chunks.id", ondelete="CASCADE"), index=True)
    signal: Mapped[str] = mapped_column(String(32))   # "cited_positive" | "cited_negative" | "retrieved_unused"
    query_mode: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

New Alembic migration: `20260324_000002_add_chunk_quality_signals.py`.

### Write Path

**Location:** `/feedback` endpoint (the route that writes `AIFeedback`).

At rating time, the response payload already includes `citations[]` with `chunk_id` and `AuditLog.retrieval_json` contains the full set of retrieved chunk IDs for that query. The write path:

1. Look up the `AuditLog` row for this query (by `actor` + `timestamp` within 60 seconds, or pass `audit_id` in the rating request).
2. For each chunk in `citations[]`: write `cited_positive` or `cited_negative` based on rating.
3. For each chunk in `retrieval_json.results` not in `citations[]`: write `retrieved_unused`.

All writes are synchronous at rating time — no background job needed, Vercel-compatible.

### Read Path (Closed Loop)

**Location:** `HybridRetriever.search()`, after the scoring loop, before the threshold filter.

For chunks with ≥ 10 quality signals, apply a small score nudge:

```python
positive_rate = cited_positive_count / (cited_positive_count + cited_negative_count)
score += 0.05 * (positive_rate - 0.5)  # range: -0.025 to +0.025
```

The nudge is capped at ±0.025 to prevent quality signals from overriding the primary hybrid score. Chunks with < 10 signals receive no adjustment (cold-start protection).

**Query:** A single bulk SQL join fetches quality signal aggregates for all candidate chunk IDs before scoring — one extra query per search, not N per chunk.

### Passive Analytics

A SQL view `v_chunk_quality` joins `AuditLog` + `AIFeedback` by `(actor, timestamp within 60s)` to surface chunks that frequently co-occur with negative ratings — useful for manual review before the `ChunkQualitySignal` table has enough data.

Readable from the existing `/admin` endpoint.

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
    ├─ Apply ChunkQualitySignal nudge (±0.025, chunks with ≥10 signals only)  [NEW]
    ├─ Filter: drop chunks below RAG_MIN_SCORE=0.12                           [NEW]
    └─ Return top_k (or all primary-call chunks if call-focused)

Context assembly in llm.py
    ├─ Prepend call-focused primary chunks (existing, no token cap)
    ├─ Fill from remaining hits in score order until token budget exhausted    [NEW]
    └─ Assemble prompt string

Response returned to user

Rating submitted (/feedback)
    ├─ Write AIFeedback (existing)
    └─ Write ChunkQualitySignal rows (cited_positive/negative, retrieved_unused) [NEW]
```

---

## Files Changed

| File | Change |
|---|---|
| `api/app/retrieval/service.py` | Score threshold filter + quality signal nudge in `search()` |
| `api/app/llm.py` | Replace `hits[:20]` with `_assemble_context()` using token budgets |
| `api/app/models/entities.py` | Add `ChunkQualitySignal` model |
| `api/app/routers/feedback.py` | Write `ChunkQualitySignal` rows at rating time |
| `api/alembic/versions/20260324_000002_add_chunk_quality_signals.py` | Migration for new table |
| `api/tests/unit/test_rag_optimization.py` | Unit tests for all three areas |

---

## What This Does Not Include

- Cross-encoder reranking (deferred post-beta; requires external API or local model)
- Background analytics jobs (Vercel-incompatible)
- Changes to embedding model or chunking strategy (separate concern)
- UI changes (metrics are admin/internal only)
