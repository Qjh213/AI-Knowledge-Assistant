from collections.abc import Sequence
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import EmbeddingServiceError
from app.services.document_chunker import TextChunk


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: TextChunk
    embedding: list[float]


class EmbeddingService:
    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        dimension: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.client = client or OpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
        )
        self.model = model or settings.embedding_model
        self.dimension = (
            dimension
            if dimension is not None
            else settings.embedding_dimension
        )
        self.batch_size = (
            batch_size
            if batch_size is not None
            else settings.embedding_batch_size
        )

        if self.dimension <= 0:
            raise EmbeddingServiceError(
                "embedding dimension must be greater than zero"
            )

        if self.batch_size <= 0:
            raise EmbeddingServiceError(
                "batch size must be greater than zero"
            )

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        if not texts:
            raise EmbeddingServiceError(
                "at least one text is required"
            )

        normalized_texts = [
            text.strip()
            for text in texts
        ]

        if any(not text for text in normalized_texts):
            raise EmbeddingServiceError(
                "embedding input cannot be empty"
            )

        embeddings: list[list[float]] = []

        try:
            for start in range(
                0,
                len(normalized_texts),
                self.batch_size,
            ):
                batch = normalized_texts[
                    start : start + self.batch_size
                ]

                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                )

                response_items = sorted(
                    response.data,
                    key=lambda item: item.index,
                )

                if len(response_items) != len(batch):
                    raise EmbeddingServiceError(
                        "embedding response count does not match input count"
                    )

                for item in response_items:
                    vector = list(item.embedding)

                    if len(vector) != self.dimension:
                        raise EmbeddingServiceError(
                            "embedding dimension mismatch: "
                            f"expected {self.dimension}, "
                            f"received {len(vector)}"
                        )

                    embeddings.append(vector)

        except EmbeddingServiceError:
            raise

        except Exception as exc:
            raise EmbeddingServiceError(str(exc)) from exc

        if len(embeddings) != len(normalized_texts):
            raise EmbeddingServiceError(
                "embedding result count does not match input count"
            )

        return embeddings

    def embed_chunks(
        self,
        chunks: Sequence[TextChunk],
    ) -> list[EmbeddedChunk]:
        if not chunks:
            raise EmbeddingServiceError(
                "at least one text chunk is required"
            )

        embeddings = self.embed_texts(
            [chunk.text for chunk in chunks]
        )

        return [
            EmbeddedChunk(
                chunk=chunk,
                embedding=embedding,
            )
            for chunk, embedding in zip(
                chunks,
                embeddings,
                strict=True,
            )
        ]