from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseNotFoundError,
)
from app.database.models import KnowledgeBase
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
)

from app.services.document_storage import DocumentStorageService
from app.services.vector_store import VectorStoreService


class KnowledgeBaseService:
    @staticmethod
    def get(
        session: Session,
        knowledge_base_id: UUID,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBaseRepository.get(
            session,
            knowledge_base_id,
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(knowledge_base_id)

        return knowledge_base

    @staticmethod
    def list(
        session: Session,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[KnowledgeBase], int]:
        return KnowledgeBaseRepository.list(
            session,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def create(
        session: Session,
        data: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        existing = KnowledgeBaseRepository.get_by_name(
            session,
            data.name,
        )

        if existing is not None:
            raise KnowledgeBaseAlreadyExistsError(data.name)

        try:
            knowledge_base = KnowledgeBaseRepository.create(
                session,
                data,
            )
            session.commit()
            session.refresh(knowledge_base)

            return knowledge_base

        except IntegrityError as exc:
            session.rollback()
            raise KnowledgeBaseAlreadyExistsError(data.name) from exc

        except Exception:
            session.rollback()
            raise

    @staticmethod
    def update(
        session: Session,
        knowledge_base_id: UUID,
        data: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        if data.name is not None and data.name != knowledge_base.name:
            existing = KnowledgeBaseRepository.get_by_name(
                session,
                data.name,
            )

            if existing is not None:
                raise KnowledgeBaseAlreadyExistsError(data.name)

        try:
            updated = KnowledgeBaseRepository.update(
                session,
                knowledge_base,
                data,
            )
            session.commit()
            session.refresh(updated)

            return updated

        except IntegrityError as exc:
            session.rollback()
            conflict_name = data.name or knowledge_base.name
            raise KnowledgeBaseAlreadyExistsError(
                conflict_name
            ) from exc

        except Exception:
            session.rollback()
            raise

    @staticmethod
    def delete(
            session: Session,
            knowledge_base_id: UUID,
    ) -> None:
        knowledge_base = KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        file_paths = [
            document.file_path
            for document in knowledge_base.documents
        ]

        vector_store = VectorStoreService()
        storage_service = DocumentStorageService()

        try:
            vector_store.delete_knowledge_base(
                knowledge_base_id
            )

            KnowledgeBaseRepository.delete(
                session,
                knowledge_base,
            )
            session.commit()

        except Exception:
            session.rollback()
            raise

        for file_path in file_paths:
            storage_service.delete(file_path)