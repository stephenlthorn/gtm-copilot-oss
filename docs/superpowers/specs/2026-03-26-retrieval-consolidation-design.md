# Retrieval Consolidation + Feishu Integration Design

**Date:** 2026-03-26
**Status:** Approved
**Scope:** Consolidate `kb_chunks` → `knowledge_index`, activate Feishu (Drive + Wiki), add HNSW vector index

---

## Overview

Two parallel retrieval systems exist today. `kb_chunks` is the legacy table used by `HybridRetriever`; `knowledge_index` is the new table used by `HybridRetrievalService`. Neither has all the infrastructure it needs:

- `knowledge_index` is missing its HNSW vector index (queries are doing full table scans)
- `kb_chunks` has HNSW but retrieval uses Python-based cosine similarity instead of TiDB's native vector search
- Feishu connector exists but only covers Drive folders, not Wiki spaces

This spec consolidates everything to `knowledge_index` with a zero-downtime migration, adds the missing vector index, and activates Feishu Drive + Wiki ingestion.

---

## Goals

1. Add HNSW vector index to `knowledge_index`
2. Stop all new ingestion from writing to `kb_chunks`
3. Backfill existing `kb_chunks` content into `knowledge_index` via Celery
4. Fan out retrieval to both tables during migration; cut over automatically on completion
5. Activate Feishu integration (Drive folders + Wiki spaces)
6. Retire `kb_chunks` after a 7-day safety hold

---

## Non-Goals (this milestone)

- **FTS / FULLTEXT indexes** — deferred until TiDB cluster migrates to Frankfurt or Singapore region (planned next week). The new `fts_match_word()` + `WITH PARSER MULTILINGUAL` is not available in us-east.
- Changes to the RAG pipeline above the retrieval layer
- UI changes

---

## Section 1 — Schema: Add HNSW Vector Index

Single Alembic migration targeting `knowledge_index`.

```sql
ALTER TABLE knowledge_index
  ADD VECTOR INDEX idx_ki_embedding
  ((VEC_COSINE_DISTANCE(embedding)))
  USING HNSW;
```

No column changes — `embedding`, `content`, `source_type`, `source_id`, `title`, `url`, `metadata` are sufficient.

**New runtime config flag:**

`RETRIEVAL_CUTOVER` must be stored in the `kb_config` database table (not `.env`) so that the Celery worker and API process both read the live value without a restart. The backfill task calls `set_runtime_config('RETRIEVAL_CUTOVER', 'true')` which writes to `kb_config`, and the retrieval fan-out reads it per-request via `get_runtime_config('RETRIEVAL_CUTOVER')`. Do not use `os.getenv()` for this flag.

**FTS drop-in (after region migration, next week):**

```sql
ALTER TABLE knowledge_index
  ADD FULLTEXT INDEX idx_ki_fts (content)
  WITH PARSER MULTILINGUAL;
```

Then set `fts_enabled=True` in `HybridRetrievalService`. No other changes needed.

---

## Section 2 — Ingestion Layer: Stop Writing to `kb_chunks`

All ingestors (Drive, Chorus, Feishu) stop writing to `kb_chunks`. Write to `knowledge_index` only.

**Changes per ingestor:**
- Remove any call to the legacy ingestor path that targets `kb_chunks`
- `feishu_indexer.py` already writes to `knowledge_index` — verify it is not also calling the legacy ingestor, then leave it as-is

`kb_chunks` becomes read-only after this deploy. No application code writes to it.

---

## Section 3 — Celery Backfill Task

A low-priority, self-chaining Celery task migrates all existing `kb_chunks` rows to `knowledge_index`.

```python
@celery_app.task(
    name='tasks.backfill_knowledge_index',
    bind=True,
    max_retries=None,
    rate_limit='10/m'
)
def backfill_knowledge_index(self, offset=0, batch_size=500):
    rows = db.query(KbChunk).offset(offset).limit(batch_size).all()
    if not rows:
        # Migration complete — activate cutover
        set_runtime_config('RETRIEVAL_CUTOVER', 'true')
        return

    for row in rows:
        # Upsert: skip if source_id already exists (e.g. Feishu docs already indexed)
        upsert_knowledge_index(row)

    # Chain next batch with 2s pause to avoid hammering DB
    backfill_knowledge_index.apply_async(
        kwargs={'offset': offset + batch_size},
        countdown=2
    )
```

**Key properties:**
- Idempotent — safe to restart if it crashes mid-migration
- Deduplicates by `source_id` to handle docs already in `knowledge_index`
- Self-terminates and flips `RETRIEVAL_CUTOVER` on completion
- Triggered once after deploy: `celery call tasks.backfill_knowledge_index`

**Progress monitoring:**

```
GET /admin/backfill-status
→ { kb_chunks_remaining: N, knowledge_index_count: M }
```

---

## Section 4 — Retrieval Fan-out During Transition

During the backfill period, documents exist in both tables. `HybridRetrievalService` (or a thin wrapper) queries both and merges results.

```python
def retrieve(query_embedding, query_text, top_k):
    new_results = query_knowledge_index(query_embedding, top_k)

    if os.getenv('RETRIEVAL_CUTOVER') == 'true':
        return new_results

    # Fan out to legacy during transition
    legacy_results = query_kb_chunks(query_embedding, top_k)

    # Merge: deduplicate by source_id, keep highest score
    merged = deduplicate_by_source_id(new_results + legacy_results)
    return sorted(merged, key=lambda r: r.score, reverse=True)[:top_k]
```

`RETRIEVAL_CUTOVER` is a runtime env var — no deploy needed when it flips. The backfill task sets it automatically.

---

## Section 5 — Feishu Integration

### Current State

The connector handles authentication and document content fetching. It supports Drive folders only. The indexer (`feishu_indexer.py`) writes to `knowledge_index`.

**Gap:** No wiki space support. The user's content lives in Feishu Wiki (`https://pingcap.feishu.cn/wiki/`), not Drive folders.

### Required: Wiki Space Extension

Add a wiki discovery layer to `feishu_connector.py`:

```python
# New: list all wiki spaces the app has access to
GET /wiki/v2/spaces
→ space_id for each space

# New: list all pages in a space
GET /wiki/v2/spaces/{space_id}/nodes
→ node_token, obj_token (actual docx token), title, parent_node_token

# Existing: fetch document content (unchanged)
GET /docx/v1/documents/{obj_token}/raw_content
→ data.content
```

The connector should auto-discover all accessible wiki spaces. For each space, paginate the flat node list (the API returns `parent_node_token` for hierarchy but indexing only needs `obj_token` values). Collect all `obj_token` values from the flat list — no recursive tree walk needed. `obj_token` maps to the same docx content API already implemented.

### Environment Variables

Add to EC2 `.env`:

```
FEISHU_APP_ID=<from Feishu developer console>
FEISHU_APP_SECRET=<from Feishu developer console>
FEISHU_WIKI_ENABLED=true
# FEISHU_FOLDER_TOKENS=<comma-separated if any Drive folders needed>
```

**Note:** Do not commit credentials to source control. Add directly to EC2 `.env` only.

### Feishu App Permissions Required

The Feishu app must have these scopes granted in the developer console:

- `wiki:wiki:readonly` — list spaces and nodes
- `docs:document:readonly` — read document content
- `drive:drive:readonly` — Drive folder access (if used)

### Sync Trigger

After adding env vars, trigger initial sync:

```bash
celery call tasks.sync_feishu
```

Subsequent syncs run on the existing Celery beat schedule. Feishu documents appear in retrieval with `source_type='feishu'` visible in chat citations.

---

## Section 6 — Cutover and Retirement

### Automatic Cutover

When the backfill task finishes, it sets `RETRIEVAL_CUTOVER=true`. The fan-out layer stops querying `kb_chunks` immediately (no deploy required).

Verify via:
```
GET /admin/backfill-status
→ { kb_chunks_remaining: 0, cutover: true }
```

### 7-Day Safety Hold

`kb_chunks` stays read-only in the database for 7 days after cutover. If retrieval quality degrades, set `RETRIEVAL_CUTOVER=false` to fall back instantly.

### Retirement (Day 7+)

```python
# Alembic migration
op.drop_table('kb_chunks')
```

Delete:
- `HybridRetriever` class (legacy)
- `KbChunk` SQLAlchemy model
- Legacy query branch in the fan-out wrapper
- Any remaining `kb_chunks` references

---

## FTS Upgrade Path (Next Week)

After TiDB cluster migrates to Frankfurt or Singapore:

1. Run Alembic migration:
   ```sql
   ALTER TABLE knowledge_index
     ADD FULLTEXT INDEX idx_ki_fts (content)
     WITH PARSER MULTILINGUAL;
   ```
2. Set `fts_enabled=True` in `HybridRetrievalService`
3. BM25 hybrid scoring activates — vector + full-text combined retrieval

No other code changes needed. This is the full FTS upgrade.

---

## Implementation Sequence

| Step | Action | Blocker |
|------|--------|---------|
| 1 | Alembic migration: add HNSW index to `knowledge_index` | None |
| 2 | Stop all ingestors writing to `kb_chunks` | Step 1 |
| 3 | Extend `feishu_connector.py` for wiki space support | None |
| 4 | Add Feishu env vars to EC2 `.env` | Step 3 |
| 5 | Add `/admin/backfill-status` endpoint | None |
| 6 | Implement fan-out retrieval with `RETRIEVAL_CUTOVER` flag | Step 1 |
| 7 | Deploy | Steps 1–6 |
| 8 | Trigger initial Feishu sync | Step 7 |
| 9 | Trigger backfill task | Step 7 |
| 10 | Monitor backfill; wait for `RETRIEVAL_CUTOVER=true` | Step 9 |
| 11 | Verify retrieval quality | Step 10 |
| 12 | Day 7: drop `kb_chunks`, delete legacy code | Step 11 |
| 13 | Region migration + FTS index | Step 12 (or parallel) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Backfill crashes mid-way | Upsert is idempotent; restart task from any offset |
| Retrieval quality drop during fan-out | Deduplication by `source_id` prevents duplicates; `top_k` applied after merge |
| Feishu wiki permissions not granted | Verify scopes in developer console before running sync |
| `RETRIEVAL_CUTOVER` flips too early | `set_runtime_config` only called when `rows` is empty (all batches processed) |
| Region migration delayed | FTS is fully independent — retirement and wiki sync proceed without it |
