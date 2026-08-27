from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pymilvus import DataType, MilvusClient

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.services.embedding import EmbeddedChunk

@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    chunk_id: UUID
    knowledge_base_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    token_count: int | None
    metadata: dict[str, Any]
    score: float


class VectorStoreService:
    def __init__(
        self,
        client: MilvusClient | None = None,
        collection_name: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.client = client or MilvusClient(
            uri=settings.milvus_uri,
            token=settings.milvus_token or None,
        )
        self.collection_name = (
            collection_name or settings.milvus_collection_name
        )
        self.dimension = (
            dimension
            if dimension is not None
            else settings.embedding_dimension
        )

        if not self.collection_name.strip():
            raise VectorStoreError(
                "collection name cannot be empty"
            )

        if self.dimension <= 0:
            raise VectorStoreError(
                "vector dimension must be greater than zero"
            )

    def ensure_collection(self) -> None:
        """Create the document chunk collection when it does not exist."""
        try:
            if self.client.has_collection(self.collection_name):
                self._validate_existing_collection()
                return

            schema = MilvusClient.create_schema(
                auto_id=False,
                enable_dynamic_field=False,
            )

            schema.add_field(
                field_name="id",
                datatype=DataType.VARCHAR,
                is_primary=True,
                max_length=36,
            )
            schema.add_field(
                field_name="knowledge_base_id",
                datatype=DataType.VARCHAR,
                max_length=36,
            )
            schema.add_field(
                field_name="document_id",
                datatype=DataType.VARCHAR,
                max_length=36,
            )
            schema.add_field(
                field_name="chunk_index",
                datatype=DataType.INT64,
            )
            schema.add_field(
                field_name="content",
                datatype=DataType.VARCHAR,
                max_length=8192,
            )
            schema.add_field(
                field_name="page_number",
                datatype=DataType.INT64,
                nullable=True,
            )
            schema.add_field(
                field_name="token_count",
                datatype=DataType.INT64,
                nullable=True,
            )
            schema.add_field(
                field_name="metadata",
                datatype=DataType.JSON,
            )
            schema.add_field(
                field_name="embedding",
                datatype=DataType.FLOAT_VECTOR,
                dim=self.dimension,
            )

            index_params = MilvusClient.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_name="document_chunks_embedding_idx",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )

            self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level="Strong",
            )

        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(str(exc)) from exc

    def insert_chunks(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        chunk_ids: Sequence[UUID],
        chunks: Sequence[EmbeddedChunk],
    ) -> int:
        if not chunks:
            raise VectorStoreError(
                "at least one embedded chunk is required"
            )

        if len(chunk_ids) != len(chunks):
            raise VectorStoreError(
                "chunk ID count does not match embedded chunk count"
            )

        records: list[dict[str, Any]] = []

        for chunk_id, embedded_chunk in zip(
            chunk_ids,
            chunks,
            strict=True,
        ):
            if len(embedded_chunk.embedding) != self.dimension:
                raise VectorStoreError(
                    "vector dimension mismatch: "
                    f"expected {self.dimension}, "
                    f"received {len(embedded_chunk.embedding)}"
                )

            chunk = embedded_chunk.chunk

            records.append(
                {
                    "id": str(chunk_id),
                    "knowledge_base_id": str(knowledge_base_id),
                    "document_id": str(document_id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.text,
                    "page_number": chunk.page_number,
                    "token_count": chunk.token_count,
                    "metadata": chunk.metadata,
                    "embedding": embedded_chunk.embedding,
                }
            )

        try:
            self.ensure_collection()

            result = self.client.insert(
                collection_name=self.collection_name,
                data=records,
            )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(str(exc)) from exc

        inserted_count = int(result.get("insert_count", 0))

        if inserted_count != len(records):
            raise VectorStoreError(
                "inserted vector count does not match requested count"
            )

        return inserted_count

    def delete_document(
        self,
        document_id: UUID,
    ) -> int:
        try:
            self.ensure_collection()

            result = self.client.delete(
                collection_name=self.collection_name,
                filter=f'document_id == "{document_id}"',
            )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(str(exc)) from exc

        return int(result.get("delete_count", 0))

    def delete_knowledge_base(
        self,
        knowledge_base_id: UUID,
    ) -> int:
        try:
            self.ensure_collection()

            result = self.client.delete(
                collection_name=self.collection_name,
                filter=(
                    f'knowledge_base_id == "{knowledge_base_id}"'
                ),
            )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(str(exc)) from exc

        return int(result.get("delete_count", 0))

    def search(
        self,
        knowledge_base_id: UUID,
        query_vector: Sequence[float],
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        if len(query_vector) != self.dimension:
            raise VectorStoreError(
                "query vector dimension mismatch: "
                f"expected {self.dimension}, "
                f"received {len(query_vector)}"
            )

        if limit <= 0:
            raise VectorStoreError(
                "search limit must be greater than zero"
            )

        try:
            self.ensure_collection()

            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[list(query_vector)],
                filter=(
                    f'knowledge_base_id == "{knowledge_base_id}"'
                ),
                limit=limit,
                anns_field="embedding",
                output_fields=[
                    "knowledge_base_id",
                    "document_id",
                    "chunk_index",
                    "content",
                    "page_number",
                    "token_count",
                    "metadata",
                ],
                search_params={
                    "metric_type": "COSINE",
                    "params": {},
                },
            )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(str(exc)) from exc

        if not search_results:
            return []

        results: list[VectorSearchResult] = []

        for hit in search_results[0]:
            entity = hit.get("entity", {})

            results.append(
                VectorSearchResult(
                    chunk_id=UUID(str(hit["id"])),
                    knowledge_base_id=UUID(
                        str(entity["knowledge_base_id"])
                    ),
                    document_id=UUID(
                        str(entity["document_id"])
                    ),
                    chunk_index=int(entity["chunk_index"]),
                    content=str(entity["content"]),
                    page_number=entity.get("page_number"),
                    token_count=entity.get("token_count"),
                    metadata=dict(entity.get("metadata") or {}),
                    score=float(hit["distance"]),
                )
            )

        return results

    def _validate_existing_collection(self) -> None:
        description = self.client.describe_collection(
            collection_name=self.collection_name,
        )

        fields = {
            field["name"]: field
            for field in description["fields"]
        }

        embedding_field = fields.get("embedding")
        if embedding_field is None:
            raise VectorStoreError(
                "existing collection does not contain an embedding field"
            )

        actual_dimension = int(
            embedding_field["params"]["dim"]
        )
        if actual_dimension != self.dimension:
            raise VectorStoreError(
                "existing collection dimension mismatch: "
                f"expected {self.dimension}, "
                f"received {actual_dimension}"
            )