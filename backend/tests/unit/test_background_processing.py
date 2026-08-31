from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import DocumentRetryNotAllowedError
from app.database.models import DocumentParser, DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.background_processing import BackgroundDocumentProcessor


class FakeExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, function, *args):
        self.submissions.append((function, args))


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, document: object) -> None:
        return None


class FakeDocumentService:
    def __init__(self, document: SimpleNamespace) -> None:
        self.document = document

    def get(self, session, knowledge_base_id, document_id):
        return self.document


def make_document(status: DocumentStatus) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        status=status,
        parser=DocumentParser.LOCAL,
        external_task_id=None,
        error_message="previous failure" if status == DocumentStatus.FAILED else None,
        processing_progress=0,
        processing_attempts=0,
        last_processing_started_at=None,
        last_processing_finished_at=None,
    )


def create_processor(
    document: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[BackgroundDocumentProcessor, FakeExecutor]:
    processor = BackgroundDocumentProcessor(max_workers=1)
    executor = FakeExecutor()
    processor._executor.shutdown(wait=False)
    processor._executor = executor
    processor._document_service = FakeDocumentService(document)

    def mark_started(session, target, parser):
        target.status = DocumentStatus.PROCESSING
        target.parser = parser
        target.error_message = None
        target.processing_attempts += 1
        return target

    monkeypatch.setattr(
        DocumentRepository,
        "mark_processing_started",
        mark_started,
    )
    return processor, executor


def test_enqueue_marks_and_submits_background_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document(DocumentStatus.PENDING)
    processor, executor = create_processor(document, monkeypatch)
    session = FakeSession()

    result = processor.enqueue(
        session,
        document.knowledge_base_id,
        document.id,
        DocumentParser.LOCAL,
    )

    assert result.status == DocumentStatus.PROCESSING
    assert result.processing_attempts == 1
    assert session.commits == 1
    assert len(executor.submissions) == 1


def test_duplicate_enqueue_does_not_submit_second_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document(DocumentStatus.PENDING)
    processor, executor = create_processor(document, monkeypatch)
    session = FakeSession()

    processor.enqueue(
        session,
        document.knowledge_base_id,
        document.id,
        DocumentParser.LOCAL,
    )
    processor.enqueue(
        session,
        document.knowledge_base_id,
        document.id,
        DocumentParser.LOCAL,
    )

    assert len(executor.submissions) == 1


def test_retry_requires_failed_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document(DocumentStatus.COMPLETED)
    processor, executor = create_processor(document, monkeypatch)

    with pytest.raises(DocumentRetryNotAllowedError):
        processor.enqueue(
            FakeSession(),
            document.knowledge_base_id,
            document.id,
            DocumentParser.LOCAL,
            retry_only=True,
        )

    assert executor.submissions == []


def test_retry_uses_selected_parser_and_clears_mineru_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = make_document(DocumentStatus.FAILED)
    document.external_task_id = "stale-task"
    processor, executor = create_processor(document, monkeypatch)

    processor.enqueue(
        FakeSession(),
        document.knowledge_base_id,
        document.id,
        DocumentParser.MINERU,
        retry_only=True,
    )

    assert document.parser == DocumentParser.MINERU
    assert document.external_task_id is None
    assert document.processing_attempts == 1
    assert len(executor.submissions) == 1
