from uuid import UUID

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
)
from app.database.models import Document
from app.repositories.document import DocumentRepository
from app.services.document_storage import DocumentStorageService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.vector_store import VectorStoreService
from app.services.quotas import upload_budget


class DocumentService:
    def __init__(
            self,
            storage_service: DocumentStorageService | None = None,
            vector_store: VectorStoreService | None = None,
    ) -> None:
        self.storage_service = (
                storage_service or DocumentStorageService()
        )
        self.vector_store = vector_store

    async def upload(
        self,
        session: Session,
        knowledge_base_id: UUID,
        upload: UploadFile,
    ) -> Document:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        # Competing uploads must wait for the user row lock off the event loop.
        budget = await run_in_threadpool(upload_budget, session)
        storage = self.storage_service
        if budget is not None:
            storage = DocumentStorageService(
                storage_path=storage.storage_path,
                max_size_bytes=min(storage.max_size_bytes, budget),
                allowed_extensions=tuple(storage.allowed_extensions),
            )
        stored = await storage.store(upload)

        existing = DocumentRepository.get_by_checksum(
            session,
            knowledge_base_id,
            stored.checksum,
        )

        if existing is not None:
            self.storage_service.delete(stored.file_path)
            raise DocumentAlreadyExistsError(
                knowledge_base_id,
                stored.original_filename,
            )

        document = Document(
            knowledge_base_id=knowledge_base_id,
            original_filename=stored.original_filename,
            stored_filename=stored.stored_filename,
            file_path=stored.file_path,
            mime_type=stored.mime_type,
            file_size=stored.file_size,
            checksum=stored.checksum,
        )

        try:
            created = DocumentRepository.create(
                session,
                document,
            )
            session.commit()
            session.refresh(created)

            return created

        except IntegrityError as exc:
            session.rollback()
            self.storage_service.delete(stored.file_path)
            raise DocumentAlreadyExistsError(
                knowledge_base_id,
                stored.original_filename,
            ) from exc

        except Exception:
            session.rollback()
            self.storage_service.delete(stored.file_path)
            raise

    def list(
        self,
        session: Session,
        knowledge_base_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Document], int]:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        return DocumentRepository.list_for_knowledge_base(
            session,
            knowledge_base_id,
            offset=offset,
            limit=limit,
        )

    def get(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        document = DocumentRepository.get_for_knowledge_base(
            session,
            knowledge_base_id,
            document_id,
        )

        if document is None:
            raise DocumentNotFoundError(
                knowledge_base_id,
                document_id,
            )

        return document

    def delete(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> None:
        document = self.get(
            session,
            knowledge_base_id,
            document_id,
        )
        file_path = document.file_path
        vector_store = (
                self.vector_store or VectorStoreService()
        )

        try:
            vector_store.delete_document(document.id)

            DocumentRepository.delete(
                session,
                document,
            )
            session.commit()

        except Exception:
            session.rollback()
            raise

        self.storage_service.delete(file_path)
