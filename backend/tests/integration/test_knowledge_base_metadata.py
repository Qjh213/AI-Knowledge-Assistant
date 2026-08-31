from uuid import UUID, uuid4

import pytest

from app.database.models import (
    Document,
    DocumentParser,
    DocumentStatus,
    KnowledgeBase,
)
from app.database.session import SessionLocal
from app.services.knowledge_base_metadata import KnowledgeBaseMetadataService


@pytest.mark.integration
def test_metadata_answer_uses_real_database_documents() -> None:
    knowledge_base_id: UUID | None = None
    unique_value = uuid4().hex

    with SessionLocal() as session:
        try:
            knowledge_base = KnowledgeBase(
                name=f"metadata-test-{unique_value}",
                description="Temporary metadata integration test",
            )
            knowledge_base.documents.extend(
                [
                    Document(
                        original_filename="course.pdf",
                        stored_filename=f"{unique_value}-course.pdf",
                        file_path=f"{unique_value}-course.pdf",
                        mime_type="application/pdf",
                        file_size=100,
                        checksum=unique_value * 2,
                        status=DocumentStatus.COMPLETED,
                        parser=DocumentParser.MINERU,
                        processing_progress=100,
                        chunk_count=8,
                    ),
                    Document(
                        original_filename="notes.md",
                        stored_filename=f"{unique_value}-notes.md",
                        file_path=f"{unique_value}-notes.md",
                        mime_type="text/markdown",
                        file_size=50,
                        checksum=(unique_value[::-1]) * 2,
                        status=DocumentStatus.PENDING,
                        parser=DocumentParser.LOCAL,
                        processing_progress=0,
                        chunk_count=0,
                    ),
                ]
            )
            session.add(knowledge_base)
            session.commit()
            knowledge_base_id = knowledge_base.id

            answer = KnowledgeBaseMetadataService().answer(
                session,
                knowledge_base.id,
                "当前知识库中有哪些文件？",
            )

            assert answer is not None
            assert "共有 2 个文件" in answer
            assert "course.pdf（处理完成，MinerU 解析，8 个分块）" in answer
            assert "notes.md（等待处理，本地解析，0 个分块）" in answer

        finally:
            if knowledge_base_id is not None:
                remaining = session.get(KnowledgeBase, knowledge_base_id)
                if remaining is not None:
                    session.delete(remaining)
                    session.commit()
