from pydantic import BaseModel, Field


class DashboardOverviewResponse(BaseModel):
    knowledge_base_count: int = Field(ge=0)
    processed_document_count: int = Field(ge=0)
    conversation_count: int = Field(ge=0)

