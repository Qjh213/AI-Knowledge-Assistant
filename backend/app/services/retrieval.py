from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmbeddingServiceError,
    RetrievalServiceError,
    VectorStoreError,
)
from app.repositories.document import DocumentRepository
from app.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from app.services.embedding import EmbeddingService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.vector_store import VectorStoreService


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
    ) -> None:
        self.embedding_service = (
            embedding_service or EmbeddingService()
        )
        self.vector_store = (
            vector_store or VectorStoreService()
        )

    def search(
        self,
        session: Session,
        knowledge_base_id: UUID,
        request: RetrievalRequest,
    ) -> RetrievalResponse:
        # 先验证知识库存在，避免为无效请求调用嵌入 API。
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        try:
            query_vector = self.embedding_service.embed_texts(
                [request.query]
            )[0]

            matches = self.vector_store.search(
                knowledge_base_id=knowledge_base_id,
                query_vector=query_vector,
                limit=request.limit,
            )

        except (
            EmbeddingServiceError,
            VectorStoreError,
        ) as exc:
            raise RetrievalServiceError(str(exc)) from exc

        documents = DocumentRepository.get_many_for_knowledge_base(
            session,
            knowledge_base_id,
            [match.document_id for match in matches],
        )
        documents_by_id = {
            document.id: document
            for document in documents
        }

        results: list[RetrievalResult] = []

        for match in matches:
            document = documents_by_id.get(match.document_id)

            # Ignore orphaned vectors that no longer have a database document.
            if document is None or match.score < request.min_score:
                continue

            results.append(RetrievalResult(
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                original_filename=document.original_filename,
                chunk_index=match.chunk_index,
                content=match.content,
                page_number=match.page_number,
                token_count=match.token_count,
                metadata=match.metadata,
                score=match.score,
            ))

        return RetrievalResponse(
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            results=results,
            total=len(results),
        )
