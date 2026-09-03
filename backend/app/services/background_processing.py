import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from time import monotonic, sleep
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DocumentRetryNotAllowedError
from app.database.models import Document, DocumentParser, DocumentStatus, KnowledgeBase
from app.database.tenant import scope_session
from app.database.session import SessionLocal
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService
from app.services.document_processing import DocumentProcessingService
from app.services.mineru_processing import MinerUDocumentProcessingService
from app.services.quotas import reserve_ai_request


logger = logging.getLogger(__name__)


class BackgroundDocumentProcessor:
    """Run document processing outside the HTTP request thread.

    Document state remains in PostgreSQL, while the executor is intentionally
    process-local. A later request can resume a processing document after an
    application restart.
    """

    def __init__(
        self,
        *,
        max_workers: int | None = None,
    ) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers or settings.background_worker_count,
            thread_name_prefix="document-processing",
        )
        self._inflight: set[UUID] = set()
        self._lock = Lock()
        self._document_service = DocumentService()

    def enqueue(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
        parser: DocumentParser | None,
        *,
        retry_only: bool = False,
    ) -> Document:
        document = self._document_service.get(
            session,
            knowledge_base_id,
            document_id,
        )
        with self._lock:
            session.refresh(document)
            parser = parser or document.parser
            if retry_only and (
                document.status not in {DocumentStatus.FAILED, DocumentStatus.PROCESSING}
                or document_id in self._inflight
            ):
                raise DocumentRetryNotAllowedError(document_id, document.status)
            if document.status == DocumentStatus.COMPLETED:
                return document
            if document_id in self._inflight:
                return document
            self._inflight.add(document_id)

        attempt = document.processing_attempts
        try:
            reserve_ai_request(session, processing_document_id=document_id, active_document_ids=self._active_ids)
        except Exception:
            session.rollback()
            with self._lock:
                self._inflight.discard(document_id)
            raise
        try:
            # A processing row with no in-memory worker is a recoverable task
            # in this single-process deployment. Preserve its remote task.
            if document.parser != parser:
                document.external_task_id = None
            DocumentRepository.mark_processing_started(session, document, parser)
            attempt = document.processing_attempts

            session.commit()
            session.refresh(document)
            self._executor.submit(
                self._run,
                knowledge_base_id,
                document_id,
                parser,
                attempt,
            )
            return document
        except Exception as exc:
            try:
                session.rollback()
            finally:
                self._record_failure(document_id, attempt, exc, stage="queue")
                with self._lock:
                    self._inflight.discard(document_id)
            raise

    def _run(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        parser: DocumentParser,
        attempt: int,
    ) -> None:
        try:
            with SessionLocal() as session:
                if isinstance(session, Session):
                    knowledge_base = session.get(KnowledgeBase, knowledge_base_id)
                    if knowledge_base is not None:
                        scope_session(session, knowledge_base.owner_id)
                if parser == DocumentParser.LOCAL:
                    DocumentProcessingService().process(
                        session,
                        knowledge_base_id,
                        document_id,
                    )
                else:
                    self._run_mineru(
                        session,
                        knowledge_base_id,
                        document_id,
                    )
        except Exception as exc:
            # Status queries and service construction may fail before the
            # processing service has a chance to persist a terminal state.
            self._record_failure(document_id, attempt, exc, stage="worker")
        finally:
            with self._lock:
                self._inflight.discard(document_id)

    def _active_ids(self):
        with self._lock:
            return tuple(self._inflight)

    @staticmethod
    def _record_failure(
        document_id: UUID, attempt: int, error: Exception, *, stage: str
    ) -> None:
        # Never log exception text/tracebacks: upstream errors may contain
        # signed URLs, API tokens or database connection strings.
        logger.error(
            "Document task failed document_id=%s attempt=%s stage=%s error_type=%s",
            document_id, attempt, stage, type(error).__name__,
        )
        try:
            with SessionLocal() as session:
                document = session.scalar(
                    select(Document).where(Document.id == document_id).with_for_update()
                )
                if (
                    document is None
                    or document.status != DocumentStatus.PROCESSING
                    or document.processing_attempts != attempt
                ):
                    return
                document.status = DocumentStatus.FAILED
                document.error_message = (
                    "后台处理任务异常中断，请检查网络后重试；已有 MinerU 任务将优先复用。"
                )
                document.last_processing_finished_at = datetime.now(UTC)
                session.commit()
        except Exception as persistence_error:
            logger.error(
                "Document failure state could not be saved document_id=%s error_type=%s",
                document_id, type(persistence_error).__name__,
            )

    @staticmethod
    def _run_mineru(
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> None:
        service = MinerUDocumentProcessingService()
        document = service.document_service.get(session, knowledge_base_id, document_id)
        if document.external_task_id:
            result = service.mineru_client.get_batch_result(
                document.external_task_id, file_name=document.original_filename
            )
            # Completed/running tasks can be resumed without another upload.
            # Only an explicitly failed remote task needs a new submission.
            if result.state == "failed":
                document.external_task_id = None
                session.commit()
        document = service.submit(session, knowledge_base_id, document_id)
        deadline = monotonic() + settings.mineru_timeout_seconds

        while document.status == DocumentStatus.PROCESSING:
            if monotonic() >= deadline:
                DocumentRepository.update_processing_state(
                    session,
                    document,
                    DocumentStatus.FAILED,
                    error_message="MinerU background processing timed out",
                    processing_progress=0,
                )
                DocumentRepository.mark_processing_finished(session, document)
                session.commit()
                return

            sleep(settings.mineru_poll_interval_seconds)
            document = service.finalize(
                session,
                knowledge_base_id,
                document_id,
            )


background_document_processor = BackgroundDocumentProcessor()
