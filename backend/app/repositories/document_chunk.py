from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import DocumentChunk


class DocumentChunkRepository:
    @staticmethod
    def create_many(
        session: Session,
        chunks: Sequence[DocumentChunk],
    ) -> list[DocumentChunk]:
        items = list(chunks)

        if not items:
            return []

        session.add_all(items)
        session.flush()

        return items

    @staticmethod
    def list_for_document(
        session: Session,
        document_id: UUID,
    ) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )

        return list(session.scalars(statement).all())

    @staticmethod
    def delete_for_document(
        session: Session,
        document_id: UUID,
    ) -> int:
        statement = delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        )

        result = session.execute(statement)
        session.flush()

        return int(result.rowcount or 0)