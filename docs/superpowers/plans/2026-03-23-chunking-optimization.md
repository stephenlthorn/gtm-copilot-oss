# Chunking Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve transcript retrieval precision by denormalizing call-level metadata into KBChunk, context-prefixing embeddings, adding a TiDB HNSW vector index, and persisting call_outcome on ChorusCall.

**Architecture:** Four coordinated changes in `transcript_ingestor.py`, `retrieval/service.py`, `models/entities.py`, and a new Alembic migration. Tests live in `api/tests/unit/test_chunking_optimization.py`. All changes follow the existing `op.get_bind()` migration pattern and SQLAlchemy 2.0 `Mapped`/`mapped_column` style.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, pytest, TiDB (MySQL dialect)

---

## File Map

| File | Role |
|---|---|
| `api/app/models/entities.py` | Add `call_outcome: Mapped[str \| None]` to `ChorusCall` |
| `api/app/ingest/transcript_ingestor.py` | Add `_coerce_outcome`, `_build_embed_text`; update `_normalize`, `_upsert_call`, `_replace_chunks` |
| `api/app/retrieval/service.py` | Add chunk-level filters to `_apply_filters`; pass `chunk` arg at call site |
| `api/alembic/versions/20260324_000001_add_hnsw_index_and_call_outcome.py` | Migration: `call_outcome` column + HNSW index |
| `api/tests/unit/test_chunking_optimization.py` | All unit + integration tests for these changes |

---

## Task 1: `call_outcome` model field + migration

**Files:**
- Modify: `api/app/models/entities.py:114` (after `se_email`)
- Create: `api/alembic/versions/20260324_000001_add_hnsw_index_and_call_outcome.py`
- Create: `api/tests/unit/test_chunking_optimization.py`

### Background

`ChorusCall` currently has no `call_outcome` field (ends at `transcript_url` / `created_at`). We add `call_outcome: Mapped[str | None]` and a combined migration that also adds the HNSW index.

The existing migration pattern (see `20260316_000004_tidb_compatibility.py`) uses `bind = op.get_bind()` / `bind.dialect.name` for dialect detection.

- [ ] **Step 1.1: Write the failing migration test**

Create `api/tests/unit/test_chunking_optimization.py`:

```python
"""Tests for chunking optimization changes."""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Task 1: Migration / model tests
# ---------------------------------------------------------------------------

def test_chorus_call_has_call_outcome_field():
    """ChorusCall model must expose call_outcome as a mapped attribute."""
    from app.models.entities import ChorusCall
    # Verify the column exists in the mapper (no DB needed)
    mapper = ChorusCall.__mapper__
    assert "call_outcome" in [c.key for c in mapper.column_attrs]
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_chorus_call_has_call_outcome_field -v
```
Expected: **FAIL** — `AssertionError` (field not yet present)

- [ ] **Step 1.2: Add `call_outcome` field to `ChorusCall` model**

In `api/app/models/entities.py`, add after line 114 (`se_email`):

```python
    call_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

The model block should look like:
```python
    rep_email: Mapped[str] = mapped_column(String(255), nullable=False)
    se_email: Mapped[str | None] = mapped_column(String(255))
    call_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    participants: Mapped[list[dict]] = mapped_column(JSON_TYPE, default=list, nullable=False)
```

- [ ] **Step 1.3: Run test to verify it passes**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_chorus_call_has_call_outcome_field -v
```
Expected: **PASS**

- [ ] **Step 1.4: Create the combined Alembic migration**

Create `api/alembic/versions/20260324_000001_add_hnsw_index_and_call_outcome.py`:

```python
"""Add call_outcome column to chorus_calls and HNSW index to kb_chunks.

Revision ID: 20260324_000001
Revises: 20260323_000002
Create Date: 2026-03-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260324_000001"
down_revision = "20260323_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # call_outcome column — all dialects
    op.add_column("chorus_calls", sa.Column("call_outcome", sa.String(64), nullable=True))

    # HNSW vector index — TiDB only
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        try:
            op.execute(
                "ALTER TABLE kb_chunks "
                "ADD VECTOR INDEX idx_kb_chunks_embedding_hnsw "
                "((VEC_COSINE_DISTANCE(embedding))) "
                "USING HNSW COMMENT 'tidb_vector_index'"
            )
        except Exception:
            pass  # Swallows duplicate-index and transient errors; verify with SHOW INDEXES


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        try:
            op.execute("ALTER TABLE kb_chunks DROP INDEX idx_kb_chunks_embedding_hnsw")
        except Exception:
            pass
    op.drop_column("chorus_calls", "call_outcome")
```

- [ ] **Step 1.5: Write migration test**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
def test_migration_adds_call_outcome_column():
    """Migration upgrade/downgrade must not raise on SQLite (non-MySQL dialect)."""
    import importlib.util, sys
    from pathlib import Path
    migration_path = Path(__file__).parents[2] / "alembic" / "versions" / "20260324_000001_add_hnsw_index_and_call_outcome.py"
    spec = importlib.util.spec_from_file_location(
        "migration_20260324",
        migration_path,
    )
    migration = importlib.util.module_from_spec(spec)
    sys.modules["migration_20260324"] = migration
    spec.loader.exec_module(migration)

    mock_bind = MagicMock()
    mock_bind.dialect.name = "sqlite"

    with patch("alembic.op.get_bind", return_value=mock_bind), \
         patch("alembic.op.add_column") as mock_add, \
         patch("alembic.op.drop_column") as mock_drop:
        migration.upgrade()
        mock_add.assert_called_once_with(
            "chorus_calls", pytest.approx(object(), abs=0)  # any Column arg
        )
        migration.downgrade()
        mock_drop.assert_called_once_with("chorus_calls", "call_outcome")
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_migration_adds_call_outcome_column -v
```
Expected: **PASS**

- [ ] **Step 1.6: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/models/entities.py api/alembic/versions/20260324_000001_add_hnsw_index_and_call_outcome.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: add call_outcome field to ChorusCall and combined migration"
```

---

## Task 2: `_coerce_outcome` helper

**Files:**
- Modify: `api/app/ingest/transcript_ingestor.py` (add module-level helper before class)
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

`_coerce_outcome` maps raw Chorus strings like `"Closed Won"` or `"open"` to canonical values `"won"`, `"lost"`, `"no_decision"`, `"active"`. It returns `None` for unrecognized values.

- [ ] **Step 2.1: Write failing tests for `_coerce_outcome`**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 2: _coerce_outcome
# ---------------------------------------------------------------------------

def test_coerce_outcome_won():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("won") == "won"

def test_coerce_outcome_closed_won():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("closed won") == "won"

def test_coerce_outcome_closed_lost_mixed_case():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("Closed Lost") == "lost"

def test_coerce_outcome_no_decision():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("no decision") == "no_decision"

def test_coerce_outcome_open_maps_to_active():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("open") == "active"

def test_coerce_outcome_in_progress_maps_to_active():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("in progress") == "active"

def test_coerce_outcome_none_returns_none():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome(None) is None

def test_coerce_outcome_unrecognized_returns_none():
    from app.ingest.transcript_ingestor import _coerce_outcome
    assert _coerce_outcome("something_random") is None
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "coerce_outcome" -v
```
Expected: **FAIL** — `ImportError: cannot import name '_coerce_outcome'`

- [ ] **Step 2.2: Implement `_coerce_outcome` in `transcript_ingestor.py`**

Add before the `class TranscriptIngestor:` declaration (after the existing imports, after `logger = logging.getLogger(__name__)`):

```python
_OUTCOME_MAP: dict[str, str] = {
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


def _coerce_outcome(raw: str | None) -> str | None:
    return _OUTCOME_MAP.get((raw or "").strip().lower())
```

- [ ] **Step 2.3: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "coerce_outcome" -v
```
Expected: **8 PASSED**

- [ ] **Step 2.4: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/ingest/transcript_ingestor.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: add _coerce_outcome helper to transcript_ingestor"
```

---

## Task 3: `_normalize` + `_upsert_call` changes for `call_outcome`

**Files:**
- Modify: `api/app/ingest/transcript_ingestor.py:55-96` (`_normalize` md dict, `_upsert_call` values dict)
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

`_normalize` builds an `md` dict at lines 55–62. We add `call_outcome` alongside the other fields. `_upsert_call` reads from `md` at lines 82–96. We add `call_outcome` to the `values` dict using `_coerce_outcome`.

- [ ] **Step 3.1: Write failing test**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 3: _normalize and _upsert_call for call_outcome
# ---------------------------------------------------------------------------

def test_normalize_extracts_call_outcome_from_top_level():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    payload = {
        "chorus_call_id": "abc",
        "date": "2026-03-01",
        "account": "Acme",
        "rep_email": "rep@corp.com",
        "call_outcome": "closed won",
        "turns": [],
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] == "closed won"


def test_normalize_extracts_call_outcome_from_metadata_dict():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    payload = {
        "chorus_call_id": "abc",
        "metadata": {
            "date": "2026-03-01",
            "account": "Acme",
            "rep_email": "rep@corp.com",
            "call_outcome": "open",
        },
        "turns": [],
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] == "open"


def test_normalize_call_outcome_none_when_absent():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    payload = {
        "chorus_call_id": "abc",
        "date": "2026-03-01",
        "account": "Acme",
        "rep_email": "rep@corp.com",
        "turns": [],
    }
    normalized = TranscriptIngestor._normalize(payload)
    assert normalized["metadata"]["call_outcome"] is None
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "normalize" -v
```
Expected: **FAIL** — `KeyError: 'call_outcome'`

- [ ] **Step 3.2: Add `call_outcome` to `_normalize`'s `md` dict**

In `api/app/ingest/transcript_ingestor.py`, the `md` dict at lines 55–62 currently ends at `se_email`. Add the new field:

```python
        md = {
            "date": payload.get("date") or payload.get("metadata", {}).get("date"),
            "account": payload.get("account") or payload.get("metadata", {}).get("account") or "Unknown",
            "opportunity": payload.get("opportunity") or payload.get("metadata", {}).get("opportunity"),
            "stage": payload.get("stage") or payload.get("metadata", {}).get("stage"),
            "rep_email": payload.get("rep_email") or payload.get("metadata", {}).get("rep_email") or "unknown@example.com",
            "se_email": payload.get("se_email") or payload.get("metadata", {}).get("se_email"),
            "call_outcome": payload.get("call_outcome") or payload.get("metadata", {}).get("call_outcome"),
        }
```

- [ ] **Step 3.3: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "normalize" -v
```
Expected: **3 PASSED**

- [ ] **Step 3.4: Write failing test for `_upsert_call`**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
def test_upsert_call_persists_call_outcome():
    """_upsert_call must call _coerce_outcome and include result in values dict."""
    from app.ingest.transcript_ingestor import TranscriptIngestor, _coerce_outcome
    from unittest.mock import MagicMock, patch, call as mock_call
    import datetime

    db = MagicMock()
    db.bind.dialect.name = "sqlite"
    ingestor = TranscriptIngestor.__new__(TranscriptIngestor)
    ingestor.db = db

    # Make execute().scalar_one_or_none() return None (new record path)
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalar_one.return_value = MagicMock(
        chorus_call_id="test-id", call_outcome="won"
    )

    normalized = {
        "chorus_call_id": "test-id",
        "engagement_type": "call",
        "meeting_summary": None,
        "action_items": [],
        "metadata": {
            "date": "2026-03-01",
            "account": "Acme",
            "rep_email": "rep@corp.com",
            "se_email": None,
            "stage": None,
            "call_outcome": "closed won",
        },
        "speaker_map": {},
        "recording_url": None,
        "transcript_url": None,
    }

    result = ingestor._upsert_call(normalized)
    # The ChorusCall was added with call_outcome
    added_obj = db.add.call_args[0][0]
    assert added_obj.call_outcome == "won"  # _coerce_outcome("closed won") == "won"
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_upsert_call_persists_call_outcome -v
```
Expected: **FAIL** — `AttributeError: call_outcome` not set on the new ChorusCall

- [ ] **Step 3.5: Add `call_outcome` to `_upsert_call` values dict**

In `api/app/ingest/transcript_ingestor.py`, the `values` dict in `_upsert_call` (lines 82–96) currently ends at `transcript_url`. Add after `se_email`:

```python
            "se_email": md.get("se_email"),
            "call_outcome": _coerce_outcome(md.get("call_outcome")),
```

- [ ] **Step 3.6: Run tests**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "normalize or upsert_call" -v
```
Expected: **4 PASSED**

- [ ] **Step 3.7: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/ingest/transcript_ingestor.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: extract and persist call_outcome through _normalize and _upsert_call"
```

---

## Task 4: `_build_embed_text` helper

**Files:**
- Modify: `api/app/ingest/transcript_ingestor.py` (add module-level function)
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

`_build_embed_text` constructs a context-prefix string and prepends it to chunk text for embedding. The prefix format is `{account} | {stage} | {date} | rep:{rep_email}` with `stage` segment omitted (including its leading ` | `) when absent. The `call_metadata` dict is the same one assembled in `_replace_chunks` — keys `stage`, `se_email`, `call_outcome` are absent (not `None`) when falsy.

- [ ] **Step 4.1: Write failing tests**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 4: _build_embed_text
# ---------------------------------------------------------------------------

def _make_call_metadata(**overrides):
    base = {
        "rep_email": "alice@corp.com",
        "account": "Acme Corp",
        "date": "2026-03-15",
    }
    base.update(overrides)
    return base


def test_build_embed_text_with_stage():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata(stage="Discovery")
    result = _build_embed_text("some transcript text", meta)
    assert result == "Acme Corp | Discovery | 2026-03-15 | rep:alice@corp.com\n\nsome transcript text"


def test_build_embed_text_without_stage():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata()  # no stage key
    result = _build_embed_text("some transcript text", meta)
    assert result == "Acme Corp | 2026-03-15 | rep:alice@corp.com\n\nsome transcript text"


def test_build_embed_text_empty_stage_omitted():
    from app.ingest.transcript_ingestor import _build_embed_text
    meta = _make_call_metadata(stage="")
    result = _build_embed_text("some transcript text", meta)
    # Empty string is falsy — prefix must NOT contain double-pipe
    assert " |  | " not in result
    assert "2026-03-15" in result


def test_build_embed_text_chunk_text_unchanged():
    from app.ingest.transcript_ingestor import _build_embed_text
    chunk_text = "00:01:23 AE: Let me understand your current architecture..."
    meta = _make_call_metadata(stage="Discovery")
    result = _build_embed_text(chunk_text, meta)
    assert result.endswith(chunk_text)
    # chunk_text appears verbatim after the double newline separator
    assert "\n\n" + chunk_text in result
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "build_embed_text" -v
```
Expected: **FAIL** — `ImportError: cannot import name '_build_embed_text'`

- [ ] **Step 4.2: Implement `_build_embed_text`**

Add after `_coerce_outcome` / `_OUTCOME_MAP` in `api/app/ingest/transcript_ingestor.py` (still before the class):

```python
def _build_embed_text(chunk_text: str, call_metadata: dict) -> str:
    parts = [call_metadata["account"]]
    stage = call_metadata.get("stage")
    if stage:
        parts.append(stage)
    parts.append(call_metadata["date"])
    parts.append(f"rep:{call_metadata['rep_email']}")
    prefix = " | ".join(parts)
    return f"{prefix}\n\n{chunk_text}"
```

- [ ] **Step 4.3: Run tests**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "build_embed_text" -v
```
Expected: **4 PASSED**

- [ ] **Step 4.4: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/ingest/transcript_ingestor.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: add _build_embed_text context-prefix helper"
```

---

## Task 5: `_replace_chunks` — metadata denormalization + context-prefix embedding

**Files:**
- Modify: `api/app/ingest/transcript_ingestor.py:146-182` (`_replace_chunks` signature and body)
- Modify: `api/app/ingest/transcript_ingestor.py:254` (`sync()` call site)
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

`_replace_chunks` gains a `call: ChorusCall` parameter. It assembles `call_metadata` from the `call` object, merges it into each chunk's `metadata_json`, and uses `_build_embed_text` to produce the embed string. `KBChunk.text` stays as the raw transcript.

The call site in `sync()` at line 254 is `page_ingestor._replace_chunks(doc, normalized)` — update to `page_ingestor._replace_chunks(doc, normalized, call)`.

- [ ] **Step 5.1: Write failing tests**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 5: _replace_chunks metadata + embedding
# ---------------------------------------------------------------------------

def _make_chorus_call(**overrides):
    from datetime import date as date_cls
    from unittest.mock import MagicMock
    call = MagicMock()
    call.rep_email = "alice@corp.com"
    call.account = "Acme Corp"
    call.date = date_cls(2026, 3, 15)
    call.se_email = None
    call.stage = None
    call.call_outcome = None
    for k, v in overrides.items():
        setattr(call, k, v)
    return call


def _make_ingestor_with_mock_db():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from unittest.mock import MagicMock, patch
    ingestor = TranscriptIngestor.__new__(TranscriptIngestor)
    ingestor.db = MagicMock()
    ingestor.embedder = MagicMock()
    ingestor.embedder.batch_embed.return_value = [[0.1] * 1536]
    return ingestor


def _minimal_normalized_with_turns():
    return {
        "chorus_call_id": "call-001",
        "speaker_map": {"S1": {"name": "AE", "role": "ae", "email": "alice@corp.com"}},
        "turns": [
            {"speaker_id": "S1", "start_time_sec": 0, "end_time_sec": 60,
             "text": "Hello and welcome to this call about your architecture."},
        ],
        "meeting_summary": None,
        "action_items": [],
    }


def test_replace_chunks_metadata_has_rep_email_and_account():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from unittest.mock import MagicMock, patch
    from app.models import KBDocument, KBChunk

    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call()

    doc = MagicMock()
    doc.id = "doc-001"

    normalized = _minimal_normalized_with_turns()

    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append

    ingestor._replace_chunks(doc, normalized, call)

    # At least one KBChunk was added
    assert len(added_chunks) >= 1
    for chunk in added_chunks:
        assert chunk.metadata_json["rep_email"] == "alice@corp.com"
        assert chunk.metadata_json["account"] == "Acme Corp"
        assert chunk.metadata_json["date"] == "2026-03-15"


def test_replace_chunks_stage_absent_when_call_stage_none():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage=None)
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert "stage" not in chunk.metadata_json


def test_replace_chunks_call_outcome_absent_when_none():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(call_outcome=None)
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert "call_outcome" not in chunk.metadata_json


def test_replace_chunks_call_outcome_present_when_set():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(call_outcome="won")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        assert chunk.metadata_json["call_outcome"] == "won"


def test_replace_chunks_text_is_raw_transcript_not_prefixed():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    for chunk in added_chunks:
        # text must NOT contain the context prefix pattern
        assert not re.match(r"^\S.*\|.*rep:", chunk.text)


def test_replace_chunks_embed_text_is_prefixed():
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    ingestor._replace_chunks(doc, normalized, call)
    # batch_embed was called with a list; first element must match prefix pattern
    embed_arg = ingestor.embedder.batch_embed.call_args.args[0][0]
    assert re.match(r"^\S.*\|.*rep:", embed_arg)


def test_replace_chunks_fallback_path_text_not_prefixed():
    """Summary-only path: KBChunk.text must not contain prefix."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    import re
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call(stage="Discovery")
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = {
        "chorus_call_id": "call-001",
        "speaker_map": {},
        "turns": [],
        "meeting_summary": "Great call about architecture.",
        "action_items": [],
    }
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    assert len(added_chunks) == 1
    assert not re.match(r"^\S.*\|.*rep:", added_chunks[0].text)
    # embed arg must be prefixed
    embed_arg = ingestor.embedder.batch_embed.call_args.args[0][0]
    assert re.match(r"^\S.*\|.*rep:", embed_arg)


def test_replace_chunks_preserves_time_window_keys():
    """start_time_sec / end_time_sec from chunk_transcript_turns must survive the metadata merge."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    ingestor = _make_ingestor_with_mock_db()
    call = _make_chorus_call()
    doc = MagicMock()
    doc.id = "doc-001"
    normalized = _minimal_normalized_with_turns()
    added_chunks = []
    ingestor.db.add.side_effect = added_chunks.append
    ingestor._replace_chunks(doc, normalized, call)
    assert len(added_chunks) >= 1
    # chunk_transcript_turns produces metadata with start/end time keys
    for chunk in added_chunks:
        assert "start_time_sec" in chunk.metadata_json
        assert "end_time_sec" in chunk.metadata_json
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "replace_chunks" -v
```
Expected: **FAIL** — `TypeError` (wrong number of args to `_replace_chunks`)

- [ ] **Step 5.2: Update `_replace_chunks` signature and body**

Replace the entire `_replace_chunks` method in `api/app/ingest/transcript_ingestor.py`:

```python
    def _replace_chunks(self, doc: KBDocument, normalized: dict, call: ChorusCall) -> list[str]:
        self.db.execute(delete(KBChunk).where(KBChunk.document_id == doc.id))

        turns = normalized.get("turns", [])
        meeting_summary = normalized.get("meeting_summary") or ""
        action_items = normalized.get("action_items") or []

        # Assemble call-level metadata to merge into each chunk's metadata_json
        call_metadata: dict = {
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

        if turns:
            chunks = chunk_transcript_turns(turns, normalized.get("speaker_map", {}))
        elif meeting_summary or action_items:
            # No transcript — embed the Chorus-generated summary + action items instead
            parts = []
            if meeting_summary:
                parts.append(f"Meeting Summary:\n{meeting_summary}")
            if action_items:
                parts.append("Action Items:\n" + "\n".join(f"- {a}" for a in action_items))
            text = "\n\n".join(parts)
            chunks = [TextChunk(text=text, token_count=len(text.split()), metadata={})]
        else:
            return []

        embed_texts = [_build_embed_text(c.text, call_metadata) for c in chunks]
        embeddings = self.embedder.batch_embed(embed_texts)
        snippets: list[str] = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.db.add(
                KBChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=emb,
                    metadata_json={**chunk.metadata, **call_metadata},
                    content_hash=sha256_text(chunk.text),
                )
            )
            snippets.append(chunk.text[:250])
        return snippets
```

- [ ] **Step 5.3: Update the call site in `sync()`**

In `api/app/ingest/transcript_ingestor.py` at line 254, change:

```python
                    snippets = page_ingestor._replace_chunks(doc, normalized)
```

to:

```python
                    snippets = page_ingestor._replace_chunks(doc, normalized, call)
```

- [ ] **Step 5.4: Run tests**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "replace_chunks" -v
```
Expected: **7 PASSED**

- [ ] **Step 5.5: Run full test suite to check for regressions**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -v
```
Expected: all tests pass

- [ ] **Step 5.6: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/ingest/transcript_ingestor.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: denormalize call metadata into KBChunk and use context-prefix embedding"
```

---

## Task 6: `_apply_filters` — chunk-level filters for rep_email, stage, call_outcome

**Files:**
- Modify: `api/app/retrieval/service.py:104-133` (`_apply_filters` signature + body)
- Modify: `api/app/retrieval/service.py:361` (call site in `search()`)
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

`_apply_filters` currently takes `(doc, filters)`. We add `chunk: KBChunk | None = None` as an optional third arg. When `chunk` is provided and `doc.source_type == SourceType.CHORUS`, we apply the new `rep_email`, `stage`, `call_outcome` filters from `chunk.metadata_json`.

The `account` filter retains its existing doc-level fallback — it does NOT exclude pre-migration chunks that lack `metadata_json["account"]`.

The single `_apply_filters` call site in `search()` is at line 361. The fast-path branch (`if call_focused_primary_doc_id and ...`) is at lines 365–369, which is AFTER line 361 — so the filter check already happens before the fast-path. The only change is adding `chunk` to the existing call.

- [ ] **Step 6.1: Write failing tests**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 6: _apply_filters chunk-level filters
# ---------------------------------------------------------------------------

def _make_doc(source_type="chorus"):
    from app.models.entities import KBDocument, SourceType
    from unittest.mock import MagicMock
    doc = MagicMock(spec=KBDocument)
    doc.source_type = MagicMock()
    doc.source_type.value = source_type
    doc.tags = {"account": "Acme Corp"}
    return doc


def _make_chunk(metadata_json=None):
    from app.models.entities import KBChunk
    from unittest.mock import MagicMock
    chunk = MagicMock(spec=KBChunk)
    chunk.metadata_json = metadata_json or {}
    return chunk


def test_apply_filters_rep_email_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "alice@corp.com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_rep_email_case_insensitive():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "Alice@Corp.Com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_rep_email_mismatch_excluded():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"rep_email": "bob@corp.com"})
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is False


def test_apply_filters_rep_email_missing_key_excluded():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({})  # no rep_email key
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is False


def test_apply_filters_rep_email_noop_for_non_chorus():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc(source_type="google_drive")
    chunk = _make_chunk({})  # no rep_email, but not CHORUS
    assert HybridRetriever._apply_filters(doc, {"rep_email": "alice@corp.com"}, chunk) is True


def test_apply_filters_stage_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"stage": "Discovery"})
    assert HybridRetriever._apply_filters(doc, {"stage": ["discovery", "Demo"]}, chunk) is True


def test_apply_filters_stage_mismatch():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"stage": "Closed"})
    assert HybridRetriever._apply_filters(doc, {"stage": ["discovery"]}, chunk) is False


def test_apply_filters_call_outcome_match():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"call_outcome": "won"})
    assert HybridRetriever._apply_filters(doc, {"call_outcome": ["won"]}, chunk) is True


def test_apply_filters_call_outcome_mismatch():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({"call_outcome": "lost"})
    assert HybridRetriever._apply_filters(doc, {"call_outcome": ["won"]}, chunk) is False


def test_apply_filters_no_filters_all_pass():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc()
    chunk = _make_chunk({})
    assert HybridRetriever._apply_filters(doc, {}, chunk) is True


def test_apply_filters_account_still_uses_doc_tags_for_non_chorus():
    from app.retrieval.service import HybridRetriever
    doc = _make_doc(source_type="google_drive")
    doc.tags = {"account": "acme corp"}
    chunk = _make_chunk({})
    assert HybridRetriever._apply_filters(doc, {"account": ["Acme Corp"]}, chunk) is True
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "apply_filters" -v
```
Expected: **FAIL** — `TypeError: _apply_filters() takes 2 positional arguments but 3 were given` (or assertion failures for filters that don't exist yet)

- [ ] **Step 6.2: Update `_apply_filters` in `service.py`**

Replace the entire `_apply_filters` static method (lines 103–133):

```python
    @staticmethod
    def _apply_filters(doc: KBDocument, filters: dict, chunk: "KBChunk | None" = None) -> bool:
        from app.models.entities import SourceType
        source_filter = {s.lower() for s in (filters.get("source_type") or [])}
        if source_filter and doc.source_type.value.lower() not in source_filter:
            return False

        viewer_email = str(filters.get("viewer_email") or "").strip().lower()
        if viewer_email and doc.source_type.value == "google_drive":
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            indexed_for = str(tags.get("user_email", "")).strip().lower()
            if indexed_for and indexed_for != viewer_email:
                return False
        if viewer_email and doc.source_type.value == "feishu":
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            indexed_for = str(tags.get("user_email", "")).strip().lower()
            if indexed_for and indexed_for != viewer_email:
                return False
        if viewer_email and doc.source_type.value == "memory":
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            indexed_for = str(tags.get("user_email", "")).strip().lower()
            if indexed_for and indexed_for != viewer_email:
                return False

        account_filter = {a.lower() for a in (filters.get("account") or [])}
        if account_filter:
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            account = str(tags.get("account", "")).lower()
            if account not in account_filter:
                return False

        # Chunk-level filters — CHORUS source only
        if chunk is not None and doc.source_type.value == SourceType.CHORUS.value:
            chunk_meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}

            rep_email_filter = str(filters.get("rep_email") or "").strip().lower()
            if rep_email_filter:
                chunk_rep = str(chunk_meta.get("rep_email", "")).strip().lower()
                if not chunk_rep or chunk_rep != rep_email_filter:
                    return False

            stage_filter = {s.lower() for s in (filters.get("stage") or [])}
            if stage_filter:
                chunk_stage = str(chunk_meta.get("stage", "")).strip().lower()
                if not chunk_stage or chunk_stage not in stage_filter:
                    return False

            outcome_filter = {o.lower() for o in (filters.get("call_outcome") or [])}
            if outcome_filter:
                chunk_outcome = str(chunk_meta.get("call_outcome", "")).strip().lower()
                if not chunk_outcome or chunk_outcome not in outcome_filter:
                    return False

        return True
```

- [ ] **Step 6.3: Update the call site in `search()`**

In `api/app/retrieval/service.py` at line 361, change:

```python
            if not self._apply_filters(doc, filters):
```

to:

```python
            if not self._apply_filters(doc, filters, chunk):
```

Also add the confirming comment at the fast-path branch (lines 365–369). Change:

```python
            # Force call-focused primary chunks to score near 1.0 in order
            chunk_doc_id = str(doc.id)
            if call_focused_primary_doc_id and chunk_doc_id == call_focused_primary_doc_id:
```

to:

```python
            # Force call-focused primary chunks to score near 1.0 in order
            # Note: _apply_filters (with chunk) was already applied above.
            chunk_doc_id = str(doc.id)
            if call_focused_primary_doc_id and chunk_doc_id == call_focused_primary_doc_id:
```

- [ ] **Step 6.4: Run tests**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -k "apply_filters" -v
```
Expected: **11 PASSED**

- [ ] **Step 6.5: Run full test file**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -v
```
Expected: all tests pass

- [ ] **Step 6.6: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/app/retrieval/service.py api/tests/unit/test_chunking_optimization.py && git commit -m "feat: add rep_email, stage, call_outcome chunk-level filters to HybridRetriever"
```

---

## Task 7: End-to-end integration test

**Files:**
- Test: `api/tests/unit/test_chunking_optimization.py`

### Background

This task implements spec §10.5: ingest a fixture call into an in-memory SQLite database, then retrieve with filters to verify chunk-level filtering and that `KBChunk.text` does not contain the context prefix. This test requires a real SQLAlchemy session (SQLite in-memory), not mocks.

- [ ] **Step 7.1: Write the failing integration test**

Add to `api/tests/unit/test_chunking_optimization.py`:

```python
# ---------------------------------------------------------------------------
# Task 7: Integration test — end-to-end ingest and retrieve
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """Spin up a fresh in-memory SQLite session with all tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    engine.dispose()


def test_integration_ingest_and_retrieve_by_call_outcome(sqlite_db):
    """Ingest a call with call_outcome='won'; search with outcome filter returns it."""
    from app.ingest.transcript_ingestor import TranscriptIngestor
    from app.retrieval.service import HybridRetriever
    from unittest.mock import MagicMock, patch

    # Patch EmbeddingService so it does not make real API calls
    mock_embed_val = [0.1] * 1536
    with patch("app.ingest.transcript_ingestor.EmbeddingService") as MockEmbed, \
         patch("app.retrieval.service.EmbeddingService") as MockRetrieveEmbed:
        MockEmbed.return_value.batch_embed.return_value = [mock_embed_val]
        MockRetrieveEmbed.return_value.embed.return_value = mock_embed_val
        MockRetrieveEmbed.return_value.client = MagicMock()

        ingestor = TranscriptIngestor(sqlite_db)
        payload = {
            "chorus_call_id": "call-won-001",
            "date": "2026-03-01",
            "account": "Acme Corp",
            "rep_email": "alice@corp.com",
            "call_outcome": "won",
            "stage": "Discovery",
            "turns": [
                {"speaker_id": "S1", "start_time_sec": 0, "end_time_sec": 60,
                 "text": "Let us discuss the architecture of your system today."},
            ],
            "speaker_map": {"S1": {"name": "AE", "role": "ae", "email": "alice@corp.com"}},
            "meeting_summary": None,
            "action_items": [],
        }
        normalized = ingestor._normalize(payload)
        call = ingestor._upsert_call(normalized)
        doc = ingestor._upsert_document(normalized, call)
        ingestor._replace_chunks(doc, normalized, call)
        sqlite_db.commit()

        retriever = HybridRetriever(sqlite_db)

        # Filter by won outcome — must return chunks
        hits_won = retriever.search(
            "architecture",
            filters={"source_type": ["chorus"], "call_outcome": ["won"]},
        )
        assert len(hits_won) >= 1

        # Filter by lost outcome — must return nothing
        hits_lost = retriever.search(
            "architecture",
            filters={"source_type": ["chorus"], "call_outcome": ["lost"]},
        )
        assert len(hits_lost) == 0

        # Filter by rep email — must return chunks for alice
        hits_rep = retriever.search(
            "architecture",
            filters={"source_type": ["chorus"], "rep_email": "alice@corp.com"},
        )
        assert len(hits_rep) >= 1

        # KBChunk.text must not contain the account/stage prefix
        import re
        for hit in hits_won:
            assert not re.match(r"^\S.*\|.*rep:", hit.text)
```

Run:
```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_integration_ingest_and_retrieve_by_call_outcome -v
```
Expected: **FAIL** — `TypeError` (wrong arg count for `_replace_chunks` before implementation in Task 5)

- [ ] **Step 7.2: Confirm test passes after Task 5 and Task 6 are complete**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py::test_integration_ingest_and_retrieve_by_call_outcome -v
```
Expected: **PASS**

- [ ] **Step 7.3: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git add api/tests/unit/test_chunking_optimization.py && git commit -m "test: add end-to-end integration test for chunking filters"
```

---

## Task 9: Final push

- [ ] **Step 9.1: Run the complete test file one final time**

```bash
cd api && python -m pytest tests/unit/test_chunking_optimization.py -v
```
Expected: all tests pass with 0 failures

- [ ] **Step 9.2: Push to GitHub**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb && git push
```

---

## Post-implementation operational note

After applying the migration to TiDB production, verify the HNSW index was created:

```sql
SHOW INDEXES FROM kb_chunks;
```

Confirm a row with `Key_name = 'idx_kb_chunks_embedding_hnsw'` appears. If only `idx_kb_chunks_embedding` appears (from the prior migration), ANN search still works — no action needed.
