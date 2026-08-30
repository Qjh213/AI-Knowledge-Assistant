from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.api.routes.conversations import (
    get_conversation_message_service,
)
from app.database.models import MessageRole
from app.main import app
from app.schemas.message import MessageResponse
from app.schemas.streaming import (
    StreamCitationsData,
    StreamDoneData,
    StreamEventType,
    StreamTokenData,
    StreamUserMessageData,
)


client = TestClient(app)


class FakeConversationMessageService:
    def __init__(self) -> None:
        self.send_arguments = None
        self.list_arguments = None
        self.stream_arguments = None

    def send(
        self,
        session,
        knowledge_base_id,
        conversation_id,
        data,
    ):
        self.send_arguments = (
            session,
            knowledge_base_id,
            conversation_id,
            data,
        )
        now = datetime.now(UTC)

        user_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=data.content,
            sources=None,
            created_at=now,
            updated_at=now,
        )
        assistant_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="Milvus 用于向量检索。[1]",
            sources=[
                {
                    "reference": 1,
                    "chunk_id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "original_filename": "milvus.txt",
                    "page_number": 1,
                    "content": "Milvus 用于向量检索。",
                    "score": 0.91,
                }
            ],
            created_at=now,
            updated_at=now,
        )

        return user_message, assistant_message

    def stream(
        self,
        session,
        knowledge_base_id,
        conversation_id,
        data,
    ):
        self.stream_arguments = (
            session,
            knowledge_base_id,
            conversation_id,
            data,
        )
        now = datetime.now(UTC)
        user_message = MessageResponse(
            id=uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=data.content,
            sources=None,
            created_at=now,
            updated_at=now,
        )
        assistant_message = MessageResponse(
            id=uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="Milvus 是向量数据库。[1]",
            sources=None,
            created_at=now,
            updated_at=now,
        )

        yield (
            StreamEventType.USER_MESSAGE,
            StreamUserMessageData(message=user_message),
        )
        yield (
            StreamEventType.CITATIONS,
            StreamCitationsData(citations=[]),
        )
        yield (
            StreamEventType.TOKEN,
            StreamTokenData(content="Milvus 是"),
        )
        yield (
            StreamEventType.TOKEN,
            StreamTokenData(content="向量数据库。[1]"),
        )
        yield (
            StreamEventType.DONE,
            StreamDoneData(message=assistant_message),
        )

    def list(
        self,
        session,
        knowledge_base_id,
        conversation_id,
        offset=0,
        limit=50,
    ):
        self.list_arguments = (
            session,
            knowledge_base_id,
            conversation_id,
            offset,
            limit,
        )
        now = datetime.now(UTC)
        item = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content="Milvus 是什么？",
            sources=None,
            created_at=now,
            updated_at=now,
        )

        return [item], 1


@pytest.fixture
def fake_dependencies():
    fake_session = object()
    fake_service = FakeConversationMessageService()

    def override_db():
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[
        get_conversation_message_service
    ] = lambda: fake_service

    try:
        yield fake_session, fake_service
    finally:
        app.dependency_overrides.clear()


def test_send_conversation_message(fake_dependencies):
    fake_session, fake_service = fake_dependencies
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "  它有什么作用？  ",
            "retrieval_limit": 8,
            "min_score": 0.4,
        },
    )

    assert response.status_code == 201

    body = response.json()
    assert body["conversation_id"] == str(conversation_id)
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "它有什么作用？"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["sources"][0][
        "original_filename"
    ] == "milvus.txt"

    arguments = fake_service.send_arguments
    assert arguments[0] is fake_session
    assert arguments[1] == knowledge_base_id
    assert arguments[2] == conversation_id
    assert arguments[3].content == "它有什么作用？"
    assert arguments[3].retrieval_limit == 8
    assert arguments[3].min_score == 0.4


def test_list_conversation_messages(fake_dependencies):
    fake_session, fake_service = fake_dependencies
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages",
        params={"offset": 2, "limit": 25},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 2
    assert body["limit"] == 25
    assert body["items"][0]["content"] == "Milvus 是什么？"

    assert fake_service.list_arguments == (
        fake_session,
        knowledge_base_id,
        conversation_id,
        2,
        25,
    )


def test_stream_conversation_message(fake_dependencies):
    fake_session, fake_service = fake_dependencies
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages/stream",
        json={"content": "  Milvus 是什么？  "},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.count("event: token") == 2
    assert "event: user_message" in response.text
    assert "event: citations" in response.text
    assert "event: done" in response.text
    assert "Milvus 是" in response.text

    arguments = fake_service.stream_arguments
    assert arguments[0] is fake_session
    assert arguments[1] == knowledge_base_id
    assert arguments[2] == conversation_id
    assert arguments[3].content == "Milvus 是什么？"


def test_reject_empty_stream_message(fake_dependencies):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages/stream",
        json={"content": "   "},
    )

    assert response.status_code == 422


def test_reject_empty_conversation_message(fake_dependencies):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages",
        json={"content": "   "},
    )

    assert response.status_code == 422


def test_reject_invalid_message_pagination(fake_dependencies):
    knowledge_base_id = uuid4()
    conversation_id = uuid4()

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}"
        f"/conversations/{conversation_id}/messages",
        params={"offset": -1, "limit": 101},
    )

    assert response.status_code == 422
