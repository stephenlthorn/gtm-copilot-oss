# Call Transcript Chunking and Retrieval Optimization — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Four coordinated changes that improve transcript retrieval precision through metadata denormalization, context-enriched embeddings, a TiDB HNSW vector index, and a `call_outcome` field on `ChorusCall`.

---

## 1. Goal

Transcript chunks are currently embedded without call-level context (account, stage, rep), and chunk-level filters only operate on document-level tags. This means:

- Retrieval cannot filter chunks by rep, outcome, or stage without joining through `KBDocument.tags`.
- Embeddings for chunks from different accounts or stages land in similar vector space even when semantically distant in a business context.
- TiDB production deployments fall back to a full table scan for ANN search because no vector index exists on `kb_chunks.embedding`.
- `call_outcome` (won/lost/no_decision/active) is available in the Chorus API payload but is never persisted.

These four changes fix all four gaps in a single coordinated increment.

---

## 2. Architecture Overview

```
Chorus API payload
       │
       ▼
TranscriptIngestor._normalize()
  ── extracts call_outcome (new)
       │
       ▼
TranscriptIngestor._upsert_call()
  ── persists call_outcome on ChorusCall (Change 4)
       │
       ▼
TranscriptIngestor._replace_chunks()
  ── builds call_metadata dict from ChorusCall
  ── for each TextChunk:
       ├─ _build_embed_text(chunk.text, call_metadata)  → embed_text  (Change 2)
       │    context_prefix is prepended; NOT stored in KBChunk.text
       ├─ embedder.embed(embed_text)                    → embedding
       └─ KBChunk.metadata_json = chunk.metadata
                                  + call-level fields    (Change 1)
                                    rep_email, se_email, account,
                                    date, stage, call_outcome
       │
       ▼
HybridRetriever._apply_filters()
  ── new chunk-level filter keys: rep_email, stage,
     call_outcome (reads from chunk.metadata_json)       (Change 1)
       │
       ▼
TiDB: HNSW vector index on kb_chunks.embedding           (Change 3)
```

---

## 3. Change 1 — Metadata Denormalization into KBChunk

### 3.1 What changes

Every `KBChunk` produced from a Chorus transcript must carry call-level metadata in its `metadata_json` column so that retrieval can filter at the chunk level without joining back to `KBDocument.tags` or `ChorusCall`.

### 3.2 Fields added to `metadata_json`

| Key | Source | Type | Notes |
|---|---|---|---|
| `rep_email` | `ChorusCall.rep_email` | `str` | Always present (non-nullable on model) |
| `se_email` | `ChorusCall.se_email` | `str \| None` | Omitted from dict if `None` |
| `account` | `ChorusCall.account` | `str` | Always present |
| `date` | `ChorusCall.date.isoformat()` | `str` (ISO 8601) | e.g. `"2026-03-23"` |
| `stage` | `ChorusCall.stage` | `str \| None` | Omitted from dict if `None` |
| `call_outcome` | `ChorusCall.call_outcome` | `str \| None` | Omitted from dict if `None` |

The existing time-window keys (`start_time_sec`, `end_time_sec`) produced by `chunk_transcript_turns` are preserved unchanged.

### 3.3 Where the change is made

File: `api/app/ingest/transcript_ingestor.py`

In `_replace_chunks(self, doc: KBDocument, normalized: dict)` — after chunks are produced by `chunk_transcript_turns` (or the summary fallback path), and before iterating to create `KBChunk` objects, a `call_metadata` dict is assembled from the `ChorusCall` object (which is already available because `_replace_chunks` is called after `_upsert_call` returns the `call` object; the signature must be updated to accept `call: ChorusCall`).

The `call_metadata` dict is merged into each `chunk.metadata` before writing to `KBChunk.metadata_json`:

```
call_metadata = {
    "rep_email": call.rep_email,
    "account": call.account,
    "date": call.date.isoformat(),
}
if call.se_email:
    call_metadata["se_email"] = call.se_email
if call.stage:
    call_metadata["stage"] = call.stage
if call.call_outcome:
    call_metadata["call_outcome"] = call.call_outcome
```

The merged dict is `{**chunk.metadata, **call_metadata}` — call-level keys always win so that stale summaries do not override current call data.

### 3.4 Signature change

`_replace_chunks` current signature:
```python
def _replace_chunks(self, doc: KBDocument, normalized: dict) -> list[str]:
```

New signature:
```python
def _replace_chunks(self, doc: KBDocument, normalized: dict, call: ChorusCall) -> list[str]:
```

All three call sites inside `sync()` must pass `call` as the third argument.

### 3.5 Retrieval filter changes

File: `api/app/retrieval/service.py`

Method: `HybridRetriever._apply_filters(doc: KBDocument, filters: dict) -> bool`

This method currently filters by `source_type`, `viewer_email`, and `account` using only `doc`-level fields and `doc.tags`. The chunk is not passed in, so chunk-level metadata is not accessible here.

Two options exist:

**Option A (preferred):** Change the signature to also accept the chunk and read `metadata_json` for the new filter keys.

New signature:
```python
@staticmethod
def _apply_filters(doc: KBDocument, filters: dict, chunk: KBChunk | None = None) -> bool:
```

The additional filter logic reads from `(chunk.metadata_json or {})` when `chunk` is provided:

- `rep_email` filter: if `filters["rep_email"]` is set (single string or list), check that the chunk's `metadata_json["rep_email"]` matches (case-insensitive). Only applied when `doc.source_type == SourceType.CHORUS`.
- `stage` filter: if `filters["stage"]` is set (list of strings), check that `metadata_json["stage"]` is in the set (case-insensitive). Only applied for CHORUS source.
- `call_outcome` filter: if `filters["call_outcome"]` is set (list of strings), check that `metadata_json["call_outcome"]` is in the set. Only applied for CHORUS source.

The existing `account` filter currently reads from `doc.tags["account"]`. For CHORUS chunks that now carry `account` in `metadata_json`, the chunk-level value should be used as the authoritative source (falls back to `doc.tags` for non-CHORUS or pre-migration chunks).

**Option B:** Apply chunk-level filters inline in `search()` after the deduplication loop, as a separate predicate. This avoids changing `_apply_filters` signature but is less cohesive.

The spec recommends Option A.

All callers of `_apply_filters` in `search()` must pass the `chunk` object:
```python
if not self._apply_filters(doc, filters, chunk):
```

---

## 4. Change 2 — Call-Context Prefix Before Embedding

### 4.1 Motivation

Embedding models treat context-free dialogue ("we need better latency at scale") as semantically similar regardless of which account or deal stage it came from. Prepending a short call-context prefix anchors the chunk vector in account-and-stage space, improving nearest-neighbor clustering without polluting `KBChunk.text` (which must remain the raw transcript for display and keyword scoring).

### 4.2 New helper function

File: `api/app/ingest/transcript_ingestor.py`

Add a static method (or module-level function) `_build_embed_text`:

```
_build_embed_text(chunk_text: str, call_metadata: dict) -> str
```

Behavior:
- Constructs a context prefix of the form:
  `{account} | {stage} | {date} | rep:{rep_email}`
- If `stage` is `None` or empty, the `stage` segment is omitted from the prefix (not replaced with a placeholder).
- Returns `f"{prefix}\n\n{chunk_text}"`.
- `call_metadata` is the same dict assembled in Change 1, so no additional data fetching is needed.

Example output:
```
Acme Corp | Discovery | 2026-03-15 | rep:alice@corp.com

00:01:23 AE: Let me understand your current architecture...
```

### 4.3 Where it is called

In `_replace_chunks`, the embedding call changes from:

```python
embeddings = self.embedder.batch_embed([c.text for c in chunks])
```

to:

```python
embed_texts = [_build_embed_text(c.text, call_metadata) for c in chunks]
embeddings = self.embedder.batch_embed(embed_texts)
```

`KBChunk.text` is set to `chunk.text` (unchanged — raw transcript only). The prefixed `embed_texts` list is used only for the embedding call and is not persisted.

### 4.4 Summary/action-item fallback path

The same prefix applies to the no-turns path (lines 155–163 in current `_replace_chunks`). The single `TextChunk` produced there should also be embedded via `_build_embed_text`.

---

## 5. Change 3 — HNSW Vector Index on TiDB

### 5.1 Context

Migration `20260316_000004_tidb_compatibility.py` already adds a HNSW vector index on `kb_chunks.embedding` in its `upgrade()`. However, the requirement says a new migration is needed — this is because that migration may have been applied without the index succeeding (the `try/except: pass` swallows errors), or the index needs a fresh authoritative migration in this branch.

### 5.2 New migration

File: `api/alembic/versions/20260324_000001_add_kb_chunks_hnsw_index.py`

```
revision = "20260324_000001"
down_revision = "20260323_000002"
```

`upgrade()` behavior:
- Check `bind.dialect.name`.
- If `"mysql"` (TiDB): execute the DDL:
  ```sql
  ALTER TABLE kb_chunks
    ADD VECTOR INDEX idx_kb_chunks_embedding_hnsw
    ((VEC_COSINE_DISTANCE(embedding)))
    USING HNSW
    COMMENT 'tidb_vector_index'
  ```
  Wrap in `try/except Exception: pass` — TiDB raises an error if the index already exists; this keeps the migration idempotent.
- If not `"mysql"`: no-op (SQLite and PostgreSQL use different vector index mechanisms, both handled elsewhere).

`downgrade()` behavior:
- If `"mysql"`: execute:
  ```sql
  ALTER TABLE kb_chunks DROP INDEX idx_kb_chunks_embedding_hnsw
  ```
  Wrapped in `try/except Exception: pass`.
- Otherwise: no-op.

### 5.3 Relationship to existing migration

Migration `20260316_000004` uses the index name `idx_kb_chunks_embedding`. The new migration uses `idx_kb_chunks_embedding_hnsw` to avoid a collision if the old index succeeded. The implementer should verify which name exists in the target TiDB instance before running; if `idx_kb_chunks_embedding` exists and is valid, the new migration body can reference the old name in downgrade only (or be left as a no-op since the old migration already created it). The canonical behavior is: at least one HNSW index on `kb_chunks.embedding` must exist in TiDB production.

---

## 6. Change 4 — `call_outcome` on ChorusCall

### 6.1 Model change

File: `api/app/models/entities.py`

Add to `ChorusCall` (after `se_email`, line 114):

```python
call_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Valid values: `"won"`, `"lost"`, `"no_decision"`, `"active"`, `None`. No DB-level CHECK constraint — validation is at the application layer.

### 6.2 Normalization

File: `api/app/ingest/transcript_ingestor.py`

In `_normalize()`, the `md` dict (lines 55–62) gains:

```python
"call_outcome": payload.get("call_outcome") or payload.get("metadata", {}).get("call_outcome"),
```

No coercion is applied in `_normalize` — the raw string from the Chorus payload is passed through. Coercion to the four canonical values happens in `_upsert_call`.

### 6.3 Upsert change

In `_upsert_call()`, add `call_outcome` to the `values` dict:

```python
"call_outcome": _coerce_outcome(md.get("call_outcome")),
```

Add a module-level helper `_coerce_outcome(raw: str | None) -> str | None`:

```
_OUTCOME_MAP = {
    "won": "won",
    "closed won": "won",
    "loss": "lost",
    "lost": "lost",
    "closed lost": "lost",
    "no decision": "no_decision",
    "no_decision": "no_decision",
    "active": "active",
    "open": "active",
    "in progress": "active",
}
```

Returns `_OUTCOME_MAP.get((raw or "").strip().lower())` — returns `None` for unrecognized values rather than raising.

### 6.4 Alembic migration

The `call_outcome` column is added in the same new migration as the HNSW index (or a separate migration — either is acceptable). If separate:

File: `api/alembic/versions/20260324_000001_add_kb_chunks_hnsw_index.py` (combined)

```python
op.add_column("chorus_calls", sa.Column("call_outcome", sa.String(64), nullable=True))
```

Downgrade:
```python
op.drop_column("chorus_calls", "call_outcome")
```

No default value is needed (nullable, existing rows become `NULL`).

### 6.5 Propagation to chunk metadata_json

Covered by Change 1. Once `ChorusCall.call_outcome` is populated by `_upsert_call`, the `call_metadata` dict assembled in `_replace_chunks` includes it (only if non-None), and it is written into each chunk's `metadata_json`.

---

## 7. Ingestion Call Flow — After All Changes

The full `sync()` loop body changes as follows (pseudo-code, not implementation):

```
normalized = _normalize(raw.payload)
  └─ now extracts call_outcome

call = _upsert_call(normalized)
  └─ persists call_outcome on ChorusCall

doc = _upsert_document(normalized, call)
  └─ unchanged

snippets = _replace_chunks(doc, normalized, call)
  └─ assembles call_metadata from call object
  └─ merges call_metadata into each chunk's metadata_json
  └─ builds embed_texts via _build_embed_text(chunk.text, call_metadata)
  └─ embeds embed_texts (NOT chunk.text)
  └─ stores KBChunk with text=chunk.text, metadata_json=merged_metadata

_replace_artifact(call_id, normalized, snippets)
  └─ unchanged
```

---

## 8. DB Schema Summary

### chorus_calls — new column

| Column | Type | Nullable | Default |
|---|---|---|---|
| `call_outcome` | `VARCHAR(64)` | YES | `NULL` |

### kb_chunks — metadata_json additions (no schema change, JSON column)

New keys that will be present on all Chorus chunks ingested after this change:

| Key | Type |
|---|---|
| `rep_email` | `string` |
| `account` | `string` |
| `date` | `string` (ISO 8601) |
| `se_email` | `string` (if non-null) |
| `stage` | `string` (if non-null) |
| `call_outcome` | `string` (if non-null) |

Pre-existing chunks (ingested before this change) will NOT have these keys. Retrieval filter logic must treat a missing key as a non-match for allowlist filters (i.e., if `rep_email` filter is set and the chunk has no `rep_email` key, the chunk is excluded).

### kb_chunks — new HNSW index (TiDB only)

Index name: `idx_kb_chunks_embedding_hnsw`
Expression: `VEC_COSINE_DISTANCE(embedding)`
Algorithm: `HNSW`

---

## 9. Retrieval Filter Reference

### Existing filter keys (unchanged semantics)

| Key | Type | Applied to |
|---|---|---|
| `source_type` | `list[str]` | `KBDocument.source_type` |
| `viewer_email` | `str` | `KBDocument.tags["user_email"]` (for google_drive, feishu, memory) |
| `account` | `list[str]` | `KBDocument.tags["account"]` (existing) + `chunk.metadata_json["account"]` (new, CHORUS only) |

### New filter keys (CHORUS chunks only)

| Key | Type | Semantics |
|---|---|---|
| `rep_email` | `str` | Case-insensitive exact match against `chunk.metadata_json["rep_email"]`. Single value (not a list) — only one rep per query context. |
| `stage` | `list[str]` | Case-insensitive membership match against `chunk.metadata_json["stage"]`. |
| `call_outcome` | `list[str]` | Case-insensitive membership match against `chunk.metadata_json["call_outcome"]`. |

All new filters are additive (AND logic with existing filters). A filter key that is absent or `None` in the `filters` dict is ignored (the chunk passes). A filter key that is set but the chunk has no matching `metadata_json` key causes the chunk to be excluded.

---

## 10. Testing

### 10.1 Unit tests — `_build_embed_text`

File: `api/tests/ingest/test_transcript_ingestor.py` (or new `test_chunking_optimization.py`)

- Prefix is present in the returned string.
- `chunk_text` is unchanged and present after the prefix.
- Omits `stage` segment when `stage` is `None`.
- Omits `stage` segment when `stage` is `""`.
- Returns correct format when all fields are present.

### 10.2 Unit tests — `_coerce_outcome`

- `"won"` → `"won"`
- `"closed won"` → `"won"`
- `"Closed Lost"` (mixed case) → `"lost"`
- `"no decision"` → `"no_decision"`
- `"open"` → `"active"`
- `None` → `None`
- Unrecognized string → `None`

### 10.3 Unit tests — metadata denormalization

Test `_replace_chunks` with a minimal `ChorusCall` and `normalized` dict:

- Each `KBChunk.metadata_json` contains `rep_email`, `account`, `date`.
- `se_email` key absent when `call.se_email` is `None`.
- `stage` key absent when `call.stage` is `None`.
- `call_outcome` key absent when `call.call_outcome` is `None`.
- `call_outcome` key present with correct value when set.
- `start_time_sec` / `end_time_sec` are preserved from the original chunk metadata.
- `KBChunk.text` equals the raw transcript chunk text (not the prefixed embed text).

### 10.4 Unit tests — `_apply_filters` with chunk metadata

- `rep_email` filter matches chunk with matching `metadata_json["rep_email"]` (case-insensitive).
- `rep_email` filter excludes chunk with different `metadata_json["rep_email"]`.
- `rep_email` filter excludes chunk with no `rep_email` key in `metadata_json`.
- `rep_email` filter is a no-op for non-CHORUS chunks.
- `stage` filter (list) includes chunk whose stage is in the list.
- `stage` filter excludes chunk whose stage is not in the list.
- `call_outcome` filter includes `"won"` chunks when filter is `["won"]`.
- `call_outcome` filter excludes `"lost"` chunks when filter is `["won"]`.
- No filters → all chunks pass.
- Existing `account` filter still works against `doc.tags` for non-CHORUS chunks.

### 10.5 Integration test — end-to-end ingest and retrieve

Using an in-memory SQLite test database:

- Ingest a fixture call with `call_outcome="won"`, `stage="Discovery"`, specific `rep_email`.
- Search with `filters={"call_outcome": ["won"]}` — chunks from this call are returned.
- Search with `filters={"call_outcome": ["lost"]}` — no chunks from this call are returned.
- Search with `filters={"rep_email": "alice@corp.com"}` — chunks returned only for Alice's calls.
- Verify `KBChunk.text` does NOT contain the account/stage prefix.

### 10.6 Migration test

- `call_outcome` column exists on `chorus_calls` after applying the migration.
- Migration is idempotent (running upgrade twice does not raise).
- Downgrade removes the column.

---

## 11. File Index

| File | Change |
|---|---|
| `api/app/models/entities.py` | Add `call_outcome` field to `ChorusCall` |
| `api/app/ingest/transcript_ingestor.py` | `_normalize`, `_upsert_call`, `_replace_chunks` (signature + body), new `_build_embed_text`, new `_coerce_outcome` |
| `api/app/retrieval/service.py` | `_apply_filters` signature and body; all call sites in `search()` |
| `api/alembic/versions/20260324_000001_add_kb_chunks_hnsw_index.py` | New migration: `call_outcome` column + HNSW index |

---

## 12. Out of Scope

- Backfilling existing `KBChunk` rows with call-level metadata. Existing chunks will lack the new keys. Re-ingestion of historical calls is a separate operational task.
- Re-embedding existing chunks with the new context prefix. Existing embeddings remain as-is. Re-embedding requires a full re-ingest.
- UI changes to expose `call_outcome`, `stage`, or `rep_email` as filter controls in the chat or copilot UI.
- Indexed DB columns on `KBChunk` for `rep_email`, `account`, or `stage` (these remain JSON lookups). Adding real columns for high-cardinality filter performance is a future optimization.
- Chorus API changes or webhook handling for `call_outcome` updates post-ingest.
- Any change to `CallArtifact` or the artifact generation pipeline.
- PostgreSQL vector index changes (pgvector uses a different index type and is handled separately).
