from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import (
    DocumentProcessingError,
    MinerUServiceError,
)
from app.database.models import (
    DocumentParser,
    DocumentStatus,
)
from app.repositories.document import DocumentRepository
from app.services.document_parser import ParsedDocument
from app.services.document_storage import DocumentStorageService
from app.services.mineru import (
    MinerUTaskResult,
    MinerUUploadTask,
)
from app.services.mineru_processing import (
    MinerUDocumentProcessingService,
)


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0
        self.refreshed_objects: list[object] = []

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def refresh(self, value: object) -> None:
        self.refreshed_objects.append(value)


class FakeDocumentService:
    def __init__(self, document: SimpleNamespace) -> None:
        self.document = document
        self.calls: list[tuple[object, object]] = []

    def get(
        self,
        session: object,
        knowledge_base_id: object,
        document_id: object,
    ) -> SimpleNamespace:
        self.calls.append(
            (knowledge_base_id, document_id)
        )
        return self.document


class FakeMinerUClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requested_names: list[str] = []
        self.uploads: list[tuple[str, Path]] = []

    def request_upload_url(
        self,
        file_name: str,
    ) -> MinerUUploadTask:
        self.requested_names.append(file_name)

        if self.fail:
            raise MinerUServiceError(
                "remote API unavailable"
            )

        return MinerUUploadTask(
            batch_id="batch-123",
            upload_url="https://upload.example/signed",
        )

    def upload_file(
        self,
        upload_url: str,
        file_path: Path,
    ) -> None:
        self.uploads.append(
            (upload_url, file_path)
        )


class FakeMinerUStatusClient:
    def __init__(
        self,
        result: MinerUTaskResult,
    ) -> None:
        self.result = result
        self.calls: list[tuple[str, str | None]] = []

    def get_batch_result(
        self,
        batch_id: str,
        *,
        file_name: str | None = None,
    ) -> MinerUTaskResult:
        self.calls.append(
            (batch_id, file_name)
        )
        return self.result


class FakeMinerUFinalizationClient(
    FakeMinerUStatusClient
):
    def __init__(
        self,
        result: MinerUTaskResult,
        markdown: str,
    ) -> None:
        super().__init__(result)
        self.markdown = markdown
        self.downloaded_urls: list[str] = []

    def download_markdown(
        self,
        full_zip_url: str,
    ) -> str:
        self.downloaded_urls.append(full_zip_url)
        return self.markdown


class FakeVectorStore:
    def __init__(self) -> None:
        self.deleted_document_ids: list[object] = []

    def delete_document(
        self,
        document_id: object,
    ) -> None:
        self.deleted_document_ids.append(
            document_id
        )


class FakeProcessingService:
    def __init__(self) -> None:
        self.calls: list[
            tuple[object, ParsedDocument]
        ] = []
        self.vector_store = FakeVectorStore()

    def index_parsed_document(
        self,
        session: FakeSession,
        document: SimpleNamespace,
        parsed_document: ParsedDocument,
    ) -> SimpleNamespace:
        self.calls.append(
            (document, parsed_document)
        )

        document.status = DocumentStatus.COMPLETED
        document.chunk_count = 1
        document.processing_progress = 100

        session.commit()
        session.refresh(document)

        return document


def make_document() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        original_filename="lesson.pdf",
        file_path="stored-document.pdf",
        status=DocumentStatus.PENDING,
        parser=DocumentParser.LOCAL,
        external_task_id=None,
        processing_progress=0,
        chunk_count=0,
        error_message=None,
    )


def patch_repository_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def update_processing_state(
        session: object,
        document: SimpleNamespace,
        status: DocumentStatus,
        **values: object,
    ) -> SimpleNamespace:
        document.status = status

        for name, value in values.items():
            if value is not None:
                setattr(document, name, value)

        return document

    monkeypatch.setattr(
        DocumentRepository,
        "update_processing_state",
        update_processing_state,
    )


def test_submit_document_to_mineru(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document()
    stored_file = tmp_path / document.file_path
    stored_file.write_bytes(b"fake-pdf-content")

    session = FakeSession()
    mineru_client = FakeMinerUClient()

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=mineru_client,
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    result = service.submit(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result is document
    assert document.status == DocumentStatus.PROCESSING
    assert document.parser == DocumentParser.MINERU
    assert document.external_task_id == "batch-123"
    assert document.processing_progress == 0

    assert mineru_client.requested_names == [
        "lesson.pdf"
    ]
    assert mineru_client.uploads == [
        (
            "https://upload.example/signed",
            stored_file.resolve(),
        )
    ]
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_do_not_submit_existing_mineru_task(
    tmp_path: Path,
) -> None:
    document = make_document()
    document.status = DocumentStatus.PROCESSING
    document.parser = DocumentParser.MINERU
    document.external_task_id = "existing-batch"

    session = FakeSession()
    mineru_client = FakeMinerUClient()

    service = MinerUDocumentProcessingService(
        mineru_client=mineru_client,
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    result = service.submit(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result is document
    assert mineru_client.requested_names == []
    assert mineru_client.uploads == []
    assert session.commit_count == 0


def test_mark_document_failed_when_submission_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document()
    stored_file = tmp_path / document.file_path
    stored_file.write_bytes(b"fake-pdf-content")

    session = FakeSession()
    mineru_client = FakeMinerUClient(fail=True)

    patch_repository_updates(monkeypatch)

    monkeypatch.setattr(
        DocumentRepository,
        "get",
        lambda session, document_id: document,
    )

    service = MinerUDocumentProcessingService(
        mineru_client=mineru_client,
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    with pytest.raises(
        DocumentProcessingError,
        match="remote API unavailable",
    ):
        service.submit(
            session,
            document.knowledge_base_id,
            document.id,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.parser == DocumentParser.MINERU
    assert document.processing_progress == 0
    assert "remote API unavailable" in document.error_message
    assert session.rollback_count == 1
    assert session.commit_count == 1


def make_submitted_document() -> SimpleNamespace:
    document = make_document()
    document.status = DocumentStatus.PROCESSING
    document.parser = DocumentParser.MINERU
    document.external_task_id = "batch-123"
    return document


def test_check_running_mineru_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_submitted_document()
    session = FakeSession()

    task_result = MinerUTaskResult(
        batch_id="batch-123",
        file_name="lesson.pdf",
        state="running",
        progress=40,
    )
    mineru_client = FakeMinerUStatusClient(
        task_result
    )

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=mineru_client,
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    result = service.check_status(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result is task_result
    assert document.status == DocumentStatus.PROCESSING
    assert document.processing_progress == 40
    assert document.error_message is None
    assert mineru_client.calls == [
        ("batch-123", "lesson.pdf")
    ]
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_check_completed_mineru_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_submitted_document()
    session = FakeSession()

    task_result = MinerUTaskResult(
        batch_id="batch-123",
        file_name="lesson.pdf",
        state="done",
        progress=100,
        full_zip_url=(
            "https://download.example/result.zip"
        ),
    )

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=FakeMinerUStatusClient(
            task_result
        ),
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    result = service.check_status(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result.state == "done"
    assert result.progress == 100

    # MinerU 解析完成，但文本尚未切分和写入向量库，
    # 因此这里仍然保持 processing。
    assert document.status == DocumentStatus.PROCESSING
    assert document.processing_progress == 100
    assert session.commit_count == 1


def test_check_failed_mineru_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_submitted_document()
    session = FakeSession()

    task_result = MinerUTaskResult(
        batch_id="batch-123",
        file_name="lesson.pdf",
        state="failed",
        progress=0,
        error_message="unsupported document",
    )

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=FakeMinerUStatusClient(
            task_result
        ),
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
    )

    result = service.check_status(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result.state == "failed"
    assert document.status == DocumentStatus.FAILED
    assert document.processing_progress == 0
    assert document.error_message == "unsupported document"
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_finalize_completed_mineru_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_submitted_document()
    session = FakeSession()

    task_result = MinerUTaskResult(
        batch_id="batch-123",
        file_name="lesson.pdf",
        state="done",
        progress=100,
        full_zip_url=(
            "https://download.example/result.zip"
        ),
    )
    mineru_client = FakeMinerUFinalizationClient(
        task_result,
        "# MinerU 标题\n\n这是解析后的正文。",
    )
    processing_service = FakeProcessingService()

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=mineru_client,
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
        processing_service=processing_service,
    )

    result = service.finalize(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result is document
    assert document.status == DocumentStatus.COMPLETED
    assert document.processing_progress == 100
    assert document.chunk_count == 1

    assert mineru_client.downloaded_urls == [
        "https://download.example/result.zip"
    ]

    assert len(processing_service.calls) == 1
    indexed_document, parsed_document = (
        processing_service.calls[0]
    )

    assert indexed_document is document
    assert parsed_document.character_count == len(
        "# MinerU 标题\n\n这是解析后的正文。"
    )
    assert len(parsed_document.sections) == 1

    section = parsed_document.sections[0]

    assert section.text == (
        "# MinerU 标题\n\n这是解析后的正文。"
    )
    assert section.page_number is None
    assert section.metadata == {
        "parser": "mineru",
        "source": "full.md",
        "batch_id": "batch-123",
        "original_filename": "lesson.pdf",
    }


def test_finalize_does_not_index_running_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_submitted_document()
    session = FakeSession()

    task_result = MinerUTaskResult(
        batch_id="batch-123",
        file_name="lesson.pdf",
        state="running",
        progress=60,
    )
    processing_service = FakeProcessingService()

    patch_repository_updates(monkeypatch)

    service = MinerUDocumentProcessingService(
        mineru_client=FakeMinerUStatusClient(
            task_result
        ),
        document_service=FakeDocumentService(document),
        storage_service=DocumentStorageService(
            storage_path=tmp_path
        ),
        processing_service=processing_service,
    )

    result = service.finalize(
        session,
        document.knowledge_base_id,
        document.id,
    )

    assert result is document
    assert document.status == DocumentStatus.PROCESSING
    assert document.processing_progress == 60
    assert processing_service.calls == []
