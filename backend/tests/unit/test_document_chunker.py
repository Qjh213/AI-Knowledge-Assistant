import pytest

from app.core.exceptions import DocumentChunkingError
from app.services.document_chunker import DocumentChunker
from app.services.document_parser import (
    ParsedDocument,
    ParsedSection,
)


def make_parsed_document(
    sections: tuple[ParsedSection, ...],
) -> ParsedDocument:
    return ParsedDocument(
        sections=sections,
        character_count=sum(
            len(section.text)
            for section in sections
        ),
    )


def test_split_document_into_ordered_chunks() -> None:
    text = "这是第一段知识库内容。" * 50
    document = make_parsed_document(
        (
            ParsedSection(
                text=text,
                page_number=1,
                metadata={"extension": ".pdf", "page": 1},
            ),
        )
    )
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=20,
    )

    chunks = chunker.split(document)

    assert len(chunks) > 1
    assert [
        chunk.chunk_index for chunk in chunks
    ] == list(range(len(chunks)))

    for chunk in chunks:
        assert chunk.text
        assert len(chunk.text) <= 100
        assert chunk.page_number == 1
        assert chunk.token_count > 0
        assert chunk.metadata["extension"] == ".pdf"
        assert chunk.metadata["section_index"] == 0


def test_preserve_section_page_numbers() -> None:
    document = make_parsed_document(
        (
            ParsedSection(
                text="第一页内容",
                page_number=1,
                metadata={"page": 1},
            ),
            ParsedSection(
                text="第二页内容",
                page_number=2,
                metadata={"page": 2},
            ),
        )
    )
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=10,
    )

    chunks = chunker.split(document)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].metadata["section_index"] == 0
    assert chunks[1].page_number == 2
    assert chunks[1].metadata["section_index"] == 1


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [
        (0, 0),
        (100, -1),
        (100, 100),
    ],
)
def test_reject_invalid_chunk_configuration(
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    with pytest.raises(DocumentChunkingError):
        DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


def test_reject_document_without_sections() -> None:
    document = ParsedDocument(
        sections=(),
        character_count=0,
    )
    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=10,
    )

    with pytest.raises(DocumentChunkingError):
        chunker.split(document)
