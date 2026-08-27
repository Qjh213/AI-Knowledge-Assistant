from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
)
from app.database.session import SessionLocal
from app.main import app
from app.services.document_chunker import TextChunk
from app.services.embedding import EmbeddedChunk
from app.services.vector_store import VectorStoreService


pytestmark = pytest.mark.integration
client = TestClient(app)


def test_delete_knowledge_base_cleans_all_document_data():
    unique_value = uuid4().hex
    stored_filename = f"{unique_value}.txt"
    stored_path = (
        settings.document_storage_path / stored_filename
    ).resolve()

    knowledge_base_id: UUID | None = None
    document_id: UUID | None = None
    vector_store = VectorStoreService()

    try:
        stored_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        stored_path.write_text(
            "Knowledge base cleanup integration test.",
            encoding="utf-8",
        )

        with SessionLocal() as session:
            knowledge_base = KnowledgeBase(
                name=f"cleanup-test-{unique_value}",
                description="Temporary cleanup test",
            )
            document = Document(
                knowledge_base=knowledge_base,
                original_filename="cleanup.txt",
                stored_filename=stored_filename,
                file_path=stored_filename,
                mime_type="text/plain",
                file_size=stored_path.stat().st_size,
                checksum=unique_value * 2,
            )
            chunk = DocumentChunk(
                document=document,
                chunk_index=0,
                content="Knowledge base cleanup integration test.",
                page_number=None,
                token_count=7,
                extra_metadata={"source": "cleanup-test"},
            )

            session.add(knowledge_base)
            session.commit()

            knowledge_base_id = knowledge_base.id
            document_id = document.id
            chunk_id = chunk.id

        text_chunk = TextChunk(
            text="Knowledge base cleanup integration test.",
            chunk_index=0,
            page_number=None,
            token_count=7,
            metadata={"source": "cleanup-test"},
        )
        vector = [0.0] * settings.embedding_dimension
        vector[0] = 1.0

        vector_store.insert_chunks(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_ids=[chunk_id],
            chunks=[
                EmbeddedChunk(
                    chunk=text_chunk,
                    embedding=vector,
                )
            ],
        )

        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base_id}"
        )

        assert response.status_code == 204
        assert not stored_path.exists()

        with SessionLocal() as session:
            assert (
                session.get(
                    KnowledgeBase,
                    knowledge_base_id,
                )
                is None
            )
            assert session.get(Document, document_id) is None
            assert session.get(DocumentChunk, chunk_id) is None

        remaining_vectors = vector_store.client.query(
            collection_name=vector_store.collection_name,
            filter=(
                f'knowledge_base_id == "{knowledge_base_id}"'
            ),
            output_fields=["id"],
        )

        assert remaining_vectors == []

    finally:
        if knowledge_base_id is not None:
            try:
                vector_store.delete_knowledge_base(
                    knowledge_base_id
                )
            except Exception:
                pass

            with SessionLocal() as session:
                remaining = session.get(
                    KnowledgeBase,
                    knowledge_base_id,
                )

                if remaining is not None:
                    session.delete(remaining)
                    session.commit()

        Path(stored_path).unlink(missing_ok=True)