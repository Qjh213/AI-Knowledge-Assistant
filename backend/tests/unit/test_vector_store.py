from uuid import uuid4

import pytest

from app.core.exceptions import VectorStoreError
from app.services.document_chunker import TextChunk
from app.services.embedding import EmbeddedChunk
from app.services.vector_store import VectorStoreService


class FakeMilvusClient:
    def __init__(self) -> None:
        self.inserted_data = None
        self.deleted_filter = None
        self.search_arguments = None
        self.raise_error = False

    def insert(self, collection_name, data):
        if self.raise_error:
            raise RuntimeError("Milvus unavailable")

        self.inserted_data = data
        return {"insert_count": len(data)}

    def delete(self, collection_name, filter):
        if self.raise_error:
            raise RuntimeError("Milvus unavailable")

        self.deleted_filter = filter
        return {"delete_count": 2}

    def search(self, **kwargs):
        if self.raise_error:
            raise RuntimeError("Milvus unavailable")

        self.search_arguments = kwargs
        record = self.inserted_data[0]

        return [
            [
                {
                    "id": record["id"],
                    "distance": 0.92,
                    "entity": {
                        key: value
                        for key, value in record.items()
                        if key not in {"id", "embedding"}
                    },
                }
            ]
        ]


def create_embedded_chunk(
    chunk_index: int = 0,
    embedding: list[float] | None = None,
) -> EmbeddedChunk:
    chunk = TextChunk(
        text="用于测试的知识库文本",
        chunk_index=chunk_index,
        page_number=1,
        token_count=8,
        metadata={"source": "test.txt"},
    )

    return EmbeddedChunk(
        chunk=chunk,
        embedding=embedding or [0.1, 0.2, 0.3],
    )


def create_service():
    client = FakeMilvusClient()
    service = VectorStoreService(
        client=client,
        collection_name="test_document_chunks",
        dimension=3,
    )

    # 单元测试只检查业务逻辑，不连接真实 Milvus。
    service.ensure_collection = lambda: None

    return service, client


def test_insert_chunks_maps_all_fields():
    service, client = create_service()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()

    inserted_count = service.insert_chunks(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        chunk_ids=[chunk_id],
        chunks=[create_embedded_chunk()],
    )

    assert inserted_count == 1

    record = client.inserted_data[0]
    assert record["id"] == str(chunk_id)
    assert record["knowledge_base_id"] == str(knowledge_base_id)
    assert record["document_id"] == str(document_id)
    assert record["chunk_index"] == 0
    assert record["content"] == "用于测试的知识库文本"
    assert record["page_number"] == 1
    assert record["token_count"] == 8
    assert record["metadata"] == {"source": "test.txt"}
    assert record["embedding"] == [0.1, 0.2, 0.3]


def test_reject_empty_chunk_insert():
    service, _ = create_service()

    with pytest.raises(
        VectorStoreError,
        match="at least one embedded chunk",
    ):
        service.insert_chunks(
            knowledge_base_id=uuid4(),
            document_id=uuid4(),
            chunk_ids=[],
            chunks=[],
        )


def test_reject_chunk_id_count_mismatch():
    service, _ = create_service()

    with pytest.raises(
        VectorStoreError,
        match="chunk ID count",
    ):
        service.insert_chunks(
            knowledge_base_id=uuid4(),
            document_id=uuid4(),
            chunk_ids=[],
            chunks=[create_embedded_chunk()],
        )


def test_reject_insert_vector_dimension_mismatch():
    service, _ = create_service()

    with pytest.raises(
        VectorStoreError,
        match="vector dimension mismatch",
    ):
        service.insert_chunks(
            knowledge_base_id=uuid4(),
            document_id=uuid4(),
            chunk_ids=[uuid4()],
            chunks=[
                create_embedded_chunk(
                    embedding=[0.1, 0.2],
                )
            ],
        )


def test_delete_document_uses_document_filter():
    service, client = create_service()
    document_id = uuid4()

    deleted_count = service.delete_document(document_id)

    assert deleted_count == 2
    assert client.deleted_filter == (
        f'document_id == "{document_id}"'
    )


def test_search_filters_by_knowledge_base():
    service, client = create_service()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()

    service.insert_chunks(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        chunk_ids=[chunk_id],
        chunks=[create_embedded_chunk()],
    )

    results = service.search(
        knowledge_base_id=knowledge_base_id,
        query_vector=[0.1, 0.2, 0.3],
        limit=4,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert results[0].knowledge_base_id == knowledge_base_id
    assert results[0].document_id == document_id
    assert results[0].content == "用于测试的知识库文本"
    assert results[0].score == pytest.approx(0.92)

    assert client.search_arguments["filter"] == (
        f'knowledge_base_id == "{knowledge_base_id}"'
    )
    assert client.search_arguments["limit"] == 4
    assert client.search_arguments["anns_field"] == "embedding"


def test_reject_query_vector_dimension_mismatch():
    service, _ = create_service()

    with pytest.raises(
        VectorStoreError,
        match="query vector dimension mismatch",
    ):
        service.search(
            knowledge_base_id=uuid4(),
            query_vector=[0.1, 0.2],
        )


@pytest.mark.parametrize("limit", [0, -1])
def test_reject_invalid_search_limit(limit):
    service, _ = create_service()

    with pytest.raises(
        VectorStoreError,
        match="search limit",
    ):
        service.search(
            knowledge_base_id=uuid4(),
            query_vector=[0.1, 0.2, 0.3],
            limit=limit,
        )


@pytest.mark.parametrize(
    ("operation", "expected_message"),
    [
        ("insert", "Milvus unavailable"),
        ("delete", "Milvus unavailable"),
        ("search", "Milvus unavailable"),
    ],
)
def test_wrap_milvus_errors(operation, expected_message):
    service, client = create_service()
    client.raise_error = True

    with pytest.raises(
        VectorStoreError,
        match=expected_message,
    ):
        if operation == "insert":
            service.insert_chunks(
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                chunk_ids=[uuid4()],
                chunks=[create_embedded_chunk()],
            )
        elif operation == "delete":
            service.delete_document(uuid4())
        else:
            service.search(
                knowledge_base_id=uuid4(),
                query_vector=[0.1, 0.2, 0.3],
            )