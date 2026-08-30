import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.schemas.streaming import StreamEventType


def encode_sse(
    event: StreamEventType,
    data: BaseModel | Mapping[str, Any],
) -> str:
    if isinstance(data, BaseModel):
        payload = data.model_dump(mode="json")
    else:
        payload = dict(data)

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"event: {event.value}\ndata: {serialized}\n\n"

