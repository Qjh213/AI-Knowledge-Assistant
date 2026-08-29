from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Message, MessageRole


class MessageRepository:
    @staticmethod
    def list_for_conversation(
        session: Session,
        conversation_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Message], int]:
        count_statement = (
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
        )
        total = session.scalar(count_statement) or 0

        statement = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
            .order_by(
                Message.created_at.asc(),
                Message.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(session.scalars(statement).all())

        return items, total

    @staticmethod
    def list_recent(
        session: Session,
        conversation_id: UUID,
        limit: int = 10,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
            .order_by(
                Message.created_at.desc(),
                Message.id.desc(),
            )
            .limit(limit)
        )

        newest_first = list(
            session.scalars(statement).all()
        )

        return list(reversed(newest_first))

    @staticmethod
    def create(
        session: Session,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
        )

        session.add(message)
        session.flush()
        session.refresh(message)

        return message