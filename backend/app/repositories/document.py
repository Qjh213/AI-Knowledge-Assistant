from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Document


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