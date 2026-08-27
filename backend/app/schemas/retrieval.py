from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrievalRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=4000,
        description="Question or search text",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of matching chunks",
    )
    min_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity score",
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Retrieval query cannot be empty"
            )

        return normalized


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    original_filename: str
    chunk_index: int
    content: str
    page_number: int | None
    token_count: int | None
    metadata: dict[str, Any]
    score: float


class RetrievalResponse(BaseModel):
    knowledge_base_id: UUID
    query: str
    results: list[RetrievalResult]
    total: int