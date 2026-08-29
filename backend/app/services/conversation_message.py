from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.models import Message, MessageRole
from app.repositories.message import MessageRepository
from app.schemas.message import MessageCreate
from app.schemas.rag import RagQuestionRequest
from app.services.conversation import ConversationService
from app.services.query_rewriter import QueryRewriteService
from app.services.rag import RagService
from app.core.config import settings


class ConversationMessageService:
    def __init__(
        self,
        query_rewriter: QueryRewriteService | None = None,
        rag_service: RagService | None = None,
        history_limit: int | None = None,
    ) -> None:
        resolved_history_limit = (
            history_limit
            if history_limit is not None
            else settings.conversation_history_limit
        )

        if resolved_history_limit <= 0:
            raise ValueError(
                "History limit must be greater than zero"
            )

        self.query_rewriter = (
            query_rewriter or QueryRewriteService()
        )
        self.rag_service = rag_service or RagService()
        self.history_limit = resolved_history_limit

    @staticmethod
    def list(
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Message], int]:
        ConversationService.get(
            session,
            knowledge_base_id,
            conversation_id,
        )

        return MessageRepository.list_for_conversation(
            session,
            conversation_id,
            offset=offset,
            limit=limit,
        )

    def send(
        self,
        session: Session,
        knowledge_base_id: UUID,
        conversation_id: UUID,
        data: MessageCreate,
    ) -> tuple[Message, Message]:
        conversation = ConversationService.get(
            session,
            knowledge_base_id,
            conversation_id,
        )

        try:
            history = MessageRepository.list_recent(
                session,
                conversation_id,
                limit=self.history_limit,
            )

            standalone_question = self.query_rewriter.rewrite(
                question=data.content,
                history=history,
            )

            rag_response = self.rag_service.answer(
                session,
                knowledge_base_id,
                RagQuestionRequest(
                    question=standalone_question,
                    retrieval_limit=data.retrieval_limit,
                    min_score=data.min_score,
                ),
            )

            sources = [
                citation.model_dump(mode="json")
                for citation in rag_response.citations
            ]

            user_message = MessageRepository.create(
                session,
                conversation_id,
                MessageRole.USER,
                data.content,
            )

            assistant_message = MessageRepository.create(
                session,
                conversation_id,
                MessageRole.ASSISTANT,
                rag_response.answer,
                sources=sources or None,
            )

            if conversation.title is None:
                conversation.title = self._create_title(
                    data.content
                )

            conversation.updated_at = datetime.now(UTC)

            session.commit()
            session.refresh(user_message)
            session.refresh(assistant_message)

            return user_message, assistant_message

        except Exception:
            session.rollback()
            raise

    @staticmethod
    def _create_title(content: str) -> str:
        normalized = content.strip()

        if len(normalized) <= 60:
            return normalized

        return f"{normalized[:59]}…"