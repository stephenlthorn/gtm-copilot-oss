# Prompt Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full prompt management system (Prompt Studio) accessible from Settings, making all 24+ prompts editable with version history, per-user overrides, and a TiDB Expert skill — then overhaul every prompt for production quality.

**Architecture:** Three new DB tables (`prompt_registry`, `prompt_versions`, `prompt_user_overrides`) store all prompts with version history. A `PromptService` resolves prompts at runtime (user override → shared → hardcoded fallback) with 5-minute cache. The UI adds a "Prompt Studio" tab to Settings with a category browser, full-screen editor, variable sidebar, and version history drawer. `llm.py` is refactored to call `PromptService` instead of importing Python constants.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (API), Next.js 14 + React 18 (UI), TiDB/MySQL/SQLite (DB), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-03-23-prompt-studio-design.md`

---

## File Structure

### API — New Files
- `api/app/models/prompt_models.py` — SQLAlchemy models: `PromptRegistry`, `PromptVersion`, `PromptUserOverride`
- `api/app/services/prompt_service.py` — `PromptService` class: resolution, caching, CRUD, version management
- `api/app/api/routes/prompts.py` — FastAPI router: 9 endpoints for prompt CRUD, versioning, overrides
- `api/app/db/seed_prompts.py` — Seed function: populates `prompt_registry` from hardcoded defaults

### API — Modified Files
- `api/app/models/entities.py` — Import new models so `Base.metadata.create_all` picks them up
- `api/app/api/router.py` — Register new prompts router
- `api/app/services/llm.py` — Refactor to use `PromptService` instead of hardcoded imports
- `api/app/db/init_db.py` — Call seed function after table creation
- `api/app/prompts/templates.py` — Add `ALL_DEFAULTS` dict mapping keys to content (for seeding)

### UI — New Files
- `ui/components/PromptStudio.js` — Main Prompt Studio component (category browser + editor)
- `ui/components/PromptEditor.js` — Full-screen prompt editor with variable sidebar
- `ui/components/PromptVersionHistory.js` — Version history drawer with diffs and rollback
- `ui/app/api/prompts/route.js` — Next.js route handler: list all prompts
- `ui/app/api/prompts/[id]/route.js` — Next.js route handler: get/update single prompt
- `ui/app/api/prompts/[id]/reset/route.js` — Next.js route handler: reset to default
- `ui/app/api/prompts/[id]/versions/route.js` — Next.js route handler: version history
- `ui/app/api/prompts/[id]/rollback/route.js` — Next.js route handler: rollback
- `ui/app/api/prompts/[id]/my-override/route.js` — Next.js route handler: user overrides

### UI — Modified Files
- `ui/app/(app)/settings/page.js` — Add Prompt Studio tab

### Tests — New Files
- `tests/unit/test_prompt_service.py` — Unit tests for resolution logic, caching, CRUD
- `tests/integration/test_prompts_api.py` — Integration tests for all 9 API endpoints

---

## Task 1: Database Models

**Files:**
- Create: `api/app/models/prompt_models.py`
- Modify: `api/app/models/entities.py`
- Test: `tests/unit/test_prompt_models.py`

- [ ] **Step 1: Write failing test for model creation**

```python
# tests/unit/test_prompt_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from api.app.db.base import Base
from api.app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_prompt_registry_create(db):
    prompt = PromptRegistry(
        id="system_oracle",
        category="system_prompt",
        name="Oracle",
        description="General chat system prompt",
        default_content="You are a GTM analyst.",
        current_content="You are a GTM analyst.",
        variables="[]",
    )
    db.add(prompt)
    db.commit()
    result = db.get(PromptRegistry, "system_oracle")
    assert result is not None
    assert result.name == "Oracle"
    assert result.category == "system_prompt"


def test_prompt_version_create(db):
    prompt = PromptRegistry(
        id="system_oracle",
        category="system_prompt",
        name="Oracle",
        description="Test",
        default_content="v1",
        current_content="v1",
        variables="[]",
    )
    db.add(prompt)
    db.flush()
    version = PromptVersion(
        prompt_id="system_oracle",
        version=1,
        content="v1",
        edited_by="admin@example.com",
    )
    db.add(version)
    db.commit()
    assert version.id is not None
    assert version.prompt_id == "system_oracle"


def test_prompt_user_override_unique_constraint(db):
    prompt = PromptRegistry(
        id="persona_sales",
        category="persona",
        name="Sales",
        description="Test",
        default_content="default",
        current_content="default",
        variables="[]",
    )
    db.add(prompt)
    db.flush()
    override1 = PromptUserOverride(
        prompt_id="persona_sales",
        user_email="rep@example.com",
        content="custom sales prompt",
    )
    db.add(override1)
    db.commit()
    override2 = PromptUserOverride(
        prompt_id="persona_sales",
        user_email="rep@example.com",
        content="another custom",
    )
    db.add(override2)
    with pytest.raises(Exception):  # IntegrityError from unique constraint
        db.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb
python -m pytest tests/unit/test_prompt_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.app.models.prompt_models'`

- [ ] **Step 3: Implement the models**

```python
# api/app/models/prompt_models.py
from datetime import datetime
from sqlalchemy import String, Text, Integer, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from api.app.db.base import Base


class PromptRegistry(Base):
    __tablename__ = "prompt_registry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_content: Mapped[str] = mapped_column(Text, nullable=False)
    current_content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("prompt_registry.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str] = mapped_column(String(255), nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptUserOverride(Base):
    __tablename__ = "prompt_user_overrides"
    __table_args__ = (UniqueConstraint("prompt_id", "user_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("prompt_registry.id"), nullable=False
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Import models in entities.py so Base.metadata sees them**

Add to the top of `api/app/models/entities.py`:

```python
from api.app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_prompt_models.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add api/app/models/prompt_models.py api/app/models/entities.py tests/unit/test_prompt_models.py
git commit -m "feat: add prompt_registry, prompt_versions, prompt_user_overrides models"
```

---

## Task 2: Seed Defaults + ALL_DEFAULTS Registry

**Files:**
- Create: `api/app/db/seed_prompts.py`
- Modify: `api/app/prompts/templates.py`
- Test: `tests/unit/test_seed_prompts.py`

- [ ] **Step 1: Write failing test for seeding**

```python
# tests/unit/test_seed_prompts.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from api.app.db.base import Base
from api.app.models.prompt_models import PromptRegistry
from api.app.db.seed_prompts import seed_prompts


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_seed_populates_all_prompts(db):
    seed_prompts(db)
    prompts = db.query(PromptRegistry).all()
    assert len(prompts) >= 24  # 11 system + 7 templates + 3 personas + 3 source profiles


def test_seed_is_idempotent(db):
    seed_prompts(db)
    count1 = db.query(PromptRegistry).count()
    seed_prompts(db)
    count2 = db.query(PromptRegistry).count()
    assert count1 == count2


def test_seed_sets_default_and_current_content_equal(db):
    seed_prompts(db)
    prompt = db.get(PromptRegistry, "system_oracle")
    assert prompt is not None
    assert prompt.default_content == prompt.current_content
    assert len(prompt.default_content) > 50  # Not empty


def test_seed_includes_tidb_expert(db):
    seed_prompts(db)
    prompt = db.get(PromptRegistry, "tidb_expert")
    assert prompt is not None
    assert prompt.category == "system_prompt"
    assert "TiDB" in prompt.current_content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_seed_prompts.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Add ALL_DEFAULTS to templates.py**

Add at the bottom of `api/app/prompts/templates.py`:

```python
from api.app.prompts.personas import PERSONA_DEFAULT_PROMPTS
from api.app.prompts.source_profiles import PRE_CALL_SOURCES, POST_CALL_SOURCES, POC_TECHNICAL_SOURCES

ALL_DEFAULTS = {
    # System prompts
    "system_oracle": {
        "category": "system_prompt",
        "name": "Oracle",
        "description": "Base system prompt for general chat and oracle queries",
        "content": SYSTEM_ORACLE,
        "variables": "[]",
    },
    "system_pre_call_intel": {
        "category": "system_prompt",
        "name": "Pre-Call Intel",
        "description": "System prompt for pre-call research briefs with accuracy rules and deep research protocol",
        "content": SYSTEM_PRE_CALL_INTEL,
        "variables": "[]",
    },
    "system_post_call_analysis": {
        "category": "system_prompt",
        "name": "Post-Call Analysis",
        "description": "System prompt for MEDDPICC post-call coaching briefs",
        "content": SYSTEM_POST_CALL_ANALYSIS,
        "variables": "[]",
    },
    "system_se_analysis": {
        "category": "system_prompt",
        "name": "SE Analysis",
        "description": "System prompt for SE technical evaluations, POC plans, and competitor coaching",
        "content": SYSTEM_SE_ANALYSIS,
        "variables": "[]",
    },
    "system_call_coach": {
        "category": "system_prompt",
        "name": "Call Coach",
        "description": "System prompt for call coaching recommendations",
        "content": SYSTEM_CALL_COACH,
        "variables": "[]",
    },
    "system_messaging_guardrail": {
        "category": "system_prompt",
        "name": "Messaging Guardrail",
        "description": "Policy enforcement for outbound email send/draft",
        "content": SYSTEM_MESSAGING_GUARDRAIL,
        "variables": "[]",
    },
    "system_market_research": {
        "category": "system_prompt",
        "name": "Market Research",
        "description": "System prompt for territory-specific strategic account planning",
        "content": SYSTEM_MARKET_RESEARCH,
        "variables": "[]",
    },
    "system_rep_execution": {
        "category": "system_prompt",
        "name": "Rep Execution",
        "description": "System prompt for sales rep account briefs, discovery questions, deal risk, follow-up drafts",
        "content": SYSTEM_REP_EXECUTION,
        "variables": "[]",
    },
    "system_se_execution": {
        "category": "system_prompt",
        "name": "SE Execution",
        "description": "System prompt for SE POC readiness, architecture fit, and competitor coaching",
        "content": SYSTEM_SE_EXECUTION,
        "variables": "[]",
    },
    "system_marketing_execution": {
        "category": "system_prompt",
        "name": "Marketing Execution",
        "description": "System prompt for marketing intelligence and campaign analysis",
        "content": SYSTEM_MARKETING_EXECUTION,
        "variables": "[]",
    },
    "tidb_expert": {
        "category": "system_prompt",
        "name": "TiDB Expert Skill",
        "description": "Complete TiDB knowledge base — injected when TiDB Expert toggle is on (Claude skill pattern)",
        "content": TIDB_EXPERT_CONTEXT,
        "variables": "[]",
    },
    # Section templates — variables listed for each
    "tpl_pre_call": {
        "category": "template",
        "name": "Pre-Call Intel",
        "description": "User-facing template for pre-call research prompts",
        "content": "",  # Will be filled from ChatWorkspace HARDCODED_DEFAULTS
        "variables": '["{account}", "{website}", "{prospect_name}", "{prospect_linkedin}"]',
    },
    "tpl_post_call": {
        "category": "template",
        "name": "Post-Call Analysis",
        "description": "User-facing template for post-call analysis prompts",
        "content": "",
        "variables": '["{account}", "{call_context}"]',
    },
    "tpl_follow_up": {
        "category": "template",
        "name": "Follow-Up Email",
        "description": "User-facing template for follow-up email drafting",
        "content": "",
        "variables": '["{account}", "{call_context}", "{email_to}", "{email_cc}", "{email_tone}"]',
    },
    "tpl_tal": {
        "category": "template",
        "name": "Market Research / TAL",
        "description": "User-facing template for target account list generation",
        "content": "",
        "variables": '["{account}", "{regions}", "{industry}", "{revenue_min}", "{revenue_max}", "{context}", "{top_n}"]',
    },
    "tpl_se_poc_plan": {
        "category": "template",
        "name": "SE: POC Plan",
        "description": "User-facing template for SE POC planning",
        "content": "",
        "variables": '["{account}", "{target_offering}", "{call_context}"]',
    },
    "tpl_se_arch_fit": {
        "category": "template",
        "name": "SE: Architecture Fit",
        "description": "User-facing template for SE architecture fit analysis",
        "content": "",
        "variables": '["{account}", "{call_context}"]',
    },
    "tpl_se_competitor": {
        "category": "template",
        "name": "SE: Competitor Coach",
        "description": "User-facing template for SE competitive coaching briefs",
        "content": "",
        "variables": '["{account}", "{competitor}", "{call_context}"]',
    },
    # Personas
    "persona_sales": {
        "category": "persona",
        "name": "Sales",
        "description": "Persona prompt for sales representatives — deal progression, MEDDPICC, next-action bias",
        "content": PERSONA_DEFAULT_PROMPTS.get("sales_representative", ""),
        "variables": "[]",
    },
    "persona_se": {
        "category": "persona",
        "name": "SE",
        "description": "Persona prompt for sales engineers — technical validation, migration risk, POC patterns",
        "content": PERSONA_DEFAULT_PROMPTS.get("se", ""),
        "variables": "[]",
    },
    "persona_marketing": {
        "category": "persona",
        "name": "Marketing",
        "description": "Persona prompt for marketing — positioning, pipeline generation, campaign angles",
        "content": PERSONA_DEFAULT_PROMPTS.get("marketing_specialist", ""),
        "variables": "[]",
    },
    # Source profiles
    "sources_pre_call": {
        "category": "source_profile",
        "name": "Pre-Call Sources",
        "description": "Search source instructions for pre-call research (13 sources)",
        "content": str(PRE_CALL_SOURCES),
        "variables": "[]",
    },
    "sources_post_call": {
        "category": "source_profile",
        "name": "Post-Call Sources",
        "description": "Search source instructions for post-call analysis",
        "content": str(POST_CALL_SOURCES),
        "variables": "[]",
    },
    "sources_poc_technical": {
        "category": "source_profile",
        "name": "POC Technical Sources",
        "description": "Search source instructions for POC technical validation",
        "content": str(POC_TECHNICAL_SOURCES),
        "variables": "[]",
    },
}
```

- [ ] **Step 4: Implement seed function**

```python
# api/app/db/seed_prompts.py
from sqlalchemy.orm import Session
from api.app.models.prompt_models import PromptRegistry
from api.app.prompts.templates import ALL_DEFAULTS


def seed_prompts(db: Session) -> int:
    """Seed prompt_registry with factory defaults. Idempotent — skips existing rows."""
    seeded = 0
    for prompt_id, meta in ALL_DEFAULTS.items():
        existing = db.get(PromptRegistry, prompt_id)
        if existing is not None:
            continue
        prompt = PromptRegistry(
            id=prompt_id,
            category=meta["category"],
            name=meta["name"],
            description=meta["description"],
            default_content=meta["content"],
            current_content=meta["content"],
            variables=meta["variables"],
        )
        db.add(prompt)
        seeded += 1
    db.commit()
    return seeded
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_seed_prompts.py -v
```

Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add api/app/db/seed_prompts.py api/app/prompts/templates.py tests/unit/test_seed_prompts.py
git commit -m "feat: add seed_prompts and ALL_DEFAULTS registry for 24+ prompts"
```

---

## Task 3: PromptService — Resolution, Caching, CRUD

**Files:**
- Create: `api/app/services/prompt_service.py`
- Test: `tests/unit/test_prompt_service.py`

- [ ] **Step 1: Write failing tests for prompt resolution**

```python
# tests/unit/test_prompt_service.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from api.app.db.base import Base
from api.app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride
from api.app.services.prompt_service import PromptService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seeded_db(db):
    db.add(PromptRegistry(
        id="system_oracle", category="system_prompt", name="Oracle",
        description="Test", default_content="factory default",
        current_content="shared version", variables="[]",
    ))
    db.commit()
    return db


def test_resolve_returns_current_content(seeded_db):
    svc = PromptService(seeded_db)
    result = svc.resolve("system_oracle")
    assert result == "shared version"


def test_resolve_returns_user_override_when_exists(seeded_db):
    seeded_db.add(PromptUserOverride(
        prompt_id="system_oracle", user_email="rep@co.com", content="my custom prompt",
    ))
    seeded_db.commit()
    svc = PromptService(seeded_db)
    result = svc.resolve("system_oracle", user_email="rep@co.com")
    assert result == "my custom prompt"


def test_resolve_returns_shared_when_no_override(seeded_db):
    svc = PromptService(seeded_db)
    result = svc.resolve("system_oracle", user_email="rep@co.com")
    assert result == "shared version"


def test_resolve_returns_none_for_unknown_key(seeded_db):
    svc = PromptService(seeded_db)
    result = svc.resolve("nonexistent")
    assert result is None


def test_save_creates_version(seeded_db):
    svc = PromptService(seeded_db)
    svc.save("system_oracle", "updated content", edited_by="admin@co.com", note="improved clarity")
    prompt = seeded_db.get(PromptRegistry, "system_oracle")
    assert prompt.current_content == "updated content"
    versions = seeded_db.query(PromptVersion).filter_by(prompt_id="system_oracle").all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].content == "updated content"
    assert versions[0].note == "improved clarity"


def test_save_increments_version(seeded_db):
    svc = PromptService(seeded_db)
    svc.save("system_oracle", "v1", edited_by="a@co.com")
    svc.save("system_oracle", "v2", edited_by="b@co.com")
    versions = seeded_db.query(PromptVersion).filter_by(prompt_id="system_oracle").order_by(PromptVersion.version).all()
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2


def test_reset_restores_default(seeded_db):
    svc = PromptService(seeded_db)
    svc.save("system_oracle", "customized", edited_by="a@co.com")
    svc.reset("system_oracle", reset_by="admin@co.com")
    prompt = seeded_db.get(PromptRegistry, "system_oracle")
    assert prompt.current_content == "factory default"


def test_rollback_to_version(seeded_db):
    svc = PromptService(seeded_db)
    svc.save("system_oracle", "v1", edited_by="a@co.com")
    svc.save("system_oracle", "v2", edited_by="a@co.com")
    svc.save("system_oracle", "v3", edited_by="a@co.com")
    svc.rollback("system_oracle", version=1, rolled_back_by="a@co.com")
    prompt = seeded_db.get(PromptRegistry, "system_oracle")
    assert prompt.current_content == "v1"


def test_list_prompts(seeded_db):
    svc = PromptService(seeded_db)
    prompts = svc.list_all()
    assert len(prompts) == 1
    assert prompts[0]["id"] == "system_oracle"
    assert "current_content" not in prompts[0]  # List doesn't include full body


def test_get_versions(seeded_db):
    svc = PromptService(seeded_db)
    svc.save("system_oracle", "v1", edited_by="a@co.com")
    svc.save("system_oracle", "v2", edited_by="b@co.com")
    versions = svc.get_versions("system_oracle")
    assert len(versions) == 2
    assert versions[0]["version"] == 2  # Most recent first
    assert versions[1]["version"] == 1


def test_save_user_override(seeded_db):
    svc = PromptService(seeded_db)
    svc.save_user_override("system_oracle", "rep@co.com", "my version")
    override = seeded_db.query(PromptUserOverride).filter_by(
        prompt_id="system_oracle", user_email="rep@co.com"
    ).first()
    assert override is not None
    assert override.content == "my version"


def test_delete_user_override(seeded_db):
    svc = PromptService(seeded_db)
    svc.save_user_override("system_oracle", "rep@co.com", "my version")
    svc.delete_user_override("system_oracle", "rep@co.com")
    override = seeded_db.query(PromptUserOverride).filter_by(
        prompt_id="system_oracle", user_email="rep@co.com"
    ).first()
    assert override is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_prompt_service.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PromptService**

```python
# api/app/services/prompt_service.py
from __future__ import annotations

import time
from sqlalchemy.orm import Session
from api.app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride

CACHE_TTL_SECONDS = 300  # 5 minutes
_cache: dict[str, tuple[float, str]] = {}


class PromptService:
    def __init__(self, db: Session):
        self.db = db

    # ── Resolution ────────────────────────────────────────────

    def resolve(
        self, prompt_id: str, *, user_email: str | None = None
    ) -> str | None:
        # Check user override first
        if user_email:
            override = (
                self.db.query(PromptUserOverride)
                .filter_by(prompt_id=prompt_id, user_email=user_email)
                .first()
            )
            if override:
                return override.content

        # Check cache
        cache_key = f"prompt:{prompt_id}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        # Query DB
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            return None

        # Cache and return
        _cache[cache_key] = (time.time(), prompt.current_content)
        return prompt.current_content

    # ── CRUD ──────────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        prompts = self.db.query(PromptRegistry).order_by(PromptRegistry.category, PromptRegistry.name).all()
        return [
            {
                "id": p.id,
                "category": p.category,
                "name": p.name,
                "description": p.description,
                "variables": p.variables,
                "updated_by": p.updated_by,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in prompts
        ]

    def get(self, prompt_id: str) -> dict | None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            return None
        return {
            "id": prompt.id,
            "category": prompt.category,
            "name": prompt.name,
            "description": prompt.description,
            "default_content": prompt.default_content,
            "current_content": prompt.current_content,
            "variables": prompt.variables,
            "updated_by": prompt.updated_by,
            "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
        }

    def save(
        self,
        prompt_id: str,
        content: str,
        *,
        edited_by: str,
        note: str | None = None,
    ) -> None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_id}' not found")

        # Determine next version number
        max_version = (
            self.db.query(PromptVersion.version)
            .filter_by(prompt_id=prompt_id)
            .order_by(PromptVersion.version.desc())
            .first()
        )
        next_version = (max_version[0] + 1) if max_version else 1

        # Create version record
        version = PromptVersion(
            prompt_id=prompt_id,
            version=next_version,
            content=content,
            edited_by=edited_by,
            note=note,
        )
        self.db.add(version)

        # Update current content
        prompt.current_content = content
        prompt.updated_by = edited_by
        self.db.commit()

        # Invalidate cache
        _cache.pop(f"prompt:{prompt_id}", None)

    def reset(self, prompt_id: str, *, reset_by: str) -> None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        self.save(prompt_id, prompt.default_content, edited_by=reset_by, note="Reset to factory default")

    def rollback(self, prompt_id: str, version: int, *, rolled_back_by: str) -> None:
        ver = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id, version=version)
            .first()
        )
        if ver is None:
            raise ValueError(f"Version {version} not found for '{prompt_id}'")
        self.save(prompt_id, ver.content, edited_by=rolled_back_by, note=f"Rollback to v{version}")

    def get_versions(self, prompt_id: str) -> list[dict]:
        versions = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id)
            .order_by(PromptVersion.version.desc())
            .all()
        )
        return [
            {
                "version": v.version,
                "content": v.content,
                "edited_by": v.edited_by,
                "edited_at": v.edited_at.isoformat() if v.edited_at else None,
                "note": v.note,
            }
            for v in versions
        ]

    def get_version(self, prompt_id: str, version: int) -> dict | None:
        ver = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id, version=version)
            .first()
        )
        if ver is None:
            return None
        return {
            "version": ver.version,
            "content": ver.content,
            "edited_by": ver.edited_by,
            "edited_at": ver.edited_at.isoformat() if ver.edited_at else None,
            "note": ver.note,
        }

    # ── User Overrides ────────────────────────────────────────

    def get_user_override(self, prompt_id: str, user_email: str) -> dict | None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override is None:
            return None
        return {
            "prompt_id": override.prompt_id,
            "user_email": override.user_email,
            "content": override.content,
            "updated_at": override.updated_at.isoformat() if override.updated_at else None,
        }

    def save_user_override(self, prompt_id: str, user_email: str, content: str) -> None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override:
            override.content = content
        else:
            override = PromptUserOverride(
                prompt_id=prompt_id, user_email=user_email, content=content
            )
            self.db.add(override)
        self.db.commit()

    def delete_user_override(self, prompt_id: str, user_email: str) -> None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override:
            self.db.delete(override)
            self.db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_prompt_service.py -v
```

Expected: 12 PASSED

- [ ] **Step 5: Commit**

```bash
git add api/app/services/prompt_service.py tests/unit/test_prompt_service.py
git commit -m "feat: add PromptService with resolution, versioning, caching, and user overrides"
```

---

## Task 4: API Routes for Prompts

**Files:**
- Create: `api/app/api/routes/prompts.py`
- Modify: `api/app/api/router.py`
- Test: `tests/integration/test_prompts_api.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/integration/test_prompts_api.py
import pytest
from fastapi.testclient import TestClient
from api.app.main import app
from api.app.db.session import get_db, SessionLocal, engine
from api.app.db.base import Base
from api.app.db.seed_prompts import seed_prompts


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_prompts(db)
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


USER_HEADER = {"X-User-Email": "test@example.com"}


def test_list_prompts(client):
    res = client.get("/prompts", headers=USER_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 24
    assert all("id" in p for p in data)
    assert all("current_content" not in p for p in data)


def test_get_prompt(client):
    res = client.get("/prompts/system_oracle", headers=USER_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "system_oracle"
    assert "current_content" in data
    assert "default_content" in data


def test_get_prompt_not_found(client):
    res = client.get("/prompts/nonexistent", headers=USER_HEADER)
    assert res.status_code == 404


def test_update_prompt(client):
    res = client.put(
        "/prompts/system_oracle",
        json={"content": "updated prompt", "note": "test edit"},
        headers=USER_HEADER,
    )
    assert res.status_code == 200
    # Verify update
    get_res = client.get("/prompts/system_oracle", headers=USER_HEADER)
    assert get_res.json()["current_content"] == "updated prompt"


def test_reset_prompt(client):
    # First update
    client.put("/prompts/system_oracle", json={"content": "custom"}, headers=USER_HEADER)
    # Then reset
    res = client.post("/prompts/system_oracle/reset", headers=USER_HEADER)
    assert res.status_code == 200
    # Verify reset
    get_res = client.get("/prompts/system_oracle", headers=USER_HEADER)
    data = get_res.json()
    assert data["current_content"] == data["default_content"]


def test_version_history(client):
    client.put("/prompts/system_oracle", json={"content": "v1"}, headers=USER_HEADER)
    client.put("/prompts/system_oracle", json={"content": "v2"}, headers=USER_HEADER)
    res = client.get("/prompts/system_oracle/versions", headers=USER_HEADER)
    assert res.status_code == 200
    versions = res.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2


def test_rollback(client):
    client.put("/prompts/system_oracle", json={"content": "v1"}, headers=USER_HEADER)
    client.put("/prompts/system_oracle", json={"content": "v2"}, headers=USER_HEADER)
    res = client.post("/prompts/system_oracle/rollback/1", headers=USER_HEADER)
    assert res.status_code == 200
    get_res = client.get("/prompts/system_oracle", headers=USER_HEADER)
    assert get_res.json()["current_content"] == "v1"


def test_user_override_crud(client):
    # Save override
    res = client.put(
        "/prompts/persona_sales/my-override",
        json={"content": "my custom sales prompt"},
        headers=USER_HEADER,
    )
    assert res.status_code == 200
    # Get override
    res = client.get("/prompts/persona_sales/my-override", headers=USER_HEADER)
    assert res.status_code == 200
    assert res.json()["content"] == "my custom sales prompt"
    # Delete override
    res = client.delete("/prompts/persona_sales/my-override", headers=USER_HEADER)
    assert res.status_code == 200
    # Verify deleted
    res = client.get("/prompts/persona_sales/my-override", headers=USER_HEADER)
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integration/test_prompts_api.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement API routes**

```python
# api/app/api/routes/prompts.py
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from api.app.db.session import SessionLocal
from api.app.services.prompt_service import PromptService

router = APIRouter()


def _get_user(request: Request) -> str:
    return request.headers.get("X-User-Email", "unknown@example.com")


def _svc() -> tuple[PromptService, SessionLocal]:
    db = SessionLocal()
    return PromptService(db), db


class UpdatePromptBody(BaseModel):
    content: str
    note: str | None = None


class OverrideBody(BaseModel):
    content: str


@router.get("")
def list_prompts():
    svc, db = _svc()
    try:
        return svc.list_all()
    finally:
        db.close()


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str):
    svc, db = _svc()
    try:
        result = svc.get(prompt_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return result
    finally:
        db.close()


@router.put("/{prompt_id}")
def update_prompt(prompt_id: str, body: UpdatePromptBody, request: Request):
    svc, db = _svc()
    try:
        svc.save(prompt_id, body.content, edited_by=_get_user(request), note=body.note)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.post("/{prompt_id}/reset")
def reset_prompt(prompt_id: str, request: Request):
    svc, db = _svc()
    try:
        svc.reset(prompt_id, reset_by=_get_user(request))
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.get("/{prompt_id}/versions")
def list_versions(prompt_id: str):
    svc, db = _svc()
    try:
        return svc.get_versions(prompt_id)
    finally:
        db.close()


@router.get("/{prompt_id}/versions/{version}")
def get_version(prompt_id: str, version: int):
    svc, db = _svc()
    try:
        result = svc.get_version(prompt_id, version)
        if result is None:
            raise HTTPException(status_code=404, detail="Version not found")
        return result
    finally:
        db.close()


@router.post("/{prompt_id}/rollback/{version}")
def rollback_prompt(prompt_id: str, version: int, request: Request):
    svc, db = _svc()
    try:
        svc.rollback(prompt_id, version, rolled_back_by=_get_user(request))
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.get("/{prompt_id}/my-override")
def get_my_override(prompt_id: str, request: Request):
    svc, db = _svc()
    try:
        result = svc.get_user_override(prompt_id, _get_user(request))
        if result is None:
            raise HTTPException(status_code=404, detail="No override found")
        return result
    finally:
        db.close()


@router.put("/{prompt_id}/my-override")
def save_my_override(prompt_id: str, body: OverrideBody, request: Request):
    svc, db = _svc()
    try:
        svc.save_user_override(prompt_id, _get_user(request), body.content)
        return {"ok": True}
    finally:
        db.close()


@router.delete("/{prompt_id}/my-override")
def delete_my_override(prompt_id: str, request: Request):
    svc, db = _svc()
    try:
        svc.delete_user_override(prompt_id, _get_user(request))
        return {"ok": True}
    finally:
        db.close()
```

- [ ] **Step 4: Register router in `api/app/api/router.py`**

Add this line alongside the other router includes:

```python
from api.app.api.routes.prompts import router as prompts_router
api_router.include_router(prompts_router, prefix="/prompts", tags=["prompts"])
```

- [ ] **Step 5: Add seed call to `api/app/db/init_db.py`**

After `Base.metadata.create_all(bind=conn)`, add:

```python
from api.app.db.seed_prompts import seed_prompts
from api.app.db.session import SessionLocal

db = SessionLocal()
try:
    seed_prompts(db)
finally:
    db.close()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/integration/test_prompts_api.py -v
```

Expected: 9 PASSED

- [ ] **Step 7: Commit**

```bash
git add api/app/api/routes/prompts.py api/app/api/router.py api/app/db/init_db.py tests/integration/test_prompts_api.py
git commit -m "feat: add /prompts API routes with CRUD, versioning, rollback, and user overrides"
```

---

## Task 5: Refactor llm.py to Use PromptService

**Files:**
- Modify: `api/app/services/llm.py`
- Test: `tests/unit/test_llm_prompt_resolution.py`

- [ ] **Step 1: Write failing test for LLM prompt resolution**

```python
# tests/unit/test_llm_prompt_resolution.py
from api.app.services.prompt_service import PromptService
from api.app.prompts.templates import SECTION_SYSTEM_PROMPTS, SYSTEM_ORACLE


def test_section_system_prompt_mapping_has_fallbacks():
    """Verify the hardcoded mapping still exists as fallback."""
    assert "pre_call" in SECTION_SYSTEM_PROMPTS
    assert "post_call" in SECTION_SYSTEM_PROMPTS
    assert SECTION_SYSTEM_PROMPTS["pre_call"] != ""


def test_prompt_service_section_key_mapping():
    """Verify the section-to-prompt-id mapping covers all sections."""
    from api.app.services.prompt_service import SECTION_TO_PROMPT_ID
    for section in ["pre_call", "post_call", "follow_up", "tal", "se_poc_plan", "se_arch_fit", "se_competitor"]:
        assert section in SECTION_TO_PROMPT_ID, f"Missing mapping for section: {section}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_llm_prompt_resolution.py -v
```

Expected: FAIL — `ImportError: cannot import name 'SECTION_TO_PROMPT_ID'`

- [ ] **Step 3: Add SECTION_TO_PROMPT_ID to prompt_service.py**

Add to `api/app/services/prompt_service.py` at module level:

```python
SECTION_TO_PROMPT_ID: dict[str, str] = {
    "pre_call": "system_pre_call_intel",
    "tal": "system_pre_call_intel",
    "post_call": "system_post_call_analysis",
    "follow_up": "system_post_call_analysis",
    "se_poc_plan": "system_se_analysis",
    "se_arch_fit": "system_se_analysis",
    "se_competitor": "system_se_analysis",
}
```

- [ ] **Step 4: Add `resolve_for_section` method to PromptService**

```python
def resolve_for_section(
    self,
    section: str,
    *,
    user_email: str | None = None,
    tidb_expert_enabled: bool = False,
) -> str:
    """Resolve the system prompt for a given section, with optional TiDB Expert injection."""
    prompt_id = SECTION_TO_PROMPT_ID.get(section)
    if prompt_id is None:
        # Fall back to oracle
        prompt_id = "system_oracle"

    content = self.resolve(prompt_id, user_email=user_email)
    if content is None:
        # Fall back to hardcoded
        from api.app.prompts.templates import SECTION_SYSTEM_PROMPTS, SYSTEM_ORACLE
        content = SECTION_SYSTEM_PROMPTS.get(section, SYSTEM_ORACLE)

    if tidb_expert_enabled:
        expert = self.resolve("tidb_expert")
        if expert is None:
            from api.app.prompts.templates import TIDB_EXPERT_CONTEXT
            expert = TIDB_EXPERT_CONTEXT
        content = content + "\n\n" + expert

    return content
```

- [ ] **Step 5: Modify `LLMService.answer_oracle` in `llm.py` to use PromptService**

In `api/app/services/llm.py`, modify the `answer_oracle` method to accept an optional `prompt_service` parameter. When provided, use `prompt_service.resolve_for_section()` instead of the hardcoded `SECTION_SYSTEM_PROMPTS` dict:

```python
# In answer_oracle, replace:
base_prompt = SECTION_SYSTEM_PROMPTS.get(section or "", SYSTEM_ORACLE)

# With:
if prompt_service:
    base_prompt = prompt_service.resolve_for_section(
        section or "",
        user_email=user_email,
        tidb_expert_enabled=tidb_expert_enabled,
    )
else:
    base_prompt = SECTION_SYSTEM_PROMPTS.get(section or "", SYSTEM_ORACLE)
```

This is a non-breaking change — existing callers that don't pass `prompt_service` continue to use hardcoded defaults.

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_llm_prompt_resolution.py -v
python -m pytest tests/ -v --timeout=30
```

Expected: ALL PASSED (no regressions)

- [ ] **Step 7: Commit**

```bash
git add api/app/services/prompt_service.py api/app/services/llm.py tests/unit/test_llm_prompt_resolution.py
git commit -m "feat: refactor llm.py to resolve prompts via PromptService with hardcoded fallback"
```

---

## Task 6: UI Route Handlers (Next.js → Python API Bridge)

**Files:**
- Create: `ui/app/api/prompts/route.js`
- Create: `ui/app/api/prompts/[id]/route.js`
- Create: `ui/app/api/prompts/[id]/reset/route.js`
- Create: `ui/app/api/prompts/[id]/versions/route.js`
- Create: `ui/app/api/prompts/[id]/rollback/route.js`
- Create: `ui/app/api/prompts/[id]/my-override/route.js`

- [ ] **Step 1: Create list/GET route handler**

```javascript
// ui/app/api/prompts/route.js
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts`, {
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

- [ ] **Step 2: Create single prompt GET/PUT handler**

```javascript
// ui/app/api/prompts/[id]/route.js
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}`, {
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const body = await request.json();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': session?.email || '',
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

- [ ] **Step 3: Create reset, versions, rollback, my-override handlers**

Follow the same pattern as Step 2 for each route. Each file proxies to the Python API with the appropriate method and path.

```javascript
// ui/app/api/prompts/[id]/reset/route.js
import { getSession } from '@/lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/reset`, {
    method: 'POST',
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

```javascript
// ui/app/api/prompts/[id]/versions/route.js
import { getSession } from '@/lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/versions`, {
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

```javascript
// ui/app/api/prompts/[id]/rollback/route.js
import { getSession } from '@/lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const body = await request.json();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/rollback/${body.version}`, {
    method: 'POST',
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

```javascript
// ui/app/api/prompts/[id]/my-override/route.js
import { getSession } from '@/lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/my-override`, {
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const body = await request.json();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/my-override`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': session?.email || '',
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(request, { params }) {
  const { id } = await params;
  const session = await getSession();
  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/my-override`, {
    method: 'DELETE',
    headers: { 'X-User-Email': session?.email || '' },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

- [ ] **Step 4: Commit**

```bash
git add ui/app/api/prompts/
git commit -m "feat: add Next.js route handlers for prompt studio API bridge"
```

---

## Task 7: Prompt Studio UI — Main Component

**Files:**
- Create: `ui/components/PromptStudio.js`
- Modify: `ui/app/(app)/settings/page.js`

- [ ] **Step 1: Build PromptStudio component**

Create `ui/components/PromptStudio.js` — a client component with:

- **State:** `prompts` (list), `selectedPrompt` (full prompt object or null), `activeCategory` filter
- **On mount:** `fetch('/api/prompts')` to load prompt list
- **Left panel:** Category tabs (System Prompts, Templates, Personas, Source Profiles) + scrollable card list. Each card shows name, category badge, version/updated info. Click opens editor.
- **TiDB Expert card:** Displayed at top of System Prompts with a prominent on/off toggle
- **Right panel:** When a prompt is selected, render `<PromptEditor>` (Task 8)
- **Styles:** Match existing settings panel patterns from `globals.css` (`.panel`, `.panel-header`, `.panel-body`, `.btn`, `.input` classes)

Key structure:

```javascript
'use client';
import { useState, useEffect } from 'react';
import PromptEditor from './PromptEditor';

const CATEGORIES = [
  { key: 'system_prompt', label: 'System Prompts' },
  { key: 'template', label: 'Templates' },
  { key: 'persona', label: 'Personas' },
  { key: 'source_profile', label: 'Source Profiles' },
];

export default function PromptStudio() {
  const [prompts, setPrompts] = useState([]);
  const [activeCategory, setActiveCategory] = useState('system_prompt');
  const [selectedId, setSelectedId] = useState(null);
  const [selectedPrompt, setSelectedPrompt] = useState(null);

  useEffect(() => {
    fetch('/api/prompts').then(r => r.json()).then(setPrompts).catch(() => {});
  }, []);

  const loadPrompt = async (id) => {
    setSelectedId(id);
    const res = await fetch(`/api/prompts/${id}`);
    if (res.ok) setSelectedPrompt(await res.json());
  };

  const filtered = prompts.filter(p => p.category === activeCategory);

  if (selectedPrompt) {
    return (
      <PromptEditor
        prompt={selectedPrompt}
        onBack={() => { setSelectedPrompt(null); setSelectedId(null); }}
        onSaved={() => {
          // Refresh list
          fetch('/api/prompts').then(r => r.json()).then(setPrompts);
          loadPrompt(selectedId);
        }}
      />
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Prompt Studio</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        {/* Category tabs */}
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {CATEGORIES.map(c => (
            <button
              key={c.key}
              className={`btn ${activeCategory === c.key ? 'btn-primary' : ''}`}
              onClick={() => setActiveCategory(c.key)}
              style={{ fontSize: '0.75rem' }}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Prompt cards */}
        {filtered.map(p => (
          <div
            key={p.id}
            onClick={() => loadPrompt(p.id)}
            style={{
              padding: '0.6rem 0.75rem',
              border: '1px solid var(--border)',
              borderRadius: '5px',
              cursor: 'pointer',
              background: selectedId === p.id ? 'rgba(57,255,20,0.06)' : 'var(--bg)',
              transition: 'background 0.1s',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>{p.name}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>{p.description}</div>
            {p.updated_by && (
              <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>
                Last edited by {p.updated_by}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add Prompt Studio tab to Settings page**

In `ui/app/(app)/settings/page.js`, add:

```javascript
import PromptStudio from '../../../components/PromptStudio';
```

Add a new section/tab for "Prompt Studio" that renders `<PromptStudio />`. Follow the existing tab pattern used in the settings page.

- [ ] **Step 3: Verify in browser**

Open `http://localhost:3000/settings`, click "Prompt Studio" tab. Verify:
- 4 category tabs render
- Prompt cards load from API (or show empty if API not connected)
- Clicking a card loads the editor (placeholder for now)

- [ ] **Step 4: Commit**

```bash
git add ui/components/PromptStudio.js ui/app/\(app\)/settings/page.js
git commit -m "feat: add Prompt Studio tab to Settings with category browser"
```

---

## Task 8: Prompt Editor with Variable Sidebar

**Files:**
- Create: `ui/components/PromptEditor.js`

- [ ] **Step 1: Build PromptEditor component**

```javascript
'use client';
import { useState } from 'react';
import PromptVersionHistory from './PromptVersionHistory';

export default function PromptEditor({ prompt, onBack, onSaved }) {
  const [content, setContent] = useState(prompt.current_content);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [status, setStatus] = useState('');

  const variables = JSON.parse(prompt.variables || '[]');
  const isPersona = prompt.category === 'persona';
  const hasChanges = content !== prompt.current_content;

  const save = async () => {
    setSaving(true);
    const res = await fetch(`/api/prompts/${prompt.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, note: note || undefined }),
    });
    setSaving(false);
    if (res.ok) { setStatus('Saved'); setNote(''); onSaved(); }
    else setStatus('Save failed');
    setTimeout(() => setStatus(''), 3000);
  };

  const saveMyVersion = async () => {
    setSaving(true);
    const res = await fetch(`/api/prompts/${prompt.id}/my-override`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    setSaving(false);
    setStatus(res.ok ? 'Personal version saved' : 'Save failed');
    setTimeout(() => setStatus(''), 3000);
  };

  const reset = async () => {
    if (!confirm('Reset to factory default? This creates a new version.')) return;
    const res = await fetch(`/api/prompts/${prompt.id}/reset`, { method: 'POST' });
    if (res.ok) { onSaved(); setStatus('Reset to default'); }
    setTimeout(() => setStatus(''), 3000);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-ghost" onClick={onBack} style={{ fontSize: '0.72rem' }}>&larr; Back</button>
          <span className="panel-title">{prompt.name}</span>
          <span className="tag">{prompt.category.replace('_', ' ')}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          {status && <span style={{ fontSize: '0.72rem', color: 'var(--accent)' }}>{status}</span>}
          <button className="btn" onClick={() => setShowHistory(!showHistory)} style={{ fontSize: '0.72rem' }}>
            {showHistory ? 'Hide History' : 'History'}
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{prompt.description}</div>

        {/* Variable sidebar */}
        {variables.length > 0 && (
          <div style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: '5px',
            padding: '0.5rem 0.75rem',
          }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-3)', marginBottom: '0.3rem' }}>
              AVAILABLE VARIABLES
            </div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {variables.map(v => (
                <code key={v} style={{
                  fontSize: '0.72rem',
                  background: 'rgba(57,255,20,0.08)',
                  color: 'var(--accent)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '3px',
                  cursor: 'pointer',
                }} onClick={() => navigator.clipboard.writeText(v)}>
                  {v}
                </code>
              ))}
            </div>
          </div>
        )}

        {/* Editor textarea */}
        <textarea
          className="input"
          value={content}
          onChange={e => setContent(e.target.value)}
          style={{
            minHeight: '400px',
            maxHeight: '700px',
            resize: 'vertical',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: '0.78rem',
            lineHeight: '1.6',
          }}
        />

        {/* Commit note */}
        <input
          className="input"
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Version note (optional) — e.g. 'improved MEDDPICC scoring'"
          style={{ fontSize: '0.78rem' }}
        />

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={save} disabled={saving || !hasChanges}>
            {saving ? 'Saving…' : 'Save New Version'}
          </button>
          {isPersona && (
            <button className="btn" onClick={saveMyVersion} disabled={saving}>
              Save as My Version
            </button>
          )}
          <button className="btn" onClick={reset} disabled={saving}>
            Reset to Default
          </button>
        </div>

        {/* Version history drawer */}
        {showHistory && (
          <PromptVersionHistory
            promptId={prompt.id}
            onRollback={() => { onSaved(); setShowHistory(false); }}
            onSelectVersion={(v) => setContent(v.content)}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/components/PromptEditor.js
git commit -m "feat: add PromptEditor with variable sidebar, version notes, and persona overrides"
```

---

## Task 9: Version History Drawer with Diffs and Rollback

**Files:**
- Create: `ui/components/PromptVersionHistory.js`

- [ ] **Step 1: Build PromptVersionHistory component**

```javascript
'use client';
import { useState, useEffect } from 'react';

export default function PromptVersionHistory({ promptId, onRollback, onSelectVersion }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [diffA, setDiffA] = useState(null); // version object for left side
  const [diffB, setDiffB] = useState(null); // version object for right side

  useEffect(() => {
    setLoading(true);
    fetch(`/api/prompts/${promptId}/versions`)
      .then(r => r.json())
      .then(data => { setVersions(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [promptId]);

  const rollback = async (version) => {
    if (!confirm(`Rollback to version ${version}? This creates a new version with the old content.`)) return;
    const res = await fetch(`/api/prompts/${promptId}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version }),
    });
    if (res.ok) onRollback();
  };

  // Simple line-by-line diff (no external library)
  const computeDiff = (textA, textB) => {
    const linesA = (textA || '').split('\n');
    const linesB = (textB || '').split('\n');
    const maxLen = Math.max(linesA.length, linesB.length);
    const result = [];
    for (let i = 0; i < maxLen; i++) {
      const a = linesA[i] ?? '';
      const b = linesB[i] ?? '';
      if (a === b) result.push({ type: 'same', text: a });
      else {
        if (a) result.push({ type: 'removed', text: a });
        if (b) result.push({ type: 'added', text: b });
      }
    }
    return result;
  };

  if (loading) return <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>Loading history…</div>;
  if (versions.length === 0) return <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No version history yet.</div>;

  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-2)', marginBottom: '0.5rem' }}>
        Version History ({versions.length})
      </div>

      {/* Version list */}
      <div style={{ display: 'grid', gap: '0.3rem', marginBottom: '0.75rem' }}>
        {versions.map(v => (
          <div key={v.version} style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.4rem 0.6rem', border: '1px solid var(--border)',
            borderRadius: '4px', fontSize: '0.75rem',
            background: (diffA?.version === v.version || diffB?.version === v.version)
              ? 'rgba(57,255,20,0.06)' : 'var(--bg)',
          }}>
            <span style={{ fontWeight: 600, color: 'var(--accent)', minWidth: '30px' }}>v{v.version}</span>
            <span style={{ color: 'var(--text-2)', flex: 1 }}>
              {v.edited_by?.split('@')[0]} — {v.note || 'no note'}
            </span>
            <span style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>
              {v.edited_at ? new Date(v.edited_at).toLocaleString() : ''}
            </span>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => onSelectVersion(v)}>Load</button>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => rollback(v.version)}>Rollback</button>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => diffA ? setDiffB(v) : setDiffA(v)}>
              {!diffA ? 'Diff A' : !diffB ? 'Diff B' : 'Diff A'}
            </button>
          </div>
        ))}
      </div>

      {/* Diff view */}
      {diffA && diffB && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)' }}>
              Comparing v{diffA.version} → v{diffB.version}
            </span>
            <button className="btn" style={{ fontSize: '0.68rem' }}
              onClick={() => { setDiffA(null); setDiffB(null); }}>Clear Diff</button>
          </div>
          <pre style={{
            fontSize: '0.72rem', lineHeight: 1.5, maxHeight: '300px',
            overflow: 'auto', background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: '5px', padding: '0.5rem',
          }}>
            {computeDiff(diffA.content, diffB.content).map((line, i) => (
              <div key={i} style={{
                color: line.type === 'added' ? '#39ff14' : line.type === 'removed' ? '#f87171' : 'var(--text-2)',
                background: line.type === 'added' ? 'rgba(57,255,20,0.06)' :
                  line.type === 'removed' ? 'rgba(248,113,113,0.06)' : 'transparent',
              }}>
                {line.type === 'added' ? '+ ' : line.type === 'removed' ? '- ' : '  '}{line.text}
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to Settings → Prompt Studio → click a prompt → click "History". Verify:
- Version list loads
- Load, Rollback, Diff buttons work
- Diff view shows colored additions/removals

- [ ] **Step 3: Commit**

```bash
git add ui/components/PromptVersionHistory.js
git commit -m "feat: add version history drawer with line diffs and rollback"
```

---

## Task 10: Seed UI Templates from ChatWorkspace Defaults

**Files:**
- Modify: `api/app/prompts/templates.py` (update `ALL_DEFAULTS` template content)

- [ ] **Step 1: Copy HARDCODED_DEFAULTS content from ChatWorkspace.js into ALL_DEFAULTS**

The 7 `tpl_*` entries in `ALL_DEFAULTS` currently have `content: ""`. Fill each with the corresponding template from `ui/components/ChatWorkspace.js` `HARDCODED_DEFAULTS`:

- `tpl_pre_call` ← `HARDCODED_DEFAULTS.pre_call`
- `tpl_post_call` ← `HARDCODED_DEFAULTS.post_call`
- `tpl_follow_up` ← `HARDCODED_DEFAULTS.follow_up`
- `tpl_tal` ← `HARDCODED_DEFAULTS.tal`
- `tpl_se_poc_plan` ← `HARDCODED_DEFAULTS.se_poc_plan`
- `tpl_se_arch_fit` ← `HARDCODED_DEFAULTS.se_arch_fit`
- `tpl_se_competitor` ← `HARDCODED_DEFAULTS.se_competitor`

Copy the full text of each template into the Python `ALL_DEFAULTS` dict as a triple-quoted string.

- [ ] **Step 2: Run seed tests to verify**

```bash
python -m pytest tests/unit/test_seed_prompts.py -v
```

Expected: PASS — all templates now have non-empty content

- [ ] **Step 3: Commit**

```bash
git add api/app/prompts/templates.py
git commit -m "feat: populate ALL_DEFAULTS with section template content from ChatWorkspace"
```

---

## Task 11: TiDB Expert Skill — Full Knowledge Base

**Files:**
- Modify: `api/app/prompts/templates.py` (expand `TIDB_EXPERT_CONTEXT`)

- [ ] **Step 1: Replace TIDB_EXPERT_CONTEXT with comprehensive knowledge base**

Replace the existing ~25-line `TIDB_EXPERT_CONTEXT` in `templates.py` with the full 11-section knowledge base as specified in the design spec (Section 8). Cover:

1. Core Architecture (TiDB Server, TiKV, TiFlash, PD — with internals)
2. Deployment Modes (Serverless, Dedicated, Self-Hosted — with specifics)
3. MySQL Compatibility (syntax, drivers, ORMs, caveats)
4. HTAP Deep Dive (TiFlash arch, Raft Learner, MPP, query routing)
5. Transactions & Consistency (Percolator 2PC, locking modes, SI, stale reads)
6. Scaling Patterns (online add, region splitting, hot region handling)
7. Migration Playbooks (MySQL/Aurora, Vitess, Oracle, PostgreSQL, MongoDB)
8. Competitive Battlecards (vs CRDB, PlanetScale, Aurora, AlloyDB, Spanner, Yugabyte)
9. Pricing & Packaging (Serverless RU, Dedicated node, Self-Hosted subscription)
10. Real-World Patterns (fintech, ad-tech, SaaS, multi-tenant)
11. Objection Handling (6+ common objections with responses)

Use the existing TiDB documentation, competitive materials, and architectural knowledge. Each section should be detailed enough to stand alone as a reference — this is the full playbook, not a summary.

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
python -m pytest tests/ -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add api/app/prompts/templates.py
git commit -m "feat: expand TiDB Expert skill to full 11-section knowledge base"
```

---

## Task 12: Prompt Quality Overhaul — System Prompts

**Files:**
- Modify: `api/app/prompts/templates.py`

- [ ] **Step 1: Upgrade each system prompt per the spec**

Apply the upgrades specified in the design spec Section 9:

| Prompt | Key Upgrade |
|--------|-------------|
| `SYSTEM_ORACLE` | Add structured output expectations, citation requirements, confidence scoring |
| `SYSTEM_PRE_CALL_INTEL` | Move accuracy rules to top, add explicit DO NOT list |
| `SYSTEM_POST_CALL_ANALYSIS` | Add MEDDPICC 1-5 scoring rubric, require transcript quotes |
| `SYSTEM_SE_ANALYSIS` | Expand with POC success/fail patterns, migration risk scoring |
| `SYSTEM_CALL_COACH` | Add situation→behavior→impact framework, require timestamps |
| `SYSTEM_MARKET_RESEARCH` | Add ICP scoring, signal weighting, territory structure |
| `SYSTEM_REP_EXECUTION` | Add deal-stage awareness (discovery/negotiation/closing) |
| `SYSTEM_SE_EXECUTION` | Add technical maturity assessment, readiness scoring |
| `SYSTEM_MARKETING_EXECUTION` | Add funnel mapping, content-to-signal matching |

Each prompt should be production-grade: specific, evidence-based, with clear output format expectations.

- [ ] **Step 2: Upgrade personas**

In the `ALL_DEFAULTS` dict (or `PERSONA_DEFAULT_PROMPTS`):
- **Sales:** Add deal-stage awareness, MEDDPICC lens, next-action bias
- **SE:** Add technical rigor, migration risk framing, POC pattern library reference
- **Marketing:** Add funnel awareness, vertical narrative framing, measurable outcome bias

- [ ] **Step 3: Upgrade source profiles**

Add confidence scoring per source and recency weighting to `PRE_CALL_SOURCES`, `POST_CALL_SOURCES`, `POC_TECHNICAL_SOURCES`.

- [ ] **Step 4: Run tests to verify no regressions**

```bash
python -m pytest tests/ -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/prompts/
git commit -m "feat: production-grade prompt overhaul for all system prompts, personas, and source profiles"
```

---

## Task 13: Wire ChatWorkspace to Load Templates from API

**Files:**
- Modify: `ui/components/ChatWorkspace.js`

- [ ] **Step 1: Update ChatWorkspace to fetch section templates from API**

In `ChatWorkspace.js`, update the template loading logic to fetch from the Prompt Studio API instead of (or with fallback to) `HARDCODED_DEFAULTS`:

```javascript
// On mount, fetch templates from API
useEffect(() => {
  async function loadFromAPI() {
    try {
      const res = await fetch('/api/prompts');
      if (!res.ok) return;
      const allPrompts = await res.json();
      // Filter for templates and build a map: section_key -> content
      const tplMap = {};
      for (const p of allPrompts) {
        if (p.category === 'template') {
          // Fetch full content
          const full = await fetch(`/api/prompts/${p.id}`);
          if (full.ok) {
            const data = await full.json();
            // Map tpl_pre_call -> pre_call
            const sectionKey = p.id.replace('tpl_', '');
            tplMap[sectionKey] = data.current_content;
          }
        }
      }
      // Merge with HARDCODED_DEFAULTS (API takes precedence)
      // Store in state for getTemplate() to use
    } catch { /* fall back to hardcoded */ }
  }
  loadFromAPI();
}, []);
```

Update `getTemplate()` to check API-loaded templates first, then existing user templates, then `HARDCODED_DEFAULTS`.

- [ ] **Step 2: Verify in browser**

- Edit a template in Prompt Studio
- Switch to the Chat workspace
- Select the same section and click Populate
- Verify the edited template content appears

- [ ] **Step 3: Commit**

```bash
git add ui/components/ChatWorkspace.js
git commit -m "feat: wire ChatWorkspace to load section templates from Prompt Studio API"
```

---

## Task 14: Final Integration Test and Push

- [ ] **Step 1: Run all backend tests**

```bash
cd /Users/stephen/Documents/gtm-copilot-oss/.worktrees/intelligence-models-feedback-tidb
python -m pytest tests/ -v --timeout=60
```

Expected: ALL PASS

- [ ] **Step 2: Manual browser verification**

1. Open Settings → Prompt Studio
2. Verify all 24 prompts appear across 4 categories
3. Click a system prompt → verify editor loads with content + variables
4. Edit content → Save → verify version appears in history
5. Click "History" → Load an old version → verify content changes
6. Rollback → verify content reverts
7. Reset to Default → verify factory content restored
8. For a persona: click "Save as My Version" → verify personal override
9. Toggle TiDB Expert → verify skill is injected in chat context

- [ ] **Step 3: Push branch**

```bash
git push origin feature/intelligence-models-feedback-tidb
```

- [ ] **Step 4: Commit any final fixes**

If any issues found during manual testing, fix and commit with descriptive messages.
