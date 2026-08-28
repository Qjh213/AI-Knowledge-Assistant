from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RagQuestionRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
        description="Question to answer from the knowledge base",
    )
    retrieval_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of context chunks",
    )
    min_score: float = Field(
        default=0.3,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity score",
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Question cannot be empty"
            )

        return normalized


class RagCitation(BaseModel):
    reference: int
    chunk_id: UUID
    document_id: UUID
    original_filename: str
    page_number: int | None
    content: str
    score: float


class RagAnswerResponse(BaseModel):
    knowledge_base_id: UUID
    question: str
    answer: str
    citations: list[RagCitation]