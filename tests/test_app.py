import importlib.util

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fastapi.routing import APIRoute
from app.config import get_settings
from app.main import create_app

DB_MODULE_READY = importlib.util.find_spec("app.db") is not None


class Body(BaseModel):
    n: int


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()

def validate(body: Body):
    return body

@pytest.fixture
def client(settings_env):
    app = create_app()
    # Insert the test route ahead of the static mount so it isn't shadowed.
    app.router.routes.insert(0, APIRoute("/_test/validate", validate, methods=["POST"]))
    return TestClient(app)


def test_docs_are_served(client):
    assert client.get("/docs").status_code == 200


def test_unknown_api_path_returns_json_error(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"] == "http_404"


def test_validation_error_has_standard_shape(client):
    r = client.post("/_test/validate", json={"n": "not a number"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert body["detail"][0]["loc"][-1] == "n"


@pytest.mark.skipif(not DB_MODULE_READY, reason="app/db.py not merged yet")
def test_startup_creates_database_file(settings_env):
    app = create_app()
    with TestClient(app):
        assert (settings_env / "test.db").exists()
        assert app.state.db is not None