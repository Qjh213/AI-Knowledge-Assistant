from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.database.models import Message, MessageRole
from app.repositories.message import MessageRepository
from app.schemas.message import MessageCreate
from app.schemas.rag import RagAnswerResponse, RagCitation
from app.schemas.streaming import StreamEventType
from app.services.conversation import ConversationService
from app.services.conversation_message import (
    ConversationMessageService,
)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.refreshed: list[object] = []

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def refresh(self, value: object) -> None:
        self.refreshed.append(value)


class FakeQueryRewriter:
    def __init__(
        self,
        result: str = "Milvus 有什么作用？",
    ) -> None:
        self.result = result
        self.question: str | None = None
        self.history: list[Message] | None = None

    def rewrite(
        self,
        question: str,
        history: list[Message],
    ) -> str:
        self.question = question
        self.history = history

        return self.result


class FakeRagService:
    def __init__(
        self,
        response: RagAnswerResponse,
    ) -> None:
        self.response = response
        self.knowledge_base_id = None
        self.request = None

    def answer(
        self,
        session,
        knowledge_base_id,
        request,
    ) -> RagAnswerResponse:
        self.knowledge_base_id = knowledge_base_id
        self.request = request

        return self.response


def create_rag_response(
    knowledge_base_id,
) -> RagAnswerResponse:
    return RagAnswerResponse(
        knowledge_base_id=knowledge_base_id,
        question="Milvus 有什么作用？",
        answer="Milvus 用于保存和检索向量。[1]",
        citations=[
            RagCitation(
                reference=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                original_filename="milvus.txt",
                page_number=2,
                content="Milvus 用于保存和检索向量。",
                score=0.91,
            )
        ],
    )


def test_send_rewrites_question_and_saves_messages(
    monkeypatch,
):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    conversation = SimpleNamespace(
        id=conversation_id,
        knowledge_base_id=knowledge_base_id,
        title=None,
        updated_at=None,
    )

    history = [
        Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content="Milvus 是什么？",
        ),
        Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="Milvus 是一个向量数据库。[1]",
        ),
    ]

    monkeypatch.setattr(
        ConversationService,
        "get",
        lambda session, knowledge_base_id, conversation_id: (
            conversation
        ),
    )
    monkeypatch.setattr(
        MessageRepository,
        "list_recent",
        lambda session, conversation_id, limit: history,
    )

    created_messages: list[Message] = []

    def fake_create(
        session,
        conversation_id,
        role,
        content,
        sources=None,
    ):
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
        )
        created_messages.append(message)
        return message

    monkeypatch.setattr(
        MessageRepository,
        "create",
        fake_create,
    )

    query_rewriter = FakeQueryRewriter()
    rag_service = FakeRagService(
        create_rag_response(knowledge_base_id)
    )
    session = FakeSession()

    service = ConversationMessageService(
        query_rewriter=query_rewriter,
        rag_service=rag_service,
        history_limit=10,
    )

    user_message, assistant_message = service.send(
        session,
        knowledge_base_id,
        conversation_id,
        MessageCreate(
            content="  它有什么作用？  ",
            retrieval_limit=8,
            min_score=0.4,
        ),
    )

    assert query_rewriter.question == "它有什么作用？"
    assert query_rewriter.history == history

    assert rag_service.knowledge_base_id == knowledge_base_id
    assert rag_service.request.question == "Milvus 有什么作用？"
    assert rag_service.request.retrieval_limit == 8
    assert rag_service.request.min_score == 0.4

    assert len(created_messages) == 2

    assert user_message.role == MessageRole.USER
    assert user_message.content == "它有什么作用？"
    assert user_message.sources is None

    assert assistant_message.role == MessageRole.ASSISTANT
    assert assistant_message.content == (
        "Milvus 用于保存和检索向量。[1]"
    )
    assert assistant_message.sources is not None
    assert assistant_message.sources[0]["reference"] == 1
    assert assistant_message.sources[0]["original_filename"] == (
        "milvus.txt"
    )

    assert conversation.title == "它有什么作用？"
    assert conversation.updated_at is not None
    assert session.committed is True
    assert session.rolled_back is False
    assert session.refreshed == [
        user_message,
        assistant_message,
    ]


def test_send_rolls_back_when_rag_fails(monkeypatch):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    conversation = SimpleNamespace(
        title="Existing conversation",
        updated_at=None,
    )

    monkeypatch.setattr(
        ConversationService,
        "get",
        lambda session, knowledge_base_id, conversation_id: (
            conversation
        ),
    )
    monkeypatch.setattr(
        MessageRepository,
        "list_recent",
        lambda session, conversation_id, limit: [],
    )

    class FailingRagService:
        def answer(self, session, knowledge_base_id, request):
            raise RuntimeError("RAG unavailable")

    session = FakeSession()
    service = ConversationMessageService(
        query_rewriter=FakeQueryRewriter(),
        rag_service=FailingRagService(),
    )

    with pytest.raises(
        RuntimeError,
        match="RAG unavailable",
    ):
        service.send(
            session,
            knowledge_base_id,
            conversation_id,
            MessageCreate(content="测试问题"),
        )

    assert session.committed is False
    assert session.rolled_back is True


def test_create_title_truncates_long_content():
    content = "问" * 100

    title = ConversationMessageService._create_title(
        content
    )

    assert len(title) == 60
    assert title == ("问" * 59) + "…"


def test_reject_invalid_history_limit():
    with pytest.raises(
        ValueError,
        match="History limit",
    ):
        ConversationMessageService(
            query_rewriter=object(),
            rag_service=object(),
            history_limit=0,
        )


class FakeStreamingRagService:
    def __init__(self, citations, chunks) -> None:
        self.citations = citations
        self.chunks = chunks

    def stream_answer(self, session, knowledge_base_id, request):
        return self.citations, iter(self.chunks)


def test_stream_saves_complete_assistant_message(monkeypatch):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()
    now = datetime.now(UTC)
    conversation = SimpleNamespace(
        title=None,
        updated_at=None,
    )
    citation = create_rag_response(
        knowledge_base_id
    ).citations[0]
    created_messages: list[Message] = []

    monkeypatch.setattr(
        ConversationService,
        "get",
        lambda *args: conversation,
    )
    monkeypatch.setattr(
        MessageRepository,
        "list_recent",
        lambda *args, **kwargs: [],
    )

    def fake_create(
        session,
        conversation_id,
        role,
        content,
        sources=None,
    ):
        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
            created_at=now,
            updated_at=now,
        )
        created_messages.append(message)
        return message

    monkeypatch.setattr(MessageRepository, "create", fake_create)
    session = FakeSession()
    service = ConversationMessageService(
        query_rewriter=FakeQueryRewriter(),
        rag_service=FakeStreamingRagService(
            [citation],
            ["Milvus ", "用于向量检索。[1]"],
        ),
    )

    events = list(
        service.stream(
            session,
            knowledge_base_id,
            conversation_id,
            MessageCreate(content="它有什么作用？"),
        )
    )

    assert [event for event, _ in events] == [
        StreamEventType.USER_MESSAGE,
        StreamEventType.CITATIONS,
        StreamEventType.TOKEN,
        StreamEventType.TOKEN,
        StreamEventType.DONE,
    ]
    assert len(created_messages) == 2
    assert created_messages[1].content == (
        "Milvus 用于向量检索。[1]"
    )
    assert created_messages[1].sources[0]["reference"] == 1
    assert session.rolled_back is False


def test_stream_keeps_user_message_when_generation_fails(monkeypatch):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()
    now = datetime.now(UTC)
    conversation = SimpleNamespace(title="测试", updated_at=None)
    created_messages: list[Message] = []

    monkeypatch.setattr(
        ConversationService,
        "get",
        lambda *args: conversation,
    )
    monkeypatch.setattr(
        MessageRepository,
        "list_recent",
        lambda *args, **kwargs: [],
    )

    def fake_create(session, conversation_id, role, content, sources=None):
        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
            created_at=now,
            updated_at=now,
        )
        created_messages.append(message)
        return message

    def failing_chunks():
        yield "部分回答"
        raise RuntimeError("stream interrupted")

    monkeypatch.setattr(MessageRepository, "create", fake_create)
    session = FakeSession()
    service = ConversationMessageService(
        query_rewriter=FakeQueryRewriter(),
        rag_service=FakeStreamingRagService([], failing_chunks()),
    )

    events = list(
        service.stream(
            session,
            knowledge_base_id,
            conversation_id,
            MessageCreate(content="测试问题"),
        )
    )

    assert [event for event, _ in events][-1] == StreamEventType.ERROR
    assert events[-1][1].detail == "stream interrupted"
    assert len(created_messages) == 1
    assert created_messages[0].role == MessageRole.USER
    assert session.rolled_back is True
