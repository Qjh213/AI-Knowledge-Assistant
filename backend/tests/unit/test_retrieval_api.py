from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import knowledge_bases as knowledge_base_routes
from app.core.exceptions import (
    KnowledgeBaseNotFoundError,
    RetrievalServiceError,
)
from app.main import app
from app.schemas.retrieval import (
    RetrievalResponse,
    RetrievalResult,
)


client = TestClient(app)


class SuccessfulRetrievalService:
    def __init__(self) -> None:
        self.called = False

    def search(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ) -> RetrievalResponse:
        self.called = True

        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=0,
            content="向量数据库用于存储和检索向量。",
            page_number=1,
            token_count=12,
            metadata={"source": "guide.txt"},
            score=0.93,
        )

        return RetrievalResponse(
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            results=[result],
            total=1,
        )


class MissingKnowledgeBaseRetrievalService:
    def search(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ):
        raise KnowledgeBaseNotFoundError(
            knowledge_base_id
        )


class UnavailableRetrievalService:
    def search(
        self,
        session,
        knowledge_base_id: UUID,
        request,
    ):
        raise RetrievalServiceError(
            "embedding provider unavailable"
        )


def override_retrieval_service(service):
    app.dependency_overrides[
        knowledge_base_routes.get_retrieval_service
    ] = lambda: service


def clear_retrieval_override():
    app.dependency_overrides.pop(
        knowledge_base_routes.get_retrieval_service,
        None,
    )


def test_retrieval_endpoint_success():
    knowledge_base_id = uuid4()
    service = SuccessfulRetrievalService()
    override_retrieval_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/search",
            json={
                "query": "  什么是向量数据库？  ",
                "limit": 5,
                "min_score": 0.5,
            },
        )
    finally:
        clear_retrieval_override()

    assert response.status_code == 200
    assert service.called is True

    payload = response.json()
    assert payload["knowledge_base_id"] == str(
        knowledge_base_id
    )
    assert payload["query"] == "什么是向量数据库？"
    assert payload["total"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["score"] == pytest.approx(
        0.93
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   "},
        {"query": "test", "limit": 0},
        {"query": "test", "limit": 21},
        {"query": "test", "min_score": -1.1},
        {"query": "test", "min_score": 1.1},
    ],
)
def test_retrieval_endpoint_validation(payload):
    service = SuccessfulRetrievalService()
    override_retrieval_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{uuid4()}/search",
            json=payload,
        )
    finally:
        clear_retrieval_override()

    assert response.status_code == 422
    assert service.called is False


def test_retrieval_endpoint_missing_knowledge_base():
    knowledge_base_id = uuid4()
    override_retrieval_service(
        MissingKnowledgeBaseRetrievalService()
    )

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/search",
            json={"query": "测试问题"},
        )
    finally:
        clear_retrieval_override()

    assert response.status_code == 404
    assert response.json()["code"] == (
        "knowledge_base_not_found"
    )


def test_retrieval_endpoint_service_unavailable():
    knowledge_base_id = uuid4()

    override_retrieval_service(
        UnavailableRetrievalService()
    )

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/search",
            json={"query": "测试问题"},
        )
    finally:
        clear_retrieval_override()

    assert response.status_code == 503
    assert response.json()["code"] == (
        "retrieval_service_unavailable"
    )
    assert "embedding provider unavailable" in (
        response.json()["detail"]
    )