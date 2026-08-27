from dataclasses import dataclass
from typing import Any

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.exceptions import DocumentChunkingError
from app.services.document_parser import ParsedDocument


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    chunk_index: int
    page_number: int | None
    token_count: int
    metadata: dict[str, Any]


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.chunk_size = (
            chunk_size
            if chunk_size is not None
            else settings.chunk_size
        )
        self.chunk_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else settings.chunk_overlap
        )

        if self.chunk_size <= 0:
            raise DocumentChunkingError(
                "chunk size must be greater than zero"
            )

        if self.chunk_overlap < 0:
            raise DocumentChunkingError(
                "chunk overlap cannot be negative"
            )

        if self.chunk_overlap >= self.chunk_size:
            raise DocumentChunkingError(
                "chunk overlap must be smaller than chunk size"
            )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            keep_separator=True,
            separators=[
                "\n\n",
                "\n",
                "。",
                "！",
                "？",
                "；",
                ". ",
                "! ",
                "? ",
                "; ",
                " ",
                "",
            ],
        )
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def split(
        self,
        document: ParsedDocument,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        chunk_index = 0

        for section_index, section in enumerate(
            document.sections
        ):
            section_chunks = self.splitter.split_text(
                section.text
            )

            for text in section_chunks:
                cleaned = text.strip()

                if not cleaned:
                    continue

                metadata = {
                    **section.metadata,
                    "section_index": section_index,
                }

                chunks.append(
                    TextChunk(
                        text=cleaned,
                        chunk_index=chunk_index,
                        page_number=section.page_number,
                        token_count=len(
                            self.tokenizer.encode(cleaned)
                        ),
                        metadata=metadata,
                    )
                )
                chunk_index += 1

        if not chunks:
            raise DocumentChunkingError(
                "no text chunks were produced"
            )

        return chunks