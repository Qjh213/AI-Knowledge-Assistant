from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_knowledge_base_crud_flow() -> None:
    unique_value = uuid4().hex
    name = f"api-test-{unique_value}"
    knowledge_base_id: str | None = None

    try:
        create_response = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"  {name}  ",
                "description": "Created by integration test",
            },
        )

        assert create_response.status_code == 201

        created = create_response.json()
        knowledge_base_id = created["id"]

        assert created["name"] == name
        assert created["description"] == "Created by integration test"

        get_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == knowledge_base_id

        list_response = client.get(
            "/api/v1/knowledge-bases",
            params={"offset": 0, "limit": 100},
        )

        assert list_response.status_code == 200

        listed = list_response.json()

        assert listed["total"] >= 1
        assert any(
            item["id"] == knowledge_base_id
            for item in listed["items"]
        )

        update_response = client.patch(
            f"/api/v1/knowledge-bases/{knowledge_base_id}",
            json={"description": "Updated description"},
        )

        assert update_response.status_code == 200
        assert (
            update_response.json()["description"]
            == "Updated description"
        )

        duplicate_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": name},
        )

        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["code"] == (
            "knowledge_base_already_exists"
        )

        delete_response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
        )

        assert delete_response.status_code == 204
        knowledge_base_id = None

        missing_response = client.get(
            f"/api/v1/knowledge-bases/{created['id']}"
        )

        assert missing_response.status_code == 404
        assert missing_response.json()["code"] == (
            "knowledge_base_not_found"
        )

    finally:
        if knowledge_base_id is not None:
            client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}"
            )


def test_knowledge_base_name_validation(api_service_session) -> None:
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "   "},
    )

    assert response.status_code == 422


def test_knowledge_base_pagination_validation(api_service_session) -> None:
    response = client.get(
        "/api/v1/knowledge-bases",
        params={"offset": -1, "limit": 101},
    )

    assert response.status_code == 422
