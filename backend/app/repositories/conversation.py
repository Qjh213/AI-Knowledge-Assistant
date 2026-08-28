from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Conversation
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
)


class ConversationRepository:
    @staticmethod
    def get(
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
    ) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.knowledge_base_id == knowledge_base_id,
        )
        return session.scalar(statement)

    @staticmethod
    def list_for_knowledge_base(
        session: Session,
        knowledge_base_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        count_statement = (
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.knowledge_base_id == knowledge_base_id,
            )
        )
        total = session.scalar(count_statement) or 0

        statement = (
            select(Conversation)
            .where(
                Conversation.knowledge_base_id == knowledge_base_id,
            )
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(session.scalars(statement).all())

        return items, total

    @staticmethod
    def create(
        session: Session,
        knowledge_base_id: UUID,
        data: ConversationCreate,
    ) -> Conversation:
        conversation = Conversation(
            knowledge_base_id=knowledge_base_id,
            **data.model_dump(),
        )

        session.add(conversation)
        session.flush()
        session.refresh(conversation)

        return conversation

    @staticmethod
    def update(
        session: Session,
        conversation: Conversation,
        data: ConversationUpdate,
    ) -> Conversation:
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(conversation, field, value)

        session.flush()
        session.refresh(conversation)

        return conversation

    @staticmethod
    def delete(
        session: Session,
        conversation: Conversation,
    ) -> None:
        session.delete(conversation)
        session.flush()