from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import (
    EmbeddingServiceError,
    KnowledgeBaseNotFoundError,
    RetrievalServiceError,
)
from app.repositories.document import DocumentRepository
from app.schemas.retrieval import RetrievalRequest
from app.services.knowledge_base import KnowledgeBaseService
from app.services.retrieval import (
    RetrievalService,
    bm25_scores,
    lexical_relevance,
    reciprocal_rank_fusion,
)
from app.services.vector_store import VectorSearchResult


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.received_texts = None
        self.called = False

    def embed_texts(self, texts):
        self.called = True
        self.received_texts = list(texts)
        return [[0.1, 0.2, 0.3]]


class FakeVectorStore:
    def __init__(self, results=None) -> None:
        self.results = results or []
        self.received_knowledge_base_id = None
        self.received_query_vector = None
        self.received_limit = None

    def search(
        self,
        knowledge_base_id,
        query_vector,
        limit,
    ):
        self.received_knowledge_base_id = (
            knowledge_base_id
        )
        self.received_query_vector = list(query_vector)
        self.received_limit = limit

        return self.results

    def search_lexical(
        self,
        knowledge_base_id,
        query,
        query_vector,
        limit,
    ):
        return []


class FakeRerankingService:
    def rank(self, query, documents):
        return sorted(
            range(len(documents)),
            key=lambda index: (
                "create_agent" not in documents[index],
                index,
            ),
        )


def create_search_result(
    *,
    knowledge_base_id,
    score,
    content,
):
    return VectorSearchResult(
        chunk_id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        page_number=1,
        token_count=10,
        metadata={"source": "test.txt"},
        score=score,
    )


def test_retrieval_maps_and_filters_results(
    monkeypatch: pytest.MonkeyPatch,
):
    knowledge_base_id = uuid4()

    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        lambda session, target_id: object(),
    )

    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore(
        results=[
            create_search_result(
                knowledge_base_id=knowledge_base_id,
                score=0.91,
                content="高相关文本",
            ),
            create_search_result(
                knowledge_base_id=knowledge_base_id,
                score=0.25,
                content="低相关文本",
            ),
        ]
    )
    monkeypatch.setattr(
        DocumentRepository,
        "get_many_for_knowledge_base",
        lambda session, target_id, document_ids: [
            SimpleNamespace(
                id=match.document_id,
                original_filename="guide.txt",
            )
            for match in vector_store.results
        ],
    )

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        reranking_service=FakeRerankingService(),
    )

    request = RetrievalRequest(
        query="  什么是向量数据库？  ",
        limit=8,
        min_score=0.5,
    )

    response = service.search(
        session=object(),
        knowledge_base_id=knowledge_base_id,
        request=request,
    )

    assert embedding_service.received_texts == [
        "什么是向量数据库？"
    ]
    assert (
        vector_store.received_knowledge_base_id
        == knowledge_base_id
    )
    assert vector_store.received_query_vector == [
        0.1,
        0.2,
        0.3,
    ]
    assert vector_store.received_limit == 80

    assert response.knowledge_base_id == knowledge_base_id
    assert response.query == "什么是向量数据库？"
    assert response.total == 1
    assert len(response.results) == 1
    assert response.results[0].original_filename == "guide.txt"
    assert response.results[0].content == "高相关文本"
    assert response.results[0].score == pytest.approx(0.91)


def test_lexical_relevance_supports_identifiers_and_plural_forms():
    assert lexical_relevance(
        "create_agent 与 Retriever",
        "Use create_agent to build agents with retrievers.",
    ) == pytest.approx(1.0)


def test_bm25_and_rrf_are_independent_of_vector_score_scale():
    scores = bm25_scores(
        "create_agent LangGraph",
        [
            "generic agent overview",
            "create_agent is implemented with LangGraph",
            "unrelated database material",
        ],
    )

    assert scores[1] > scores[0]
    assert reciprocal_rank_fusion(3, scores)[0] == 1


def test_retrieval_reranks_larger_candidate_pool(
    monkeypatch: pytest.MonkeyPatch,
):
    knowledge_base_id = uuid4()
    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        lambda session, target_id: object(),
    )
    vector_store = FakeVectorStore(results=[
        create_search_result(
            knowledge_base_id=knowledge_base_id,
            score=0.70,
            content="智能体的一般概念介绍",
        ),
        create_search_result(
            knowledge_base_id=knowledge_base_id,
            score=0.66,
            content="使用 create_agent 创建 LangGraph 智能体",
        ),
    ])
    monkeypatch.setattr(
        DocumentRepository,
        "get_many_for_knowledge_base",
        lambda session, target_id, document_ids: [
            SimpleNamespace(
                id=match.document_id,
                original_filename="guide.txt",
            )
            for match in vector_store.results
        ],
    )
    service = RetrievalService(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        reranking_service=FakeRerankingService(),
    )

    response = service.search(
        session=object(),
        knowledge_base_id=knowledge_base_id,
        request=RetrievalRequest(
            query="create_agent 如何创建 LangGraph 智能体？",
            limit=1,
        ),
    )

    assert vector_store.received_limit == 10
    assert response.results[0].content.startswith("使用 create_agent")
    assert response.results[0].score == pytest.approx(0.66)


def test_retrieval_returns_empty_results(
    monkeypatch: pytest.MonkeyPatch,
):
    knowledge_base_id = uuid4()

    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        lambda session, target_id: object(),
    )

    service = RetrievalService(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
        reranking_service=FakeRerankingService(),
    )

    response = service.search(
        session=object(),
        knowledge_base_id=knowledge_base_id,
        request=RetrievalRequest(query="没有匹配结果"),
    )

    assert response.results == []
    assert response.total == 0


def test_missing_knowledge_base_skips_embedding(
    monkeypatch: pytest.MonkeyPatch,
):
    knowledge_base_id = uuid4()
    embedding_service = FakeEmbeddingService()

    def raise_not_found(session, target_id):
        raise KnowledgeBaseNotFoundError(target_id)

    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        raise_not_found,
    )

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=FakeVectorStore(),
        reranking_service=FakeRerankingService(),
    )

    with pytest.raises(KnowledgeBaseNotFoundError):
        service.search(
            session=object(),
            knowledge_base_id=knowledge_base_id,
            request=RetrievalRequest(query="测试问题"),
        )

    assert embedding_service.called is False


def test_retrieval_wraps_embedding_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    knowledge_base_id = uuid4()

    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        lambda session, target_id: object(),
    )

    class FailingEmbeddingService:
        def embed_texts(self, texts):
            raise EmbeddingServiceError(
                "provider unavailable"
            )

    service = RetrievalService(
        embedding_service=FailingEmbeddingService(),
        vector_store=FakeVectorStore(),
        reranking_service=FakeRerankingService(),
    )

    with pytest.raises(
        RetrievalServiceError,
        match="provider unavailable",
    ):
        service.search(
            session=object(),
            knowledge_base_id=knowledge_base_id,
            request=RetrievalRequest(query="测试问题"),
        )
