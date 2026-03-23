import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.entities import UserPreference


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_user_preference_intel_brief_fields_have_correct_defaults(db):
    pref = UserPreference(user_email="test@example.com")
    db.add(pref)
    db.commit()
    db.refresh(pref)
    assert pref.intel_brief_enabled is True
    assert pref.intel_brief_summarizer_model == "gpt-5.4-mini"
    assert pref.intel_brief_summarizer_effort is None
    assert pref.intel_brief_synthesis_model == "gpt-5.4"
    assert pref.intel_brief_synthesis_effort == "medium"
