from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Conversation,
    Document,
    DocumentStatus,
    KnowledgeBase,
)
from app.schemas.dashboard import DashboardOverviewResponse


class DashboardService:
    @staticmethod
    def get_overview(session: Session) -> DashboardOverviewResponse:
        knowledge_base_count = session.scalar(
            select(func.count()).select_from(KnowledgeBase)
        ) or 0
        processed_document_count = session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.status == DocumentStatus.COMPLETED)
        ) or 0
        conversation_count = session.scalar(
            select(func.count()).select_from(Conversation)
        ) or 0

        return DashboardOverviewResponse(
            knowledge_base_count=knowledge_base_count,
            processed_document_count=processed_document_count,
            conversation_count=conversation_count,
        )

