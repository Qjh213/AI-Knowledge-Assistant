from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import knowledge_bases as knowledge_base_routes
from app.core.exceptions import (
    ChatServiceError,
    KnowledgeBaseNotFoundError,
)
from app.main import app
from app.schemas.rag import RagAnswerResponse, RagCitation


client = TestClient(app)


class SuccessfulRagService:
    def __init__(self) -> None:
        self.called = False

    def answer(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ) -> RagAnswerResponse:
        self.called = True

        return RagAnswerResponse(
            knowledge_base_id=knowledge_base_id,
            question=request.question,
            answer="Milvus 用于保存和检索向量 [1]。",
            citations=[
                RagCitation(
                    reference=1,
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    original_filename="milvus-guide.txt",
                    page_number=2,
                    content="Milvus 用于保存和检索向量。",
                    score=0.93,
                )
            ],
        )


class MissingKnowledgeBaseRagService:
    def answer(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ):
        raise KnowledgeBaseNotFoundError(knowledge_base_id)


class UnavailableRagService:
    def answer(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ):
        raise ChatServiceError("DeepSeek unavailable")


def override_rag_service(service) -> None:
    app.dependency_overrides[
        knowledge_base_routes.get_rag_service
    ] = lambda: service


def clear_rag_override() -> None:
    app.dependency_overrides.pop(
        knowledge_base_routes.get_rag_service,
        None,
    )


def test_rag_endpoint_success():
    knowledge_base_id = uuid4()
    service = SuccessfulRagService()
    override_rag_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/answer",
            json={
                "question": "  Milvus 有什么作用？  ",
                "retrieval_limit": 5,
                "min_score": 0.3,
            },
        )
    finally:
        clear_rag_override()

    assert response.status_code == 200
    assert service.called is True

    payload = response.json()
    assert payload["knowledge_base_id"] == str(knowledge_base_id)
    assert payload["question"] == "Milvus 有什么作用？"
    assert payload["answer"] == "Milvus 用于保存和检索向量 [1]。"
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["reference"] == 1
    assert (
        payload["citations"][0]["original_filename"]
        == "milvus-guide.txt"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},
        {"question": "test", "retrieval_limit": 0},
        {"question": "test", "retrieval_limit": 21},
        {"question": "test", "min_score": -1.1},
        {"question": "test", "min_score": 1.1},
    ],
)
def test_rag_endpoint_validation(payload):
    service = SuccessfulRagService()
    override_rag_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{uuid4()}/answer",
            json=payload,
        )
    finally:
        clear_rag_override()

    assert response.status_code == 422
    assert service.called is False


def test_rag_endpoint_missing_knowledge_base():
    knowledge_base_id = uuid4()
    override_rag_service(MissingKnowledgeBaseRagService())

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/answer",
            json={"question": "测试问题"},
        )
    finally:
        clear_rag_override()

    assert response.status_code == 404
    assert response.json()["code"] == "knowledge_base_not_found"


def test_rag_endpoint_chat_service_unavailable():
    knowledge_base_id = uuid4()
    override_rag_service(UnavailableRagService())

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/answer",
            json={"question": "测试问题"},
        )
    finally:
        clear_rag_override()

    assert response.status_code == 503
    assert response.json()["code"] == "chat_service_unavailable"
    assert "DeepSeek unavailable" in response.json()["detail"]
