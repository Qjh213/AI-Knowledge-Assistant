from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)

from app.core.exceptions import (
    EmbeddingServiceError,
    RetrievalServiceError,
    VectorStoreError,
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

        results = [
            RetrievalResult(
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                chunk_index=match.chunk_index,
                content=match.content,
                page_number=match.page_number,
                token_count=match.token_count,
                metadata=match.metadata,
                score=match.score,
            )
            for match in matches
            if match.score >= request.min_score
        ]

        return RetrievalResponse(
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            results=results,
            total=len(results),
        )