from types import SimpleNamespace
from uuid import uuid4
from threading import Lock
from unittest.mock import MagicMock

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

    def rollback(self) -> None:
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


@pytest.mark.parametrize("status", [DocumentStatus.FAILED, DocumentStatus.PROCESSING])
def test_resume_preserves_existing_mineru_task(monkeypatch, status):
    document = make_document(status)
    document.parser = DocumentParser.MINERU
    document.external_task_id = "completed-remote-task"
    processor, executor = create_processor(document, monkeypatch)
    processor.enqueue(FakeSession(), document.knowledge_base_id, document.id, None, retry_only=True)
    assert document.external_task_id == "completed-remote-task"
    assert document.processing_attempts == 1
    assert len(executor.submissions) == 1


def test_cannot_resume_an_active_worker(monkeypatch):
    document = make_document(DocumentStatus.PROCESSING)
    processor, executor = create_processor(document, monkeypatch)
    processor._inflight.add(document.id)
    with pytest.raises(DocumentRetryNotAllowedError):
        processor.enqueue(FakeSession(), document.knowledge_base_id, document.id, None, retry_only=True)
    assert not executor.submissions


def test_worker_exception_persists_failure_and_releases_slot(monkeypatch, caplog):
    document = make_document(DocumentStatus.PROCESSING)
    document.processing_attempts = 4
    document.parser = DocumentParser.MINERU
    document.external_task_id = "keep-task"
    processor = object.__new__(BackgroundDocumentProcessor)
    processor._lock = Lock()
    processor._inflight = {document.id}
    processor._run_mineru = MagicMock(side_effect=RuntimeError("https://secret.example/?token=TOP-SECRET"))
    session = MagicMock()
    session.scalar.return_value = document
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr("app.services.background_processing.SessionLocal", factory)
    processor._run(document.knowledge_base_id, document.id, DocumentParser.MINERU, 4)
    assert document.status == DocumentStatus.FAILED
    assert document.last_processing_finished_at is not None
    assert document.external_task_id == "keep-task"
    assert document.id not in processor._inflight
    assert "TOP-SECRET" not in caplog.text
    assert "TOP-SECRET" not in document.error_message
    assert "RuntimeError" in caplog.text
    session.commit.assert_called_once()


@pytest.mark.parametrize("status,attempt", [(DocumentStatus.COMPLETED, 4), (DocumentStatus.FAILED, 4), (DocumentStatus.PROCESSING, 5)])
def test_failure_does_not_overwrite_terminal_or_new_attempt(monkeypatch, status, attempt):
    document = make_document(status)
    document.processing_attempts = attempt
    session = MagicMock()
    session.scalar.return_value = document
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr("app.services.background_processing.SessionLocal", factory)
    BackgroundDocumentProcessor._record_failure(document.id, 4, RuntimeError(), stage="worker")
    assert document.status == status
    session.commit.assert_not_called()


def test_queue_submission_failure_is_recorded(monkeypatch):
    document = make_document(DocumentStatus.PENDING)
    processor, executor = create_processor(document, monkeypatch)
    executor.submit = MagicMock(side_effect=RuntimeError("executor stopped"))
    processor._record_failure = MagicMock()
    with pytest.raises(RuntimeError):
        processor.enqueue(FakeSession(), document.knowledge_base_id, document.id, None)
    processor._record_failure.assert_called_once()
    assert document.id not in processor._inflight


@pytest.mark.parametrize("remote_state", ["done", "running", "failed"])
def test_remote_task_reuse_only_resubmits_failed_remote_task(monkeypatch, remote_state):
    document = make_document(DocumentStatus.PROCESSING)
    document.original_filename = "lesson.pdf"
    document.external_task_id = "existing-task"
    service = MagicMock()
    service.document_service.get.return_value = document
    service.mineru_client.get_batch_result.return_value = SimpleNamespace(state=remote_state)
    submitted_task_ids = []
    def submit(*args):
        submitted_task_ids.append(document.external_task_id)
        return document
    def finalize(*args):
        document.status = DocumentStatus.COMPLETED
        return document
    service.submit.side_effect = submit
    service.finalize.side_effect = finalize
    monkeypatch.setattr("app.services.background_processing.MinerUDocumentProcessingService", lambda: service)
    monkeypatch.setattr("app.services.background_processing.sleep", lambda seconds: None)
    BackgroundDocumentProcessor._run_mineru(FakeSession(), document.knowledge_base_id, document.id)
    assert submitted_task_ids == [None if remote_state == "failed" else "existing-task"]


def test_failure_persistence_error_is_logged_without_secrets(monkeypatch, caplog):
    factory = MagicMock(side_effect=RuntimeError("postgresql://secret"))
    monkeypatch.setattr("app.services.background_processing.SessionLocal", factory)
    BackgroundDocumentProcessor._record_failure(uuid4(), 1, ValueError("token-secret"), stage="worker")
    assert "could not be saved" in caplog.text
    assert "postgresql://secret" not in caplog.text
    assert "token-secret" not in caplog.text


@pytest.mark.parametrize("status,attempt,expected", [
    (DocumentStatus.PROCESSING, 4, DocumentStatus.FAILED),
    (DocumentStatus.PROCESSING, 5, DocumentStatus.PROCESSING),
    (DocumentStatus.COMPLETED, 4, DocumentStatus.COMPLETED),
])
def test_failure_persists_in_isolated_database(monkeypatch, status, attempt, expected):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.base import Base
    from app.database.models import Document, KnowledgeBase

    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Only these two tables are involved; unrelated models use PostgreSQL JSONB.
    Base.metadata.create_all(engine, tables=[KnowledgeBase.__table__, Document.__table__])
    factory = sessionmaker(bind=engine)
    doc_id, kb_id = uuid4(), uuid4()
    try:
        with factory() as session:
            session.add(KnowledgeBase(id=kb_id, name="isolated recovery test"))
            session.flush()
            session.add(Document(
                id=doc_id, knowledge_base_id=kb_id, original_filename="test.pdf",
                stored_filename="isolated.pdf", file_path="isolated.pdf", mime_type="application/pdf",
                file_size=1, checksum="a" * 64, status=status, parser=DocumentParser.MINERU,
                processing_attempts=attempt, external_task_id="keep-task", processing_progress=40,
            ))
            session.commit()
        monkeypatch.setattr("app.services.background_processing.SessionLocal", factory)
        BackgroundDocumentProcessor._record_failure(doc_id, 4, RuntimeError("sensitive"), stage="worker")
        with factory() as session:
            document = session.get(Document, doc_id)
            assert document.status == expected
            assert document.external_task_id == "keep-task"
            assert document.processing_progress == 40
            assert (document.last_processing_finished_at is not None) == (expected == DocumentStatus.FAILED)
    finally:
        engine.dispose()
