from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as documents_route
from app.main import app
from app.services.document_storage import DocumentStorageService


client = TestClient(app)


@pytest.mark.integration
def test_document_api_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_service = DocumentStorageService(
        storage_path=tmp_path,
        max_size_bytes=1024,
        allowed_extensions=(".txt", ".md", ".pdf", ".docx"),
    )
    monkeypatch.setattr(
        documents_route.document_service,
        "storage_service",
        storage_service,
    )

    unique_value = uuid4().hex
    knowledge_base_id: str | None = None
    document_id: str | None = None

    try:
        knowledge_base_response = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": f"document-api-test-{unique_value}",
                "description": "Temporary document API test",
            },
        )

        assert knowledge_base_response.status_code == 201
        knowledge_base_id = knowledge_base_response.json()["id"]

        content = b"AI knowledge assistant document content."

        upload_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "guide.txt",
                    content,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        uploaded = upload_response.json()
        document_id = uploaded["id"]

        assert uploaded["knowledge_base_id"] == knowledge_base_id
        assert uploaded["original_filename"] == "guide.txt"
        assert uploaded["mime_type"] == "text/plain"
        assert uploaded["file_size"] == len(content)
        assert uploaded["status"] == "pending"
        assert uploaded["chunk_count"] == 0
        assert len(list(tmp_path.iterdir())) == 1

        get_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}"
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == document_id

        list_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents"
        )

        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert list_response.json()["items"][0]["id"] == document_id

        duplicate_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "renamed.txt",
                    content,
                    "text/plain",
                )
            },
        )

        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["code"] == (
            "document_already_exists"
        )
        assert len(list(tmp_path.iterdir())) == 1

        unsupported_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "program.exe",
                    b"not allowed",
                    "application/octet-stream",
                )
            },
        )

        assert unsupported_response.status_code == 415
        assert unsupported_response.json()["code"] == (
            "unsupported_document_type"
        )

        empty_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "empty.txt",
                    b"",
                    "text/plain",
                )
            },
        )

        assert empty_response.status_code == 400
        assert empty_response.json()["code"] == "empty_document"

        oversized_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "large.txt",
                    b"x" * 1025,
                    "text/plain",
                )
            },
        )

        assert oversized_response.status_code == 413
        assert oversized_response.json()["code"] == (
            "document_too_large"
        )

        delete_response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{document_id}"
        )

        assert delete_response.status_code == 204
        document_id = None
        assert not any(tmp_path.iterdir())

        missing_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
            f"/documents/{uploaded['id']}"
        )

        assert missing_response.status_code == 404
        assert missing_response.json()["code"] == (
            "document_not_found"
        )

    finally:
        if document_id is not None and knowledge_base_id is not None:
            client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}"
                f"/documents/{document_id}"
            )

        if knowledge_base_id is not None:
            client.delete(
                f"/api/v1/knowledge-bases/{knowledge_base_id}"
            )