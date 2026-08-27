from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes import documents as documents_route
from app.core.exceptions import DocumentProcessingError
from app.database.models import DocumentStatus
from app.main import app


client = TestClient(app)


class SuccessfulProcessingService:
    def process(
        self,
        session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ):
        now = datetime.now(UTC)

        return SimpleNamespace(
            id=document_id,
            knowledge_base_id=knowledge_base_id,
            original_filename="test.txt",
            mime_type="text/plain",
            file_size=100,
            checksum="a" * 64,
            status=DocumentStatus.COMPLETED,
            error_message=None,
            chunk_count=2,
            created_at=now,
            updated_at=now,
        )


class FailingProcessingService:
    def process(
        self,
        session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ):
        raise DocumentProcessingError(
            document_id,
            "embedding provider unavailable",
        )


def test_process_document_endpoint_success():
    knowledge_base_id = uuid4()
    document_id = uuid4()

    app.dependency_overrides[
        documents_route.get_document_processing_service
    ] = lambda: SuccessfulProcessingService()

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}/process"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == str(document_id)
    assert payload["knowledge_base_id"] == str(
        knowledge_base_id
    )
    assert payload["status"] == "completed"
    assert payload["chunk_count"] == 2
    assert payload["error_message"] is None


def test_process_document_endpoint_failure():
    knowledge_base_id = uuid4()
    document_id = uuid4()

    app.dependency_overrides[
        documents_route.get_document_processing_service
    ] = lambda: FailingProcessingService()

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}/process"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["code"] == (
        "document_processing_failed"
    )
    assert "embedding provider unavailable" in (
        response.json()["detail"]
    )