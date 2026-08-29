from uuid import UUID, uuid4

import pytest

from app.database.models import (
    Conversation,
    KnowledgeBase,
    MessageRole,
)
from app.database.session import SessionLocal
from app.repositories.message import MessageRepository


@pytest.mark.integration
def test_message_history_pagination_and_recent_limit() -> None:
    knowledge_base_id: UUID | None = None
    conversation_id: UUID | None = None
    unique_value = uuid4().hex

    with SessionLocal() as session:
        try:
            knowledge_base = KnowledgeBase(
                name=f"message-history-test-{unique_value}",
            )
            conversation = Conversation(
                knowledge_base=knowledge_base,
                title="Message history test",
            )

            session.add(knowledge_base)
            session.flush()

            knowledge_base_id = knowledge_base.id
            conversation_id = conversation.id

            for index in range(12):
                role = (
                    MessageRole.USER
                    if index % 2 == 0
                    else MessageRole.ASSISTANT
                )

                MessageRepository.create(
                    session,
                    conversation_id,
                    role,
                    f"message-{index}",
                )

            session.commit()

            items, total = (
                MessageRepository.list_for_conversation(
                    session,
                    conversation_id,
                    offset=2,
                    limit=4,
                )
            )

            assert total == 12
            assert [item.content for item in items] == [
                "message-2",
                "message-3",
                "message-4",
                "message-5",
            ]

            recent = MessageRepository.list_recent(
                session,
                conversation_id,
                limit=4,
            )

            assert [item.content for item in recent] == [
                "message-8",
                "message-9",
                "message-10",
                "message-11",
            ]

            assert [item.role for item in recent] == [
                MessageRole.USER,
                MessageRole.ASSISTANT,
                MessageRole.USER,
                MessageRole.ASSISTANT,
            ]

        finally:
            if knowledge_base_id is not None:
                remaining = session.get(
                    KnowledgeBase,
                    knowledge_base_id,
                )

                if remaining is not None:
                    session.delete(remaining)
                    session.commit()