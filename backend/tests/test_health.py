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


def test_readiness_check_when_services_are_healthy(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_postgres",
        lambda: (True, "connected"),
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_milvus",
        lambda: (True, "connected"),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["services"]["postgres"]["status"] == "healthy"
    assert payload["services"]["milvus"]["status"] == "healthy"


def test_readiness_check_when_postgres_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_postgres",
        lambda: (False, "connection failed"),
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_milvus",
        lambda: (True, "connected"),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503

    payload = response.json()

    assert payload["status"] == "not_ready"
    assert payload["services"]["postgres"] == {
        "status": "unhealthy",
        "detail": "connection failed",
    }
    assert payload["services"]["milvus"]["status"] == "healthy"