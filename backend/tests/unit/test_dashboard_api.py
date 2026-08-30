from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.main import app


client = TestClient(app)


class FakeSession:
    def __init__(self) -> None:
        self.values = iter([2, 7, 4])

    def scalar(self, statement):
        return next(self.values)


def test_get_dashboard_overview_endpoint() -> None:
    def override_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = override_db

    try:
        response = client.get("/api/v1/dashboard/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "knowledge_base_count": 2,
        "processed_document_count": 7,
        "conversation_count": 4,
    }
