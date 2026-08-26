from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["application"] == "AI Knowledge Assistant"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "development"
    assert "timestamp" in payload