from uuid import UUID, uuid4

import pytest

from app.database.models import (
    Conversation,
    KnowledgeBase,
    Message,
    MessageRole,
)
from app.database.session import SessionLocal


@pytest.mark.integration
def test_conversation_relationships_and_cascade_delete() -> None:
    knowledge_base_id: UUID | None = None
    conversation_id: UUID | None = None
    user_message_id: UUID | None = None
    assistant_message_id: UUID | None = None

    unique_value = uuid4().hex

    with SessionLocal() as session:
        try:
            knowledge_base = KnowledgeBase(
                name=f"conversation-test-{unique_value}",
                description="Temporary conversation integration test",
            )

            conversation = Conversation(
                knowledge_base=knowledge_base,
                title="Milvus 测试对话",
            )

            user_message = Message(
                conversation=conversation,
                role=MessageRole.USER,
                content="Milvus 是什么？",
            )

            assistant_message = Message(
                conversation=conversation,
                role=MessageRole.ASSISTANT,
                content="Milvus 是一个向量数据库。[1]",
                sources=[
                    {
                        "index": 1,
                        "document_id": str(uuid4()),
                        "content": "Milvus 是一个向量数据库。",
                    }
                ],
            )

            session.add(knowledge_base)
            session.commit()

            knowledge_base_id = knowledge_base.id
            conversation_id = conversation.id
            user_message_id = user_message.id
            assistant_message_id = assistant_message.id

            assert conversation.knowledge_base_id == knowledge_base.id
            assert user_message.conversation_id == conversation.id
            assert assistant_message.conversation_id == conversation.id

            assert user_message.role == MessageRole.USER
            assert user_message.sources is None
            assert assistant_message.role == MessageRole.ASSISTANT
            assert assistant_message.sources is not None
            assert assistant_message.sources[0]["index"] == 1

            session.delete(knowledge_base)
            session.commit()

            assert session.get(KnowledgeBase, knowledge_base_id) is None
            assert session.get(Conversation, conversation_id) is None
            assert session.get(Message, user_message_id) is None
            assert session.get(Message, assistant_message_id) is None

        finally:
            if knowledge_base_id is not None:
                remaining = session.get(KnowledgeBase, knowledge_base_id)

                if remaining is not None:
                    session.delete(remaining)
                    session.commit()