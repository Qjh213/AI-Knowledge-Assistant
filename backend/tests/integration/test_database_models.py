from uuid import UUID, uuid4

import pytest

from app.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    KnowledgeBase,
)
from app.database.session import SessionLocal


@pytest.mark.integration
def test_document_relationships_and_cascade_delete() -> None:
    knowledge_base_id: UUID | None = None
    document_id: UUID | None = None
    chunk_id: UUID | None = None

    unique_value = uuid4().hex

    with SessionLocal() as session:
        try:
            knowledge_base = KnowledgeBase(
                name=f"test-knowledge-base-{unique_value}",
                description="Temporary integration test knowledge base",
            )

            document = Document(
                knowledge_base=knowledge_base,
                original_filename="test.txt",
                stored_filename=f"{unique_value}.txt",
                file_path=f"data/documents/{unique_value}.txt",
                mime_type="text/plain",
                file_size=10,
                checksum=unique_value * 2,
            )

            chunk = DocumentChunk(
                document=document,
                chunk_index=0,
                content="This is a database integration test.",
                page_number=1,
                token_count=8,
                extra_metadata={"source": "integration-test"},
            )

            session.add(knowledge_base)
            session.commit()

            knowledge_base_id = knowledge_base.id
            document_id = document.id
            chunk_id = chunk.id

            assert document.status == DocumentStatus.PENDING
            assert document.knowledge_base_id == knowledge_base.id
            assert chunk.document_id == document.id
            assert chunk.extra_metadata == {
                "source": "integration-test",
            }

            session.delete(knowledge_base)
            session.commit()

            assert session.get(KnowledgeBase, knowledge_base_id) is None
            assert session.get(Document, document_id) is None
            assert session.get(DocumentChunk, chunk_id) is None

        finally:
            if knowledge_base_id is not None:
                remaining = session.get(KnowledgeBase, knowledge_base_id)

                if remaining is not None:
                    session.delete(remaining)
                    session.commit()