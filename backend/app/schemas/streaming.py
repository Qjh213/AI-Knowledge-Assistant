from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.message import MessageResponse
from app.schemas.rag import RagCitation


class StreamEventType(StrEnum):
    USER_MESSAGE = "user_message"
    CITATIONS = "citations"
    TOKEN = "token"
    DONE = "done"
    ERROR = "error"


class StreamUserMessageData(BaseModel):
    message: MessageResponse


class StreamCitationsData(BaseModel):
    citations: list[RagCitation]


class StreamTokenData(BaseModel):
    content: str = Field(min_length=1)


class StreamDoneData(BaseModel):
    message: MessageResponse


class StreamErrorData(BaseModel):
    detail: str = Field(min_length=1)

