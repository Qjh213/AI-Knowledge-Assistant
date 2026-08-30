from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.database.models import DocumentParser, DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    checksum: str
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    parser: DocumentParser = DocumentParser.LOCAL
    external_task_id: str | None = None
    processing_progress: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    offset: int
    limit: int
