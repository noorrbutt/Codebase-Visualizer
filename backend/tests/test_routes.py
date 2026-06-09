from fastapi.testclient import TestClient

from app.database import create_tables
from app.main import app

create_tables()
client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_analyze_invalid_url():
    response = client.post("/repos/analyze", json={"github_url": "https://notgithub.com/a/b"})
    assert response.status_code == 400


def test_analyze_missing_url():
    response = client.post("/repos/analyze", json={})
    assert response.status_code == 422


def test_get_repo_not_found():
    response = client.get("/repos/99999")
    assert response.status_code == 404
