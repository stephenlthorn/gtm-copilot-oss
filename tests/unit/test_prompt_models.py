import pytest
import sqlalchemy.exc
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride


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
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.commit()
