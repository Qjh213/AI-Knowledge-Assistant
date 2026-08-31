from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import DocumentProcessingError
from app.database.models import (
    Document,
    DocumentChunk,
    DocumentParser,
    DocumentStatus,
)
from app.repositories.document import DocumentRepository
from app.repositories.document_chunk import DocumentChunkRepository
from app.services.document import DocumentService
from app.services.document_chunker import DocumentChunker
from app.services.document_parser import (
    DocumentParserService,
    ParsedDocument,
)
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStoreService


class DocumentProcessingService:
    def __init__(
        self,
        parser: DocumentParserService | None = None,
        chunker: DocumentChunker | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        document_service: DocumentService | None = None,
    ) -> None:
        self.parser = parser or DocumentParserService()
        self.chunker = chunker or DocumentChunker()
        self.embedding_service = (
            embedding_service or EmbeddingService()
        )
        self.vector_store = (
            vector_store or VectorStoreService()
        )
        self.document_service = (
            document_service or DocumentService()
        )

    def index_parsed_document(
        self,
        session: Session,
        document: Document,
        parsed_document: ParsedDocument,
    ) -> Document:
        """Chunk, embed, and index an already parsed document."""
        text_chunks = self.chunker.split(
            parsed_document
        )
        embedded_chunks = (
            self.embedding_service.embed_chunks(
                text_chunks
            )
        )

        # 清除上一次处理可能留下的数据。
        self.vector_store.delete_document(document.id)

        DocumentChunkRepository.delete_for_document(
            session,
            document.id,
        )

        database_chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.text,
                page_number=chunk.page_number,
                token_count=chunk.token_count,
                extra_metadata=chunk.metadata,
            )
            for chunk in text_chunks
        ]

        DocumentChunkRepository.create_many(
            session,
            database_chunks,
        )

        self.vector_store.insert_chunks(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            chunk_ids=[
                chunk.id
                for chunk in database_chunks
            ],
            chunks=embedded_chunks,
        )

        DocumentRepository.update_processing_state(
            session,
            document,
            DocumentStatus.COMPLETED,
            chunk_count=len(database_chunks),
            error_message=None,
            processing_progress=100,
        )
        DocumentRepository.mark_processing_finished(session, document)

        session.commit()
        session.refresh(document)

        return document

    def process(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document:
        document = self.document_service.get(
            session,
            knowledge_base_id,
            document_id,
        )

        try:
            if not (
                document.status == DocumentStatus.PROCESSING
                and document.parser == DocumentParser.LOCAL
            ):
                DocumentRepository.mark_processing_started(
                    session,
                    document,
                    DocumentParser.LOCAL,
                )
            document.chunk_count = 0
            session.commit()
            session.refresh(document)

            parsed_document = self.parser.parse(
                document.file_path
            )

            return self.index_parsed_document(
                session,
                document,
                parsed_document,
            )

        except Exception as exc:
            session.rollback()

            # 如果 Milvus 已经写入了部分数据，尽力清理。
            try:
                self.vector_store.delete_document(document_id)
            except Exception:
                pass

            detail = str(exc)

            try:
                failed_document = DocumentRepository.get(
                    session,
                    document_id,
                )

                if failed_document is not None:
                    DocumentChunkRepository.delete_for_document(
                        session,
                        document_id,
                    )
                    DocumentRepository.update_processing_state(
                        session,
                        failed_document,
                        DocumentStatus.FAILED,
                        chunk_count=0,
                        error_message=detail,
                        processing_progress=0,
                    )
                    DocumentRepository.mark_processing_finished(
                        session,
                        failed_document,
                    )
                    session.commit()
            except Exception:
                session.rollback()

            raise DocumentProcessingError(
                document_id,
                detail,
            ) from exc
