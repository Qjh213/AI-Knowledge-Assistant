from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Document,
    DocumentParser,
    DocumentStatus,
)


class DocumentRepository:
    @staticmethod
    def get(
        session: Session,
        document_id: UUID,
    ) -> Document | None:
        return session.get(Document, document_id)

    @staticmethod
    def get_for_knowledge_base(
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
        return session.scalar(statement)

    @staticmethod
    def get_by_checksum(
        session: Session,
        knowledge_base_id: UUID,
        checksum: str,
    ) -> Document | None:
        statement = select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.checksum == checksum,
        )
        return session.scalar(statement)

    @staticmethod
    def list_for_knowledge_base(
        session: Session,
        knowledge_base_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Document], int]:
        filters = (
            Document.knowledge_base_id == knowledge_base_id
        )

        count_statement = (
            select(func.count())
            .select_from(Document)
            .where(filters)
        )
        total = session.scalar(count_statement) or 0

        statement = (
            select(Document)
            .where(filters)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(session.scalars(statement).all())

        return items, total

    @staticmethod
    def list_all_for_knowledge_base(
        session: Session,
        knowledge_base_id: UUID,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.asc(), Document.id.asc())
        )
        return list(session.scalars(statement).all())

    @staticmethod
    def create(
        session: Session,
        document: Document,
    ) -> Document:
        session.add(document)
        session.flush()
        session.refresh(document)

        return document

    @staticmethod
    def delete(
        session: Session,
        document: Document,
    ) -> None:
        session.delete(document)
        session.flush()

    @staticmethod
    def update_processing_state(
            session: Session,
            document: Document,
            status: DocumentStatus,
            *,
            chunk_count: int | None = None,
            error_message: str | None = None,
            parser: DocumentParser | None = None,
            external_task_id: str | None = None,
            processing_progress: int | None = None,
    ) -> Document:
        if processing_progress is not None and not (
                0 <= processing_progress <= 100
        ):
            raise ValueError(
                "Processing progress must be between 0 and 100"
            )

        document.status = status
        document.error_message = error_message

        if chunk_count is not None:
            document.chunk_count = chunk_count

        if parser is not None:
            document.parser = parser

        if external_task_id is not None:
            document.external_task_id = external_task_id

        if processing_progress is not None:
            document.processing_progress = processing_progress

        session.flush()
        session.refresh(document)

        return document

    @staticmethod
    def get_many_for_knowledge_base(
        session: Session,
        knowledge_base_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[Document]:
        ids = list(set(document_ids))

        if not ids:
            return []

        statement = select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.id.in_(ids),
        )

        return list(session.scalars(statement).all())
