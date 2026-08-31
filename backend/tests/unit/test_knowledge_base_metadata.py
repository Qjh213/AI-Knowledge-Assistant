from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.database.models import DocumentParser, DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_base_metadata import KnowledgeBaseMetadataService


def document(
    name: str,
    status: DocumentStatus,
    *,
    parser: DocumentParser = DocumentParser.LOCAL,
    chunks: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        original_filename=name,
        status=status,
        parser=parser,
        chunk_count=chunks,
    )


@pytest.fixture
def metadata_documents() -> list[SimpleNamespace]:
    return [
        document(
            "guide.pdf",
            DocumentStatus.COMPLETED,
            parser=DocumentParser.MINERU,
            chunks=12,
        ),
        document("notes.md", DocumentStatus.COMPLETED, chunks=3),
        document("broken.docx", DocumentStatus.FAILED),
    ]


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
    metadata_documents: list[SimpleNamespace],
) -> KnowledgeBaseMetadataService:
    monkeypatch.setattr(
        KnowledgeBaseService,
        "get",
        lambda session, knowledge_base_id: SimpleNamespace(id=knowledge_base_id),
    )
    monkeypatch.setattr(
        DocumentRepository,
        "list_all_for_knowledge_base",
        lambda session, knowledge_base_id: metadata_documents,
    )
    return KnowledgeBaseMetadataService()


def test_answer_document_inventory(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "当前知识库中有什么文件？")

    assert answer is not None
    assert "共有 3 个文件" in answer
    assert "guide.pdf（处理完成，MinerU 解析，12 个分块）" in answer
    assert "notes.md（处理完成，本地解析，3 个分块）" in answer
    assert "broken.docx（处理失败，本地解析，0 个分块）" in answer


def test_filter_failed_documents(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "哪些文件处理失败了？")

    assert answer is not None
    assert "共有 1 个处理失败的文件" in answer
    assert "broken.docx" in answer
    assert "guide.pdf" not in answer


def test_filter_pdf_documents(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "列出 PDF 文件")

    assert answer is not None
    assert "共有 1 个PDF 文件" in answer
    assert "guide.pdf" in answer
    assert "notes.md" not in answer


def test_ignore_content_question(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "这个文件讲了什么？")

    assert answer is None


def test_filter_mineru_documents(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "哪些文件使用 MinerU 解析？")

    assert answer is not None
    assert "共有 1 个使用 MinerU 解析的文件" in answer
    assert "guide.pdf" in answer
    assert "notes.md" not in answer


def test_filter_local_documents(service: KnowledgeBaseMetadataService) -> None:
    answer = service.answer(object(), uuid4(), "列出本地解析的文件")

    assert answer is not None
    assert "共有 2 个使用本地解析的文件" in answer
    assert "notes.md" in answer
    assert "broken.docx" in answer
    assert "guide.pdf" not in answer
