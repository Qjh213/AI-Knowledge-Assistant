from types import SimpleNamespace

import pytest

from app.core.exceptions import ChatServiceError
from app.services.chat import ChatService


class FakeCompletionsAPI:
    def __init__(
        self,
        content: str | None = "知识库回答",
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.arguments = None

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error

        self.arguments = kwargs

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=self.content
                    )
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(
        self,
        content: str | None = "知识库回答",
        error: Exception | None = None,
    ) -> None:
        self.completions = FakeCompletionsAPI(
            content=content,
            error=error,
        )
        self.chat = SimpleNamespace(
            completions=self.completions
        )


def create_service(
    client: FakeOpenAIClient | None = None,
    **kwargs,
) -> ChatService:
    return ChatService(
        client=client or FakeOpenAIClient(),
        model=kwargs.get("model", "deepseek-v4-flash"),
        temperature=kwargs.get("temperature", 0.2),
        max_tokens=kwargs.get("max_tokens", 512),
    )


def test_generate_chat_answer():
    client = FakeOpenAIClient(
        content="  根据知识库，Milvus 用于向量检索。  "
    )
    service = create_service(client)

    answer = service.generate(
        system_prompt="  你是知识库助手。  ",
        user_prompt="  Milvus 有什么作用？  ",
    )

    assert answer == "根据知识库，Milvus 用于向量检索。"

    arguments = client.completions.arguments
    assert arguments["model"] == "deepseek-v4-flash"
    assert arguments["temperature"] == 0.2
    assert arguments["max_tokens"] == 512
    assert arguments["messages"] == [
        {
            "role": "system",
            "content": "你是知识库助手。",
        },
        {
            "role": "user",
            "content": "Milvus 有什么作用？",
        },
    ]


@pytest.mark.parametrize(
    ("system_prompt", "user_prompt", "message"),
    [
        ("   ", "question", "system prompt"),
        ("system", "   ", "user prompt"),
    ],
)
def test_reject_empty_prompts(
    system_prompt,
    user_prompt,
    message,
):
    service = create_service()

    with pytest.raises(
        ChatServiceError,
        match=message,
    ):
        service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


def test_wrap_remote_api_error():
    service = create_service(
        FakeOpenAIClient(
            error=RuntimeError("DeepSeek unavailable")
        )
    )

    with pytest.raises(
        ChatServiceError,
        match="DeepSeek unavailable",
    ):
        service.generate(
            system_prompt="system",
            user_prompt="question",
        )


@pytest.mark.parametrize("content", [None, "", "   "])
def test_reject_empty_model_response(content):
    service = create_service(
        FakeOpenAIClient(content=content)
    )

    with pytest.raises(
        ChatServiceError,
        match="empty response",
    ):
        service.generate(
            system_prompt="system",
            user_prompt="question",
        )


@pytest.mark.parametrize(
    "temperature",
    [-0.1, 2.1],
)
def test_reject_invalid_temperature(temperature):
    with pytest.raises(
        ChatServiceError,
        match="temperature",
    ):
        create_service(temperature=temperature)


def test_reject_invalid_max_tokens():
    with pytest.raises(
        ChatServiceError,
        match="max tokens",
    ):
        create_service(max_tokens=0)


def test_reject_empty_model_name():
    with pytest.raises(
        ChatServiceError,
        match="chat model",
    ):
        create_service(model=" ")