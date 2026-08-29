from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.models import MessageRole
from app.schemas.rag import RagCitation


class MessageCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="User message sent to the conversation",
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

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Message content cannot be empty")

        return normalized


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    sources: list[RagCitation] | None
    created_at: datetime
    updated_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    offset: int
    limit: int


class MessageTurnResponse(BaseModel):
    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse