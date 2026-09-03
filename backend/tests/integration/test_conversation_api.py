from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_conversation_crud_flow_and_knowledge_base_scope() -> None:
    unique_value = uuid4().hex
    first_knowledge_base_id: str | None = None
    second_knowledge_base_id: str | None = None
    conversation_id: str | None = None

    try:
        first_response = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"conversation-api-first-{unique_value}",
            },
        )
        assert first_response.status_code == 201
        first_knowledge_base_id = first_response.json()["id"]

        second_response = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"conversation-api-second-{unique_value}",
            },
        )
        assert second_response.status_code == 201
        second_knowledge_base_id = second_response.json()["id"]

        base_url = (
            f"/api/v1/knowledge-bases/"
            f"{first_knowledge_base_id}/conversations"
        )

        create_response = client.post(
            base_url,
            json={"title": "  Milvus 问答  "},
        )

        assert create_response.status_code == 201

        created = create_response.json()
        conversation_id = created["id"]

        assert created["knowledge_base_id"] == first_knowledge_base_id
        assert created["title"] == "Milvus 问答"

        get_response = client.get(
            f"{base_url}/{conversation_id}"
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == conversation_id

        list_response = client.get(
            base_url,
            params={"offset": 0, "limit": 20},
        )

        assert list_response.status_code == 200

        listed = list_response.json()

        assert listed["total"] == 1
        assert len(listed["items"]) == 1
        assert listed["items"][0]["id"] == conversation_id

        update_response = client.patch(
            f"{base_url}/{conversation_id}",
            json={"title": "  更新后的标题  "},
        )

        assert update_response.status_code == 200
        assert update_response.json()["title"] == "更新后的标题"

        cross_scope_response = client.get(
            f"/api/v1/knowledge-bases/"
            f"{second_knowledge_base_id}/conversations/"
            f"{conversation_id}"
        )

        assert cross_scope_response.status_code == 404
        assert cross_scope_response.json()["code"] == (
            "conversation_not_found"
        )

        delete_response = client.delete(
            f"{base_url}/{conversation_id}"
        )

        assert delete_response.status_code == 204
        conversation_id = None

        missing_response = client.get(
            f"{base_url}/{created['id']}"
        )

        assert missing_response.status_code == 404
        assert missing_response.json()["code"] == (
            "conversation_not_found"
        )

    finally:
        if (
            first_knowledge_base_id is not None
            and conversation_id is not None
        ):
            client.delete(
                f"/api/v1/knowledge-bases/"
                f"{first_knowledge_base_id}/conversations/"
                f"{conversation_id}"
            )

        if first_knowledge_base_id is not None:
            client.delete(
                f"/api/v1/knowledge-bases/"
                f"{first_knowledge_base_id}"
            )

        if second_knowledge_base_id is not None:
            client.delete(
                f"/api/v1/knowledge-bases/"
                f"{second_knowledge_base_id}"
            )


def test_conversation_title_validation(api_service_session) -> None:
    response = client.post(
        f"/api/v1/knowledge-bases/{uuid4()}/conversations",
        json={"title": "   "},
    )

    assert response.status_code == 422


def test_conversation_pagination_validation(api_service_session) -> None:
    response = client.get(
        f"/api/v1/knowledge-bases/{uuid4()}/conversations",
        params={"offset": -1, "limit": 101},
    )

    assert response.status_code == 422
