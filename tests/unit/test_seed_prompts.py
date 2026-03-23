import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.prompt_models import PromptRegistry
from app.db.seed_prompts import seed_prompts


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
