from uuid import UUID, uuid4

import pytest

from app.core.exceptions import DocumentProcessingError
from app.database.models import (
    Document,
    DocumentStatus,
    KnowledgeBase,
)
from app.database.session import SessionLocal
from app.repositories.document_chunk import DocumentChunkRepository
from app.services.document_chunker import TextChunk
from app.services.document_parser import (
    ParsedDocument,
    ParsedSection,
)
from app.services.document_processing import (
    DocumentProcessingService,
)
from app.services.embedding import EmbeddedChunk


pytestmark = pytest.mark.integration


class FakeParser:
    def parse(self, file_path: str) -> ParsedDocument:
        return ParsedDocument(
            sections=(
                ParsedSection(
                    text="第一段知识库测试内容。",
                    page_number=1,
                    metadata={"source": "test.txt"},
                ),
                ParsedSection(
                    text="第二段知识库测试内容。",
                    page_number=2,
                    metadata={"source": "test.txt"},
                ),
            ),
            character_count=20,
        )


class FakeChunker:
    def split(
        self,
        document: ParsedDocument,
    ) -> list[TextChunk]:
        return [
            TextChunk(
                text=section.text,
                chunk_index=index,
                page_number=section.page_number,
                token_count=10,
                metadata=section.metadata,
            )
            for index, section in enumerate(document.sections)
        ]


class FakeEmbeddingService:
    def embed_chunks(
        self,
        chunks: list[TextChunk],
    ) -> list[EmbeddedChunk]:
        return [
            EmbeddedChunk(
                chunk=chunk,
                embedding=[float(index), 1.0, 0.0],
            )
            for index, chunk in enumerate(chunks)
        ]


class FailingEmbeddingService:
    def embed_chunks(
        self,
        chunks: list[TextChunk],
    ) -> list[EmbeddedChunk]:
        raise RuntimeError("embedding provider unavailable")


class FakeVectorStore:
    def __init__(self) -> None:
        self.inserted_document_id: UUID | None = None
        self.inserted_chunk_ids: list[UUID] = []
        self.deleted_document_ids: list[UUID] = []

    def insert_chunks(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        chunk_ids,
        chunks,
    ) -> int:
        self.inserted_document_id = document_id
        self.inserted_chunk_ids = list(chunk_ids)
        return len(chunks)

    def delete_document(
        self,
        document_id: UUID,
    ) -> int:
        self.deleted_document_ids.append(document_id)
        return 0


def create_database_document(session):
    unique_value = uuid4().hex

    knowledge_base = KnowledgeBase(
        name=f"processing-test-{unique_value}",
        description="Temporary processing test",
    )
    document = Document(
        knowledge_base=knowledge_base,
        original_filename="test.txt",
        stored_filename=f"{unique_value}.txt",
        file_path=f"data/documents/{unique_value}.txt",
        mime_type="text/plain",
        file_size=20,
        checksum=unique_value * 2,
    )

    session.add(knowledge_base)
    session.commit()
    session.refresh(document)

    return knowledge_base, document


def test_document_processing_success():
    vector_store = FakeVectorStore()

    with SessionLocal() as session:
        knowledge_base, document = create_database_document(
            session
        )
        knowledge_base_id = knowledge_base.id
        document_id = document.id

        try:
            service = DocumentProcessingService(
                parser=FakeParser(),
                chunker=FakeChunker(),
                embedding_service=FakeEmbeddingService(),
                vector_store=vector_store,
            )

            processed = service.process(
                session,
                knowledge_base_id,
                document_id,
            )

            assert processed.status == DocumentStatus.COMPLETED
            assert processed.chunk_count == 2
            assert processed.error_message is None

            database_chunks = (
                DocumentChunkRepository.list_for_document(
                    session,
                    document_id,
                )
            )

            assert len(database_chunks) == 2
            assert database_chunks[0].chunk_index == 0
            assert database_chunks[0].page_number == 1
            assert database_chunks[1].chunk_index == 1
            assert database_chunks[1].page_number == 2

            assert vector_store.inserted_document_id == document_id
            assert vector_store.inserted_chunk_ids == [
                chunk.id
                for chunk in database_chunks
            ]

        finally:
            remaining = session.get(
                KnowledgeBase,
                knowledge_base_id,
            )
            if remaining is not None:
                session.delete(remaining)
                session.commit()


def test_document_processing_failure_marks_document_failed():
    vector_store = FakeVectorStore()

    with SessionLocal() as session:
        knowledge_base, document = create_database_document(
            session
        )
        knowledge_base_id = knowledge_base.id
        document_id = document.id

        try:
            service = DocumentProcessingService(
                parser=FakeParser(),
                chunker=FakeChunker(),
                embedding_service=FailingEmbeddingService(),
                vector_store=vector_store,
            )

            with pytest.raises(
                DocumentProcessingError,
                match="embedding provider unavailable",
            ):
                service.process(
                    session,
                    knowledge_base_id,
                    document_id,
                )

            failed_document = session.get(
                Document,
                document_id,
            )

            assert failed_document is not None
            assert failed_document.status == DocumentStatus.FAILED
            assert failed_document.chunk_count == 0
            assert (
                failed_document.error_message
                == "embedding provider unavailable"
            )

            assert (
                DocumentChunkRepository.list_for_document(
                    session,
                    document_id,
                )
                == []
            )
            assert document_id in (
                vector_store.deleted_document_ids
            )

        finally:
            remaining = session.get(
                KnowledgeBase,
                knowledge_base_id,
            )
            if remaining is not None:
                session.delete(remaining)
                session.commit()