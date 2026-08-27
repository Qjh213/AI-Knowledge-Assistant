from uuid import uuid4

import pytest

from app.services.document_chunker import TextChunk
from app.services.embedding import EmbeddedChunk
from app.services.vector_store import VectorStoreService


pytestmark = pytest.mark.integration


def create_vector(
    dimension: int,
    position: int,
) -> list[float]:
    vector = [0.0] * dimension
    vector[position] = 1.0
    return vector


def test_real_milvus_insert_search_and_delete():
    service = VectorStoreService()
    service.ensure_collection()

    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_ids = [uuid4(), uuid4()]

    chunks = [
        EmbeddedChunk(
            chunk=TextChunk(
                text="人工智能知识库测试文本",
                chunk_index=0,
                page_number=1,
                token_count=10,
                metadata={"source": "integration-test"},
            ),
            embedding=create_vector(
                service.dimension,
                position=0,
            ),
        ),
        EmbeddedChunk(
            chunk=TextChunk(
                text="与查询向量无关的测试文本",
                chunk_index=1,
                page_number=2,
                token_count=12,
                metadata={"source": "integration-test"},
            ),
            embedding=create_vector(
                service.dimension,
                position=1,
            ),
        ),
    ]

    try:
        inserted_count = service.insert_chunks(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_ids=chunk_ids,
            chunks=chunks,
        )

        assert inserted_count == 2

        results = service.search(
            knowledge_base_id=knowledge_base_id,
            query_vector=create_vector(
                service.dimension,
                position=0,
            ),
            limit=2,
        )

        assert len(results) == 2
        assert results[0].chunk_id == chunk_ids[0]
        assert results[0].document_id == document_id
        assert results[0].knowledge_base_id == knowledge_base_id
        assert results[0].content == "人工智能知识库测试文本"
        assert results[0].score == pytest.approx(
            1.0,
            abs=0.0001,
        )

    finally:
        service.delete_document(document_id)

    remaining_results = service.search(
        knowledge_base_id=knowledge_base_id,
        query_vector=create_vector(
            service.dimension,
            position=0,
        ),
        limit=2,
    )

    assert remaining_results == []