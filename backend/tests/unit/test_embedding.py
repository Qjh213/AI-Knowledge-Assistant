from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import EmbeddingServiceError
from app.services.document_chunker import TextChunk
from app.services.embedding import EmbeddingService


class FakeEmbeddingsAPI:
    def __init__(
        self,
        dimension: int = 3,
        fail: bool = False,
        omit_last: bool = False,
    ) -> None:
        self.dimension = dimension
        self.fail = fail
        self.omit_last = omit_last
        self.calls: list[dict[str, Any]] = []

    def create(
        self,
        *,
        model: str,
        input: list[str],
        encoding_format: str,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "model": model,
                "input": list(input),
                "encoding_format": encoding_format,
            }
        )

        if self.fail:
            raise RuntimeError("remote API unavailable")

        data = [
            SimpleNamespace(
                index=index,
                embedding=[float(len(text))] * self.dimension,
            )
            for index, text in enumerate(input)
        ]

        if self.omit_last and data:
            data = data[:-1]

        return SimpleNamespace(
            data=list(reversed(data)),
        )


class FakeOpenAIClient:
    def __init__(
        self,
        embeddings_api: FakeEmbeddingsAPI,
    ) -> None:
        self.embeddings = embeddings_api


def make_service(
    embeddings_api: FakeEmbeddingsAPI,
    *,
    dimension: int = 3,
    batch_size: int = 2,
) -> EmbeddingService:
    return EmbeddingService(
        client=FakeOpenAIClient(embeddings_api),
        model="BAAI/bge-m3",
        dimension=dimension,
        batch_size=batch_size,
    )


def test_embed_texts_in_batches_and_restore_order() -> None:
    embeddings_api = FakeEmbeddingsAPI(dimension=3)
    service = make_service(
        embeddings_api,
        dimension=3,
        batch_size=2,
    )

    embeddings = service.embed_texts(
        ["a", "bb", "ccc", "dddd", "eeeee"]
    )

    assert len(embeddings_api.calls) == 3
    assert [
        len(call["input"])
        for call in embeddings_api.calls
    ] == [2, 2, 1]
    assert all(
        call["model"] == "BAAI/bge-m3"
        for call in embeddings_api.calls
    )
    assert all(
        call["encoding_format"] == "float"
        for call in embeddings_api.calls
    )

    assert embeddings == [
        [1.0, 1.0, 1.0],
        [2.0, 2.0, 2.0],
        [3.0, 3.0, 3.0],
        [4.0, 4.0, 4.0],
        [5.0, 5.0, 5.0],
    ]


def test_embed_chunks_preserves_chunk_relationship() -> None:
    embeddings_api = FakeEmbeddingsAPI(dimension=3)
    service = make_service(embeddings_api)

    chunks = [
        TextChunk(
            text="first",
            chunk_index=0,
            page_number=1,
            token_count=1,
            metadata={"page": 1},
        ),
        TextChunk(
            text="second",
            chunk_index=1,
            page_number=2,
            token_count=1,
            metadata={"page": 2},
        ),
    ]

    embedded = service.embed_chunks(chunks)

    assert len(embedded) == 2
    assert embedded[0].chunk is chunks[0]
    assert embedded[1].chunk is chunks[1]
    assert embedded[0].embedding == [5.0, 5.0, 5.0]
    assert embedded[1].embedding == [6.0, 6.0, 6.0]


@pytest.mark.parametrize(
    "texts",
    [
        [],
        [""],
        ["   "],
    ],
)
def test_reject_empty_embedding_input(
    texts: list[str],
) -> None:
    service = make_service(FakeEmbeddingsAPI())

    with pytest.raises(EmbeddingServiceError):
        service.embed_texts(texts)


def test_reject_dimension_mismatch() -> None:
    embeddings_api = FakeEmbeddingsAPI(dimension=2)
    service = make_service(
        embeddings_api,
        dimension=3,
    )

    with pytest.raises(
        EmbeddingServiceError,
        match="dimension mismatch",
    ):
        service.embed_texts(["text"])


def test_reject_response_count_mismatch() -> None:
    embeddings_api = FakeEmbeddingsAPI(
        dimension=3,
        omit_last=True,
    )
    service = make_service(embeddings_api)

    with pytest.raises(
        EmbeddingServiceError,
        match="response count",
    ):
        service.embed_texts(["first", "second"])


def test_wrap_remote_api_error() -> None:
    embeddings_api = FakeEmbeddingsAPI(
        dimension=3,
        fail=True,
    )
    service = make_service(embeddings_api)

    with pytest.raises(
        EmbeddingServiceError,
        match="remote API unavailable",
    ):
        service.embed_texts(["text"])


@pytest.mark.parametrize(
    ("dimension", "batch_size"),
    [
        (0, 2),
        (3, 0),
    ],
)
def test_reject_invalid_embedding_configuration(
    dimension: int,
    batch_size: int,
) -> None:
    with pytest.raises(EmbeddingServiceError):
        make_service(
            FakeEmbeddingsAPI(),
            dimension=dimension,
            batch_size=batch_size,
        )