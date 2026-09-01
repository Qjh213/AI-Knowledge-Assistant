from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.database.models import Conversation
from app.main import app
from app.services.conversation import ConversationService


client = TestClient(app)


def test_list_recent_conversations(monkeypatch) -> None:
    knowledge_base_id = uuid4()
    conversation = Conversation(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        title="向量数据库问答",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    monkeypatch.setattr(
        ConversationService,
        "list_recent",
        lambda session, offset=0, limit=20: (
            [(conversation, "技术资料库")],
            1,
        ),
    )
    app.dependency_overrides[get_db] = lambda: iter((object(),))

    try:
        response = client.get("/api/v1/conversations/recent")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["knowledge_base_name"] == "技术资料库"
    assert response.json()["items"][0]["title"] == "向量数据库问答"
