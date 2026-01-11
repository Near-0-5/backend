from fastapi.testclient import TestClient
from app.main import app


def test_root_returns_200():
    client = TestClient(app)
    res = client.get("/")

    assert res.status_code == 200