import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.db.seed_prompts import seed_prompts
from app.services.prompt_service import clear_cache


@pytest.fixture(autouse=True)
def reset_and_seed():
    clear_cache()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_prompts(db)
    yield
    clear_cache()


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
