from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

pytestmark = pytest.mark.usefixtures('api_service_session')

from app.api.routes import documents as document_routes
from app.database.models import (
    DocumentParser,
    DocumentStatus,
)
from app.main import app


client = TestClient(app)


def make_document() -> SimpleNamespace:
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        original_filename="lesson.pdf",
        mime_type="application/pdf",
        file_size=1024,
        checksum="a" * 64,
        status=DocumentStatus.PENDING,
        error_message=None,
        chunk_count=0,
        parser=DocumentParser.LOCAL,
        external_task_id=None,
        processing_progress=0,
        created_at=now,
        updated_at=now,
    )


class FakeMinerUProcessingService:
    def __init__(
        self,
        document: SimpleNamespace,
    ) -> None:
        self.document = document
        self.submit_calls: list[
            tuple[UUID, UUID]
        ] = []
        self.finalize_calls: list[
            tuple[UUID, UUID]
        ] = []

    def submit(
        self,
        session: object,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> SimpleNamespace:
        self.submit_calls.append(
            (knowledge_base_id, document_id)
        )

        self.document.status = (
            DocumentStatus.PROCESSING
        )
        self.document.parser = DocumentParser.MINERU
        self.document.external_task_id = "batch-123"
        self.document.processing_progress = 0

        return self.document

    def finalize(
        self,
        session: object,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> SimpleNamespace:
        self.finalize_calls.append(
            (knowledge_base_id, document_id)
        )

        self.document.status = (
            DocumentStatus.COMPLETED
        )
        self.document.parser = DocumentParser.MINERU
        self.document.external_task_id = "batch-123"
        self.document.processing_progress = 100
        self.document.chunk_count = 3

        return self.document


def override_mineru_service(
    service: FakeMinerUProcessingService,
) -> None:
    app.dependency_overrides[
        document_routes.get_mineru_processing_service
    ] = lambda: service


def clear_mineru_override() -> None:
    app.dependency_overrides.pop(
        document_routes.get_mineru_processing_service,
        None,
    )


def test_submit_document_to_mineru_api() -> None:
    document = make_document()
    service = FakeMinerUProcessingService(
        document
    )
    override_mineru_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/"
            f"{document.knowledge_base_id}/documents/"
            f"{document.id}/process/mineru"
        )
    finally:
        clear_mineru_override()

    assert response.status_code == 200
    assert service.submit_calls == [
        (
            document.knowledge_base_id,
            document.id,
        )
    ]

    payload = response.json()

    assert payload["id"] == str(document.id)
    assert payload["status"] == "processing"
    assert payload["parser"] == "mineru"
    assert payload["external_task_id"] == "batch-123"
    assert payload["processing_progress"] == 0


def test_refresh_and_finalize_mineru_api() -> None:
    document = make_document()
    document.status = DocumentStatus.PROCESSING
    document.parser = DocumentParser.MINERU
    document.external_task_id = "batch-123"

    service = FakeMinerUProcessingService(
        document
    )
    override_mineru_service(service)

    try:
        response = client.post(
            f"/api/v1/knowledge-bases/"
            f"{document.knowledge_base_id}/documents/"
            f"{document.id}/process/mineru/refresh"
        )
    finally:
        clear_mineru_override()

    assert response.status_code == 200
    assert service.finalize_calls == [
        (
            document.knowledge_base_id,
            document.id,
        )
    ]

    payload = response.json()

    assert payload["status"] == "completed"
    assert payload["parser"] == "mineru"
    assert payload["external_task_id"] == "batch-123"
    assert payload["processing_progress"] == 100
    assert payload["chunk_count"] == 3
