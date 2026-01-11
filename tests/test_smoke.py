from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_root_when_db_host_exists(monkeypatch):
    monkeypatch.setattr(settings, "DB_HOST", "localhost")

    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == "success: localhost"

def test_root_when_db_host_missing(monkeypatch):
    monkeypatch.setattr(settings, "DB_HOST", "")

    resp = client.get("/")
    assert resp.status_code == 200

    assert resp.json() == ["false"]