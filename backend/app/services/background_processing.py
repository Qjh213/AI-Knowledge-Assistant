from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic, sleep
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DocumentRetryNotAllowedError
from app.database.models import Document, DocumentParser, DocumentStatus
from app.database.session import SessionLocal
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService
from app.services.document_processing import DocumentProcessingService
from app.services.mineru_processing import MinerUDocumentProcessingService


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
        parser = parser or document.parser

        if retry_only and document.status != DocumentStatus.FAILED:
            raise DocumentRetryNotAllowedError(document_id, document.status)

        if document.status == DocumentStatus.COMPLETED:
            return document

        with self._lock:
            if document_id in self._inflight:
                return document
            self._inflight.add(document_id)

        try:
            # A processing row with no in-memory worker is a recoverable task
            # left behind by a previous application process.
            if document.status != DocumentStatus.PROCESSING:
                DocumentRepository.mark_processing_started(
                    session,
                    document,
                    parser,
                )
                if parser == DocumentParser.MINERU:
                    document.external_task_id = None

            session.commit()
            session.refresh(document)
            self._executor.submit(
                self._run,
                knowledge_base_id,
                document_id,
                parser,
            )
            return document
        except Exception:
            with self._lock:
                self._inflight.discard(document_id)
            raise

    def _run(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        parser: DocumentParser,
    ) -> None:
        try:
            with SessionLocal() as session:
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
        except Exception:
            # Processing services persist a useful failed state themselves.
            # The exception must not terminate the executor worker.
            pass
        finally:
            with self._lock:
                self._inflight.discard(document_id)

    @staticmethod
    def _run_mineru(
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> None:
        service = MinerUDocumentProcessingService()
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
