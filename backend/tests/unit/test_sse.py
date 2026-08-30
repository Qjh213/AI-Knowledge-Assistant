import json

from app.schemas.streaming import (
    StreamErrorData,
    StreamEventType,
    StreamTokenData,
)
from app.services.sse import encode_sse


def parse_event(value: str) -> tuple[str, dict[str, object]]:
    lines = value.rstrip("\n").splitlines()
    event = lines[0].removeprefix("event: ")
    data = json.loads(lines[1].removeprefix("data: "))
    return event, data


def test_encode_token_event() -> None:
    encoded = encode_sse(
        StreamEventType.TOKEN,
        StreamTokenData(content="你好\n世界"),
    )

    event, data = parse_event(encoded)

    assert event == "token"
    assert data == {"content": "你好\n世界"}
    assert encoded.endswith("\n\n")


def test_encode_error_event_from_model() -> None:
    encoded = encode_sse(
        StreamEventType.ERROR,
        StreamErrorData(detail="模型暂时不可用"),
    )

    event, data = parse_event(encoded)

    assert event == "error"
    assert data == {"detail": "模型暂时不可用"}


def test_encode_event_from_mapping() -> None:
    encoded = encode_sse(
        StreamEventType.CITATIONS,
        {"citations": []},
    )

    event, data = parse_event(encoded)

    assert event == "citations"
    assert data == {"citations": []}
