# Retrieval Consolidation + Feishu Wiki Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken v2 indexing pipeline, add HNSW index, add Feishu wiki support, and migrate retrieval from kb_chunks to knowledge_index with a zero-downtime backfill.

**Architecture:** Add missing ORM models that the v2 pipeline already imports but that don't exist in entities.py. Layer in HNSW index via Alembic, extend FeishuConnector with wiki space discovery, and add a db-backed `retrieval_cutover` flag so a Celery backfill task can flip retrieval from the legacy `kb_chunks` table to `knowledge_index` without a deploy.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Celery, TiDB (MySQL dialect), httpx, pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `api/app/models/entities.py` | Modify | Add `SyncSourceType`, `SyncStatusEnum`, `SyncStatus`, `KnowledgeIndex`, `retrieval_cutover` on KBConfig |
| `api/app/models/__init__.py` | Modify | Export new models |
| `api/alembic/versions/20260326_000001_add_retrieval_cutover.py` | Create | Add `retrieval_cutover` column to `kb_config` |
| `api/alembic/versions/20260326_000002_add_hnsw_knowledge_index.py` | Create | Add HNSW vector index to `knowledge_index` |
| `api/app/ingest/feishu_connector.py` | Modify | Add wiki space/node listing methods |
| `api/app/services/indexing/feishu_indexer.py` | Modify | Add wiki document discovery to `sync()` |
| `api/app/core/settings.py` | Modify | Add `wiki:wiki:readonly` to Feishu OAuth scopes |
| `api/app/worker.py` | Modify | Replace v1 beat schedule with `full_reindex_v2` |
| `api/app/tasks/indexing_tasks.py` | Modify | Add `backfill_knowledge_index` Celery task |
| `api/app/services/indexing/retrieval.py` | Modify | Add retrieval fan-out with `retrieval_cutover` check |
| `api/app/api/routes/admin.py` | Modify | Add `GET /admin/backfill-status` endpoint |
| `api/tests/test_orm_models.py` | Create | Tests: ORM model imports, instantiation |
| `api/tests/test_feishu_wiki.py` | Create | Tests: wiki connector methods (mocked HTTP) |
| `api/tests/test_retrieval_fanout.py` | Create | Tests: fan-out logic, cutover flag |
| `api/tests/test_backfill_task.py` | Create | Tests: backfill task logic |

---

## Task 1: Add missing ORM models to entities.py

**Why:** `index_manager.py`, `feishu_indexer.py`, and `retrieval.py` all import `KnowledgeIndex`, `SyncSourceType`, `SyncStatus`, `SyncStatusEnum` from `entities.py` — but none exist there. The entire v2 pipeline is currently broken with ImportError. Tables already exist in the DB from migration `20260312_add_gtm_v2_models.py`. No new migration needed.

**Files:**
- Modify: `api/app/models/entities.py`
- Modify: `api/app/models/__init__.py`
- Create: `api/tests/test_orm_models.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_orm_models.py
import pytest

def test_sync_source_type_has_expected_values():
    from app.models.entities import SyncSourceType
    assert SyncSourceType.feishu.value == "feishu"
    assert SyncSourceType.google_drive.value == "google_drive"
    assert SyncSourceType.tidb_docs.value == "tidb_docs"

def test_sync_status_enum_has_expected_values():
    from app.models.entities import SyncStatusEnum
    assert SyncStatusEnum.idle.value == "idle"
    assert SyncStatusEnum.syncing.value == "syncing"
    assert SyncStatusEnum.error.value == "error"

def test_knowledge_index_can_be_instantiated():
    from app.models.entities import KnowledgeIndex
    ki = KnowledgeIndex(
        source_type="feishu",
        source_ref="ABC123",
        title="Test Doc",
        chunk_text="hello world",
        chunk_index=0,
        org_id=1,
    )
    assert ki.source_ref == "ABC123"
    assert ki.org_id == 1

def test_sync_status_can_be_instantiated():
    from app.models.entities import SyncStatus, SyncStatusEnum
    ss = SyncStatus(source_type="feishu", org_id=1, status=SyncStatusEnum.idle)
    assert ss.org_id == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_orm_models.py -v 2>&1 | head -20
```
Expected: `ImportError` or `cannot import name`

- [ ] **Step 3: Add the missing models to entities.py**

Add after the `SourceType` class (around line 37), before `MessageMode`:

```python
class SyncSourceType(str, enum.Enum):
    feishu = "feishu"
    google_drive = "google_drive"
    chorus = "chorus"
    tidb_docs = "tidb_docs"
    github = "github"


class SyncStatusEnum(str, enum.Enum):
    idle = "idle"
    syncing = "syncing"
    error = "error"
```

Add after `KBChunk` (around line 102), before `ChorusCall`:

```python
class SyncStatus(Base):
    __tablename__ = "sync_status"
    __table_args__ = (Index("idx_source_org", "source_type", "org_id", unique=True),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    org_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    docs_indexed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="idle", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class KnowledgeIndex(Base):
    __tablename__ = "knowledge_index"
    __table_args__ = (Index("idx_source", "source_type", "org_id"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(String(512))
    chunk_text: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[dict | None] = mapped_column(JSON_TYPE)
    embedding_model: Mapped[str | None] = mapped_column(String(64), server_default="text-embedding-3-small")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON_TYPE)
    org_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now())
```

Note: `sa.BigInteger` requires `import sqlalchemy as sa` which is already present at the top of `entities.py`.

- [ ] **Step 4: Export new models from `api/app/models/__init__.py`**

Add to the import block and `__all__` list:

```python
# Add to import from app.models.entities:
    KnowledgeIndex,
    SyncSourceType,
    SyncStatus,
    SyncStatusEnum,
```

```python
# Add to __all__:
    "KnowledgeIndex",
    "SyncSourceType",
    "SyncStatus",
    "SyncStatusEnum",
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_orm_models.py -v
```
Expected: 4 tests PASS

- [ ] **Step 6: Confirm v2 pipeline imports work**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -c "from app.services.indexing.index_manager import IndexManager; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/models/entities.py api/app/models/__init__.py api/tests/test_orm_models.py
git commit -m "feat: add missing ORM models KnowledgeIndex, SyncStatus, SyncSourceType, SyncStatusEnum"
```

---

## Task 2: Add `retrieval_cutover` to KBConfig

**Why:** The fan-out retrieval and backfill task both need to read/write a live DB flag. Stored in `kb_config` so all processes (API and Celery workers) see the same value without a restart.

**Files:**
- Modify: `api/app/models/entities.py` — add column
- Create: `api/alembic/versions/20260326_000001_add_retrieval_cutover.py`

- [ ] **Step 1: Write the failing test** (add to `api/tests/test_orm_models.py`)

```python
def test_kb_config_has_retrieval_cutover():
    from app.models.entities import KBConfig
    config = KBConfig()
    assert hasattr(config, "retrieval_cutover")
    assert config.retrieval_cutover is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_orm_models.py::test_kb_config_has_retrieval_cutover -v
```
Expected: FAIL — `AttributeError`

- [ ] **Step 3: Add column to KBConfig in entities.py**

In the `KBConfig` class, add after `feishu_app_secret` (around line 194):

```python
    retrieval_cutover: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_orm_models.py -v
```
Expected: All pass

- [ ] **Step 5: Create Alembic migration**

Create `api/alembic/versions/20260326_000001_add_retrieval_cutover.py`:

```python
"""add retrieval_cutover to kb_config

Revision ID: 20260326_000001
Revises: 20260325_000001
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "20260326_000001"
down_revision = "20260325_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_config",
        sa.Column("retrieval_cutover", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("kb_config", "retrieval_cutover")
```

**Important:** Find the correct `down_revision` by running:
```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m alembic heads
```
Use that revision ID as `down_revision`.

- [ ] **Step 6: Run migration**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m alembic upgrade head
```
Expected: Migration applies cleanly

- [ ] **Step 7: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/models/entities.py api/alembic/versions/20260326_000001_add_retrieval_cutover.py
git commit -m "feat: add retrieval_cutover flag to kb_config for zero-downtime cutover"
```

---

## Task 3: Add HNSW vector index to knowledge_index

**Why:** `_vector_search_tidb()` uses `VEC_COSINE_DISTANCE` which requires an HNSW index for performance. Without it, every query does a full table scan.

**Files:**
- Create: `api/alembic/versions/20260326_000002_add_hnsw_knowledge_index.py`

- [ ] **Step 1: Create Alembic migration**

```python
"""add HNSW vector index to knowledge_index

Revision ID: 20260326_000002
Revises: 20260326_000001
Create Date: 2026-03-26
"""
from alembic import op

revision = "20260326_000002"
down_revision = "20260326_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TiDB-specific: HNSW index on the embedding column using cosine distance.
    # This is a raw DDL statement — SQLAlchemy has no ORM equivalent.
    op.execute(
        "ALTER TABLE knowledge_index "
        "ADD VECTOR INDEX idx_ki_embedding "
        "((VEC_COSINE_DISTANCE(embedding))) "
        "USING HNSW;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_index DROP INDEX idx_ki_embedding;")
```

- [ ] **Step 2: Run migration**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m alembic upgrade head
```

This will take a few minutes if `knowledge_index` has existing rows. Expected: `Running upgrade ... -> 20260326_000002`

- [ ] **Step 3: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/alembic/versions/20260326_000002_add_hnsw_knowledge_index.py
git commit -m "feat: add HNSW vector index to knowledge_index for TiDB native vector search"
```

---

## Task 4: Add wiki support to feishu_connector.py

**Why:** The connector only handles Drive folders. User's content is in Feishu Wiki (`https://pingcap.feishu.cn/wiki/`). The Feishu Wiki v2 API uses different endpoints but the same document content API (`/docx/v1/documents/{token}/raw_content`).

**Files:**
- Modify: `api/app/ingest/feishu_connector.py`
- Create: `api/tests/test_feishu_wiki.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_feishu_wiki.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def connector():
    from app.ingest.feishu_connector import FeishuConnector
    c = FeishuConnector(app_id="test_id", app_secret="test_secret")
    c._tenant_token = "fake_token"  # skip auth
    return c


def test_list_wiki_spaces_returns_space_list(connector):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"space_id": "sp_abc", "name": "Sales Wiki"}],
            "has_more": False,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        spaces = connector.list_wiki_spaces()

    assert len(spaces) == 1
    assert spaces[0]["space_id"] == "sp_abc"


def test_list_wiki_nodes_returns_flat_node_list(connector):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [
                {"node_token": "n1", "obj_token": "doc_abc", "obj_type": "docx", "title": "My Doc"},
                {"node_token": "n2", "obj_token": "doc_xyz", "obj_type": "docx", "title": "Other Doc"},
            ],
            "has_more": False,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        nodes = connector.list_wiki_nodes("sp_abc")

    assert len(nodes) == 2
    assert nodes[0]["obj_token"] == "doc_abc"


def test_list_wiki_documents_collects_docx_from_all_spaces(connector):
    spaces_response = MagicMock()
    spaces_response.raise_for_status = MagicMock()
    spaces_response.json.return_value = {
        "code": 0,
        "data": {"items": [{"space_id": "sp1"}, {"space_id": "sp2"}], "has_more": False},
    }

    nodes_response = MagicMock()
    nodes_response.raise_for_status = MagicMock()
    nodes_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"obj_token": "doc_1", "obj_type": "docx", "title": "Doc 1"}],
            "has_more": False,
        },
    }

    with patch("httpx.get", side_effect=[spaces_response, nodes_response, nodes_response]):
        docs = connector.list_wiki_documents()

    # 2 spaces × 1 doc each, but second space returns same token — deduplicated
    assert any(d["token"] == "doc_1" for d in docs)


def test_list_wiki_documents_skips_non_docx_nodes(connector):
    spaces_response = MagicMock()
    spaces_response.raise_for_status = MagicMock()
    spaces_response.json.return_value = {
        "code": 0,
        "data": {"items": [{"space_id": "sp1"}], "has_more": False},
    }

    nodes_response = MagicMock()
    nodes_response.raise_for_status = MagicMock()
    nodes_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [
                {"obj_token": "sheet_1", "obj_type": "sheet", "title": "Spreadsheet"},
                {"obj_token": "doc_1", "obj_type": "docx", "title": "Doc 1"},
            ],
            "has_more": False,
        },
    }

    with patch("httpx.get", side_effect=[spaces_response, nodes_response]):
        docs = connector.list_wiki_documents()

    assert len(docs) == 1
    assert docs[0]["token"] == "doc_1"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_feishu_wiki.py -v
```
Expected: `AttributeError: 'FeishuConnector' object has no attribute 'list_wiki_spaces'`

- [ ] **Step 3: Add wiki constants and methods to feishu_connector.py**

Add after the existing URL constants (after line 12):

```python
_LIST_WIKI_SPACES_URL = "/wiki/v2/spaces"
_LIST_WIKI_NODES_URL = "/wiki/v2/spaces/{space_id}/nodes"
```

Add after the `list_folder` method (after line 185), before the Content section:

```python
    # ------------------------------------------------------------------
    # Wiki
    # ------------------------------------------------------------------

    def list_wiki_spaces(self) -> list[dict[str, Any]]:
        """Return all wiki spaces the app has access to."""
        url = self.base_url + _LIST_WIKI_SPACES_URL
        spaces: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu list_wiki_spaces error: {data}")
            payload = data.get("data", {})
            spaces.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")

        logger.info("Feishu wiki: found %d spaces", len(spaces))
        return spaces

    def list_wiki_nodes(self, space_id: str) -> list[dict[str, Any]]:
        """Return all nodes (flat list) from a wiki space."""
        url = self.base_url + _LIST_WIKI_NODES_URL.format(space_id=space_id)
        nodes: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("Feishu list_wiki_nodes error for space %s: %s", space_id, data)
                break
            payload = data.get("data", {})
            nodes.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")

        return nodes

    def list_wiki_documents(self) -> list[dict[str, Any]]:
        """Return all docx/doc items from all wiki spaces (flat, deduplicated)."""
        spaces = self.list_wiki_spaces()
        docs: list[dict[str, Any]] = []
        seen: set[str] = set()

        for space in spaces:
            space_id = (space.get("space_id") or "").strip()
            if not space_id:
                continue
            nodes = self.list_wiki_nodes(space_id)
            for node in nodes:
                obj_type = (node.get("obj_type") or "").strip().lower()
                obj_token = (node.get("obj_token") or "").strip()
                if obj_type not in {"docx", "doc"} or not obj_token or obj_token in seen:
                    continue
                seen.add(obj_token)
                docs.append({
                    "token": obj_token,
                    "name": node.get("title") or obj_token,
                    "_source": "wiki",
                    "_space_id": space_id,
                })

        logger.info("Feishu wiki: found %d docs across %d spaces", len(docs), len(spaces))
        return docs
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_feishu_wiki.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/ingest/feishu_connector.py api/tests/test_feishu_wiki.py
git commit -m "feat: add Feishu wiki space/node listing to FeishuConnector"
```

---

## Task 5: Update feishu_indexer.py to sync wiki documents

**Why:** `FeishuIndexer.sync()` currently only calls `connector.list_documents(root_tokens)` (Drive). It needs to also call `connector.list_wiki_documents()` and index those.

**Files:**
- Modify: `api/app/services/indexing/feishu_indexer.py`

- [ ] **Step 1: Write failing test** (add to `api/tests/test_feishu_wiki.py`)

```python
def test_feishu_indexer_sync_includes_wiki_docs():
    """Indexer should call list_wiki_documents and index those docs too."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None  # no KBConfig

    with patch("app.services.indexing.feishu_indexer.FeishuConnector") as MockConnector, \
         patch("app.services.indexing.feishu_indexer.IndexManager") as MockIndexManager:

        instance = MockConnector.return_value
        instance.list_documents.return_value = []
        instance.list_wiki_documents.return_value = [
            {"token": "wiki_doc_1", "name": "Wiki Page 1", "_source": "wiki"}
        ]
        instance.get_doc_content.return_value = "Some wiki content"

        mock_index = MockIndexManager.return_value
        mock_index.update_sync_status = MagicMock()
        mock_index.index_document = AsyncMock(return_value=2)

        from app.services.indexing.feishu_indexer import FeishuIndexer
        indexer = FeishuIndexer(db=mock_db)

        import asyncio
        result = asyncio.run(indexer.sync(org_id=1))

    instance.list_wiki_documents.assert_called_once()
    mock_index.index_document.assert_called_once()
    assert result.docs_indexed == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_feishu_wiki.py::test_feishu_indexer_sync_includes_wiki_docs -v
```
Expected: FAIL — `assert_called_once()` fails (wiki never called)

- [ ] **Step 3: Update sync() in feishu_indexer.py**

After line 46 (`doc_items = connector.list_documents(root_tokens, recursive=True)`), add:

```python
            wiki_items: list = []
            try:
                wiki_items = connector.list_wiki_documents()
            except Exception as exc:
                msg = f"Feishu wiki listing failed: {exc}"
                logger.warning(msg)
                errors.append(msg)

            all_items = doc_items + wiki_items
```

Then change line 48 from `for item in doc_items:` to `for item in all_items:`.

- [ ] **Step 4: Run tests**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_feishu_wiki.py -v
```
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/services/indexing/feishu_indexer.py
git commit -m "feat: add wiki document discovery to FeishuIndexer.sync()"
```

---

## Task 6: Add wiki scope to settings and update worker beat schedule

**Why:** Two small changes needed together — Feishu app needs `wiki:wiki:readonly` OAuth scope, and the daily beat schedule should use the v2 full reindex instead of v1.

**Files:**
- Modify: `api/app/core/settings.py`
- Modify: `api/app/worker.py`

- [ ] **Step 1: Update settings.py**

Find the line:
```python
feishu_oauth_scopes: str = "offline_access drive:drive:readonly docs:document:readonly"
```

Change to:
```python
feishu_oauth_scopes: str = "offline_access drive:drive:readonly docs:document:readonly wiki:wiki:readonly"
```

- [ ] **Step 2: Update worker.py beat schedule**

Find the `beat_schedule` dict in `celery_app.conf.update(...)`:

```python
beat_schedule={
    "daily-ingestion": {
        "task": "daily_ingestion",
        "schedule": 24 * 60 * 60,
    }
},
```

Replace with:

```python
beat_schedule={
    "daily-ingestion-v2": {
        "task": "full_reindex_v2",
        "schedule": 24 * 60 * 60,
    }
},
```

Also add this import at the top of `worker.py` after the existing imports to ensure v2 tasks are registered with Celery:

```python
import app.tasks.indexing_tasks  # noqa: F401 — registers v2 Celery tasks
```

- [ ] **Step 3: Verify import works**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -c "from app.worker import celery_app; print(list(celery_app.tasks.keys()))" 2>&1 | grep -E "reindex|feishu|drive"
```
Expected: `full_reindex_v2`, `sync_feishu_v2`, `sync_google_drive_v2` appear in the list

- [ ] **Step 4: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/core/settings.py api/app/worker.py
git commit -m "feat: add wiki:wiki:readonly scope and switch beat schedule to full_reindex_v2"
```

---

## Task 7: Add backfill Celery task

**Why:** Existing `kb_chunks` rows need to be migrated to `knowledge_index`. The task runs in the background, processes 500 rows at a time, and flips `retrieval_cutover=True` on `kb_config` when done.

**Files:**
- Modify: `api/app/tasks/indexing_tasks.py`
- Create: `api/tests/test_backfill_task.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_backfill_task.py
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_chunk(text="hello", chunk_index=0, embedding=None, source_type="google_drive", source_id="doc1"):
    chunk = MagicMock()
    chunk.text = text
    chunk.chunk_index = chunk_index
    chunk.embedding = embedding or [0.1, 0.2, 0.3]
    chunk.metadata_json = {}
    doc = MagicMock()
    doc.source_type = source_type
    doc.source_id = source_id
    doc.title = "Test Doc"
    doc.url = None
    return chunk, doc


def test_backfill_inserts_chunks_into_knowledge_index():
    chunk, doc = _make_chunk()

    mock_db = MagicMock()
    # Simulate: 1 row in first batch, empty second batch
    mock_db.execute.return_value.all.side_effect = [
        [(chunk, doc.source_type, doc.source_id, doc.title, doc.url)],  # first batch
    ]
    mock_db.execute.return_value.scalar_one_or_none.return_value = None  # no existing KI row

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"), \
         patch("app.tasks.indexing_tasks.backfill_knowledge_index.apply_async") as mock_chain:

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    mock_db.add_all.assert_called_once()
    mock_chain.assert_called_once()
    assert result["status"] == "running"


def test_backfill_flips_cutover_when_no_rows_remain():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = []  # empty batch = done

    mock_config = MagicMock()
    mock_config.retrieval_cutover = False
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_config

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"):

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    assert mock_config.retrieval_cutover is True
    mock_db.commit.assert_called()
    assert result["status"] == "complete"


def test_backfill_skips_already_indexed_chunks():
    chunk, doc = _make_chunk(source_id="already_indexed")

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [
        (chunk, doc.source_type, doc.source_id, doc.title, doc.url)
    ]
    # Simulate: chunk already exists in knowledge_index
    existing_ki = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_ki

    with patch("app.tasks.indexing_tasks.SessionLocal") as MockSession, \
         patch("app.tasks.indexing_tasks.init_db"), \
         patch("app.tasks.indexing_tasks.backfill_knowledge_index.apply_async"):

        MockSession.return_value.__enter__.return_value = mock_db

        from app.tasks.indexing_tasks import backfill_knowledge_index
        result = backfill_knowledge_index(offset=0, batch_size=500)

    # add_all called with empty list (skipped)
    call_args = mock_db.add_all.call_args
    assert call_args is None or call_args[0][0] == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_backfill_task.py -v
```
Expected: `ImportError` — `backfill_knowledge_index` doesn't exist yet

- [ ] **Step 3: Add task to indexing_tasks.py**

Add at the bottom of `api/app/tasks/indexing_tasks.py`:

```python
import json as _json


@celery_app.task(name="backfill_knowledge_index", bind=True, max_retries=None, rate_limit="10/m")
def backfill_knowledge_index(self, offset: int = 0, batch_size: int = 500) -> dict:
    """Migrate kb_chunks rows to knowledge_index in batches. Self-chains until done."""
    init_db()
    from sqlalchemy import select
    from app.models.entities import KBChunk, KBDocument, KnowledgeIndex, KBConfig

    with SessionLocal() as db:
        # Fetch next batch of chunks with their parent document info
        rows = db.execute(
            select(KBChunk, KBDocument.source_type, KBDocument.source_id, KBDocument.title, KBDocument.url)
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .order_by(KBChunk.id)
            .offset(offset)
            .limit(batch_size)
        ).all()

        if not rows:
            # All done — flip cutover flag
            config = db.execute(select(KBConfig).limit(1)).scalar_one_or_none()
            if config is not None:
                config.retrieval_cutover = True
                db.commit()
            logger.info("Backfill complete — retrieval_cutover=True (total processed: %d)", offset)
            return {"status": "complete", "total_processed": offset}

        new_rows = []
        for chunk, source_type, source_id, title, url in rows:
            # Skip if already in knowledge_index (idempotent)
            existing = db.execute(
                select(KnowledgeIndex).where(
                    KnowledgeIndex.source_ref == source_id,
                    KnowledgeIndex.chunk_index == chunk.chunk_index,
                    KnowledgeIndex.org_id == 1,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            # Normalize embedding to JSON string (knowledge_index stores as JSON)
            emb = chunk.embedding
            if emb is None:
                embedding_val = None
            elif isinstance(emb, str):
                embedding_val = emb
            else:
                embedding_val = _json.dumps(emb)

            source_type_str = source_type.value if hasattr(source_type, "value") else str(source_type)

            new_rows.append(KnowledgeIndex(
                source_type=source_type_str,
                source_ref=source_id,
                title=title or "",
                chunk_text=chunk.text or "",
                chunk_index=chunk.chunk_index,
                embedding=embedding_val,
                embedding_model="text-embedding-3-small",
                metadata_=chunk.metadata_json or {},
                org_id=1,
            ))

        if new_rows:
            db.add_all(new_rows)
            db.commit()

        logger.info("Backfill: offset=%d new=%d skipped=%d", offset, len(new_rows), len(rows) - len(new_rows))

    # Chain next batch (2s pause between batches)
    backfill_knowledge_index.apply_async(
        kwargs={"offset": offset + batch_size, "batch_size": batch_size},
        countdown=2,
    )
    return {"status": "running", "offset": offset, "new_rows": len(new_rows)}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_backfill_task.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/tasks/indexing_tasks.py api/tests/test_backfill_task.py
git commit -m "feat: add backfill_knowledge_index Celery task for kb_chunks → knowledge_index migration"
```

---

## Task 8: Add retrieval fan-out to HybridRetrievalService

**Why:** During the migration period, documents exist in both tables. `search()` must query both and merge results. Once `retrieval_cutover=True` in `kb_config`, the legacy path is skipped.

**Files:**
- Modify: `api/app/services/indexing/retrieval.py`
- Create: `api/tests/test_retrieval_fanout.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_retrieval_fanout.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_service(cutover: bool = False):
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.retrieval_cutover = cutover
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_config

    from app.services.indexing.retrieval import HybridRetrievalService
    mock_embedder = MagicMock()
    mock_embedder.embed_chunks = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    svc = HybridRetrievalService(db=mock_db, embedding_service=mock_embedder)
    return svc, mock_db


@pytest.mark.asyncio
async def test_search_calls_legacy_when_not_cut_over():
    svc, mock_db = _make_service(cutover=False)

    with patch.object(svc, "_vector_search", return_value=[]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[]) as mock_legacy_vec, \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]) as mock_legacy_fts:

        await svc.search("test query", org_id=1, top_k=5)

    mock_legacy_vec.assert_called_once()
    mock_legacy_fts.assert_called_once()


@pytest.mark.asyncio
async def test_search_skips_legacy_after_cutover():
    svc, mock_db = _make_service(cutover=True)

    with patch.object(svc, "_vector_search", return_value=[]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[]) as mock_legacy_vec, \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]) as mock_legacy_fts:

        await svc.search("test query", org_id=1, top_k=5)

    mock_legacy_vec.assert_not_called()
    mock_legacy_fts.assert_not_called()


@pytest.mark.asyncio
async def test_search_deduplicates_results_across_tables():
    from app.services.indexing.retrieval import RetrievalResult

    same_result = RetrievalResult(
        chunk_text="shared content",
        source_type="feishu",
        source_ref="doc_1",
        title="Doc 1",
        score=0.9,
        metadata={},
    )

    svc, mock_db = _make_service(cutover=False)

    with patch.object(svc, "_vector_search", return_value=[same_result]), \
         patch.object(svc, "_fulltext_search", return_value=[]), \
         patch.object(svc, "_legacy_vector_search", return_value=[same_result]), \
         patch.object(svc, "_legacy_fulltext_search", return_value=[]):

        results = await svc.search("shared content", org_id=1, top_k=10)

    # Same content from two tables should appear only once
    texts = [r.chunk_text for r in results]
    assert texts.count("shared content") == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_retrieval_fanout.py -v
```
Expected: FAIL — `_legacy_vector_search` doesn't exist yet

- [ ] **Step 3: Update HybridRetrievalService.search() and add legacy methods**

In `api/app/services/indexing/retrieval.py`, replace the `search()` method:

```python
    async def search(
        self,
        query: str,
        org_id: int,
        top_k: int = 10,
        source_types: list[str] | None = None,
    ) -> list[RetrievalResult]:
        from sqlalchemy import select as sa_select
        from app.models.entities import KBConfig

        config = self.db.execute(sa_select(KBConfig).limit(1)).scalar_one_or_none()
        cutover = config.retrieval_cutover if config is not None else False

        query_embeddings = await self.embedding_service.embed_chunks([query])
        query_vec = query_embeddings[0] if query_embeddings else []

        vector_results = self._vector_search(query_vec, org_id, source_types)
        fulltext_results = self._fulltext_search(query, org_id, source_types)

        if not cutover:
            vector_results = vector_results + self._legacy_vector_search(query_vec, top_k * 2)
            fulltext_results = fulltext_results + self._legacy_fulltext_search(query, top_k * 2)

        fused = self._reciprocal_rank_fusion(vector_results, fulltext_results)

        seen: set[str] = set()
        deduplicated: list[RetrievalResult] = []
        for result in fused:
            dedup_key = f"{result.source_ref}:{result.chunk_text[:100]}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            deduplicated.append(result)

        return deduplicated[:top_k]
```

Add these two methods after `_fulltext_search_generic()` (before `_reciprocal_rank_fusion`):

```python
    def _legacy_vector_search(self, query_vec: list[float], limit: int = 20) -> list[RetrievalResult]:
        """Fan-out vector search to kb_chunks during migration transition."""
        if not query_vec:
            return []
        try:
            import json as _json
            from sqlalchemy import select as sa_select
            from app.models.entities import KBChunk, KBDocument

            rows = self.db.execute(
                sa_select(KBChunk, KBDocument.title, KBDocument.source_type, KBDocument.source_id)
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(KBChunk.embedding.isnot(None))
                .limit(200)
            ).all()

            scored: list[tuple[float, KBChunk, str, str, str]] = []
            for chunk, title, source_type, source_id in rows:
                emb = chunk.embedding
                if emb is None:
                    continue
                if isinstance(emb, str):
                    try:
                        emb = _json.loads(emb)
                    except Exception:
                        continue
                score = self._cosine_similarity(query_vec, emb)
                scored.append((score, chunk, title or "", source_type, source_id or ""))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, chunk, title, source_type, source_id in scored[:limit]:
                st = source_type.value if hasattr(source_type, "value") else str(source_type)
                results.append(RetrievalResult(
                    chunk_text=chunk.text or "",
                    source_type=st,
                    source_ref=source_id,
                    title=title,
                    score=score,
                    metadata=chunk.metadata_json or {},
                ))
            return results
        except Exception as exc:
            logger.warning("Legacy vector search failed: %s", exc)
            return []

    def _legacy_fulltext_search(self, query: str, limit: int = 20) -> list[RetrievalResult]:
        """Fan-out fulltext search to kb_chunks during migration transition."""
        try:
            from sqlalchemy import select as sa_select
            from app.models.entities import KBChunk, KBDocument

            like_term = f"%{query}%"
            rows = self.db.execute(
                sa_select(KBChunk, KBDocument.title, KBDocument.source_type, KBDocument.source_id)
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(KBChunk.text.ilike(like_term))
                .limit(limit)
            ).all()

            results = []
            for chunk, title, source_type, source_id in rows:
                st = source_type.value if hasattr(source_type, "value") else str(source_type)
                results.append(RetrievalResult(
                    chunk_text=chunk.text or "",
                    source_type=st,
                    source_ref=source_id or "",
                    title=title or "",
                    score=0.5,
                    metadata=chunk.metadata_json or {},
                ))
            return results
        except Exception as exc:
            logger.warning("Legacy fulltext search failed: %s", exc)
            return []
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -m pytest tests/test_retrieval_fanout.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/services/indexing/retrieval.py api/tests/test_retrieval_fanout.py
git commit -m "feat: add retrieval fan-out to both kb_chunks and knowledge_index with retrieval_cutover flag"
```

---

## Task 9: Add /admin/backfill-status endpoint

**Why:** Operators need to monitor backfill progress and know when cutover is complete.

**Files:**
- Modify: `api/app/api/routes/admin.py`

- [ ] **Step 1: Add endpoint to admin.py**

Find a logical location (e.g., after the `GET /admin/kb-config` route). Add:

```python
@router.get("/admin/backfill-status")
def get_backfill_status(db: Session = Depends(db_session)):
    from sqlalchemy import func, select
    from app.models.entities import KBChunk, KnowledgeIndex

    kb_count = db.execute(select(func.count()).select_from(KBChunk)).scalar() or 0
    ki_count = db.execute(select(func.count()).select_from(KnowledgeIndex)).scalar() or 0
    config = db.execute(select(KBConfig).limit(1)).scalar_one_or_none()
    cutover = config.retrieval_cutover if config is not None else False

    return {
        "kb_chunks_count": kb_count,
        "knowledge_index_count": ki_count,
        "cutover_complete": cutover,
        "backfill_remaining": max(0, kb_count - ki_count),
    }
```

**Note:** `KBConfig` is already imported at the top of admin.py. `KBChunk` and `KnowledgeIndex` are imported inline to avoid circular import risk.

- [ ] **Step 2: Verify endpoint is reachable**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/api && python -c "
from app.api.routes.admin import router
routes = [r.path for r in router.routes]
print([r for r in routes if 'backfill' in r])
"
```
Expected: `['/admin/backfill-status']`

- [ ] **Step 3: Commit**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git add api/app/api/routes/admin.py
git commit -m "feat: add GET /admin/backfill-status endpoint to monitor migration progress"
```

---

## Task 10: Deploy and trigger

- [ ] **Step 1: Push to repo**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss && git push
```

- [ ] **Step 2: Deploy on EC2**

```bash
# SSH to EC2
cd ~/app
git pull
docker compose -f docker-compose.prod.yml up -d --build api worker
```

- [ ] **Step 3: Add Feishu credentials to EC2 .env**

```bash
# On EC2, edit ~/app/.env — add:
FEISHU_APP_ID=cli_a9175ad86b389cd3
FEISHU_APP_SECRET=<your_secret>
```

Restart after env change: `docker compose -f docker-compose.prod.yml restart api worker`

- [ ] **Step 4: Run DB migrations on EC2**

```bash
docker compose -f docker-compose.prod.yml exec api python -m alembic upgrade head
```

**Note:** The HNSW migration (Task 3) may take a few minutes if `knowledge_index` already has rows. Monitor with:
```bash
docker compose -f docker-compose.prod.yml logs api -f
```

- [ ] **Step 5: Trigger initial Feishu sync**

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app.worker.celery_app call sync_feishu_v2
```

- [ ] **Step 6: Trigger backfill**

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app.worker.celery_app call backfill_knowledge_index
```

- [ ] **Step 7: Monitor progress**

```bash
# Check every few minutes until cutover_complete=true
curl http://localhost:8000/admin/backfill-status
```

- [ ] **Step 8: Verify Feishu docs appear in chat citations**

In the app, ask a question about something in your Feishu wiki. The response citations should show `source_type: feishu`.

---

## Post-Migration (7 days later)

Once `cutover_complete=true` and retrieval quality is confirmed:

```bash
# On EC2:
docker compose -f docker-compose.prod.yml exec api python -m alembic upgrade head
# (after creating a new migration to drop kb_chunks and remove legacy code)
```

Files to delete after retirement:
- `_legacy_vector_search` and `_legacy_fulltext_search` from `retrieval.py`
- `HybridRetriever` class in `api/app/retrieval/service.py` (v1)
- `KBChunk`, `KBDocument` SQLAlchemy models from `entities.py`
- Legacy ingestor-path references

---

## FTS Upgrade (after region migration to Frankfurt/Singapore)

```sql
ALTER TABLE knowledge_index
  ADD FULLTEXT INDEX idx_ki_fts (chunk_text)
  WITH PARSER MULTILINGUAL;
```

No other code changes. `_fulltext_search_tidb()` will use it automatically.
