from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConversationNotFoundError
from app.database.models import Conversation
from app.repositories.conversation import ConversationRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
)
from app.services.knowledge_base import KnowledgeBaseService


class ConversationService:
    @staticmethod
    def list_recent(
        session: Session,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Conversation, str]], int]:
        return ConversationRepository.list_recent(
            session,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def get(
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
    ) -> Conversation:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        conversation = ConversationRepository.get(
            session,
            knowledge_base_id,
            conversation_id,
        )

        if conversation is None:
            raise ConversationNotFoundError(
                knowledge_base_id,
                conversation_id,
            )

        return conversation

    @staticmethod
    def list(
        session: Session,
        knowledge_base_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        return ConversationRepository.list_for_knowledge_base(
            session,
            knowledge_base_id,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def create(
        session: Session,
        knowledge_base_id: UUID,
        data: ConversationCreate,
    ) -> Conversation:
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        try:
            conversation = ConversationRepository.create(
                session,
                knowledge_base_id,
                data,
            )
            session.commit()
            session.refresh(conversation)

            return conversation

        except Exception:
            session.rollback()
            raise

    @staticmethod
    def update(
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
        data: ConversationUpdate,
    ) -> Conversation:
        conversation = ConversationService.get(
            session,
            knowledge_base_id,
            conversation_id,
        )

        try:
            updated = ConversationRepository.update(
                session,
                conversation,
                data,
            )
            session.commit()
            session.refresh(updated)

            return updated

        except Exception:
            session.rollback()
            raise

    @staticmethod
    def delete(
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
    ) -> None:
        conversation = ConversationService.get(
            session,
            knowledge_base_id,
            conversation_id,
        )

        try:
            ConversationRepository.delete(
                session,
                conversation,
            )
            session.commit()

        except Exception:
            session.rollback()
            raise
