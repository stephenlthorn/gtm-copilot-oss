import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride
from app.services.prompt_service import PromptService, clear_cache


@pytest.fixture(autouse=True)
def reset_prompt_cache():
    clear_cache()
    yield
    clear_cache()


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
