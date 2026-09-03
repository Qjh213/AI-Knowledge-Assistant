from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

pytestmark = pytest.mark.usefixtures('api_service_session')

from app.api.routes import documents as documents_route
from app.core.exceptions import (
    DocumentProcessingError,
    DocumentRetryNotAllowedError,
)
from app.database.models import DocumentParser, DocumentStatus
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


class FakeBackgroundProcessor:
    def __init__(self, *, reject_retry: bool = False) -> None:
        self.reject_retry = reject_retry
        self.calls: list[tuple[UUID, UUID, DocumentParser, bool]] = []

    def enqueue(
        self,
        session,
        knowledge_base_id: UUID,
        document_id: UUID,
        parser: DocumentParser | None,
        *,
        retry_only: bool = False,
    ):
        if self.reject_retry:
            raise DocumentRetryNotAllowedError(
                document_id,
                DocumentStatus.COMPLETED,
            )
        parser = parser or DocumentParser.LOCAL
        self.calls.append(
            (knowledge_base_id, document_id, parser, retry_only)
        )
        now = datetime.now(UTC)
        return SimpleNamespace(
            id=document_id,
            knowledge_base_id=knowledge_base_id,
            original_filename="test.txt",
            mime_type="text/plain",
            file_size=100,
            checksum="a" * 64,
            status=DocumentStatus.PROCESSING,
            error_message=None,
            chunk_count=0,
            parser=parser,
            external_task_id=None,
            processing_progress=0,
            processing_attempts=1,
            last_processing_started_at=now,
            last_processing_finished_at=None,
            created_at=now,
            updated_at=now,
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


def test_queue_document_processing_endpoint():
    knowledge_base_id = uuid4()
    document_id = uuid4()
    processor = FakeBackgroundProcessor()
    app.dependency_overrides[
        documents_route.get_background_document_processor
    ] = lambda: processor

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}/process/background",
            params={"parser": "mineru"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "processing"
    assert response.json()["processing_attempts"] == 1
    assert processor.calls == [
        (
            knowledge_base_id,
            document_id,
            DocumentParser.MINERU,
            False,
        )
    ]


def test_retry_rejects_non_failed_document():
    knowledge_base_id = uuid4()
    document_id = uuid4()
    processor = FakeBackgroundProcessor(reject_retry=True)
    app.dependency_overrides[
        documents_route.get_background_document_processor
    ] = lambda: processor

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}/process/retry",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["code"] == "document_retry_not_allowed"
