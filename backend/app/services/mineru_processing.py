from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import DocumentProcessingError
from app.database.models import (
    Document,
    DocumentParser,
    DocumentStatus,
)
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService
from app.services.document_storage import DocumentStorageService
from app.services.mineru import (
    MinerUClient,
    MinerUTaskResult,
)

from app.repositories.document_chunk import (
    DocumentChunkRepository,
)
from app.services.document_parser import (
    ParsedDocument,
    ParsedSection,
)
from app.services.document_processing import (
    DocumentProcessingService,
)


class MinerUDocumentProcessingService:
    """Submit stored documents to the MinerU batch API."""

    def __init__(
        self,
        *,
        mineru_client: MinerUClient | None = None,
        document_service: DocumentService | None = None,
        storage_service: DocumentStorageService | None = None,
        processing_service: DocumentProcessingService | None = None,
    ) -> None:
        self.mineru_client = mineru_client or MinerUClient()
        self.document_service = document_service or DocumentService()
        self.storage_service = (
            storage_service or DocumentStorageService()
        )
        self.processing_service = processing_service

    def submit(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document:
        document = self.document_service.get(
            session,
            knowledge_base_id,
            document_id,
        )

        # 防止用户重复点击时重复提交相同任务。
        if (
            document.status == DocumentStatus.PROCESSING
            and document.parser == DocumentParser.MINERU
            and document.external_task_id
        ):
            return document

        # 已经处理完成的文档无需再次提交。
        if document.status == DocumentStatus.COMPLETED:
            return document

        try:
            file_path = self._resolve_file_path(
                document.file_path
            )

            upload_task = (
                self.mineru_client.request_upload_url(
                    document.original_filename
                )
            )

            self.mineru_client.upload_file(
                upload_task.upload_url,
                file_path,
            )

            DocumentRepository.update_processing_state(
                session,
                document,
                DocumentStatus.PROCESSING,
                chunk_count=0,
                error_message=None,
                parser=DocumentParser.MINERU,
                external_task_id=upload_task.batch_id,
                processing_progress=0,
            )

            session.commit()
            session.refresh(document)

            return document

        except Exception as exc:
            session.rollback()
            detail = str(exc)

            try:
                failed_document = DocumentRepository.get(
                    session,
                    document_id,
                )

                if failed_document is not None:
                    DocumentRepository.update_processing_state(
                        session,
                        failed_document,
                        DocumentStatus.FAILED,
                        chunk_count=0,
                        error_message=detail,
                        parser=DocumentParser.MINERU,
                        processing_progress=0,
                    )
                    session.commit()
            except Exception:
                session.rollback()

            raise DocumentProcessingError(
                document_id,
                detail,
            ) from exc

    def check_status(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> MinerUTaskResult:
        document = self.document_service.get(
            session,
            knowledge_base_id,
            document_id,
        )

        if (
            document.parser != DocumentParser.MINERU
            or not document.external_task_id
        ):
            raise DocumentProcessingError(
                document_id,
                "Document does not have a MinerU task",
            )

        try:
            task_result = (
                self.mineru_client.get_batch_result(
                    document.external_task_id,
                    file_name=document.original_filename,
                )
            )

            if task_result.state == "failed":
                DocumentRepository.update_processing_state(
                    session,
                    document,
                    DocumentStatus.FAILED,
                    chunk_count=0,
                    error_message=(
                        task_result.error_message
                        or "MinerU document parsing failed"
                    ),
                    parser=DocumentParser.MINERU,
                    processing_progress=0,
                )
            else:
                # 即使 MinerU 已经解析完成，在完成文本切分、
                # 嵌入和向量写入前，文档仍保持 processing。
                DocumentRepository.update_processing_state(
                    session,
                    document,
                    DocumentStatus.PROCESSING,
                    error_message=None,
                    parser=DocumentParser.MINERU,
                    processing_progress=task_result.progress,
                )

            session.commit()
            session.refresh(document)

            return task_result

        except DocumentProcessingError:
            raise

        except Exception as exc:
            session.rollback()

            # 查询失败可能只是临时网络问题，因此这里不把
            # 文档永久标记为 failed。
            raise DocumentProcessingError(
                document_id,
                str(exc),
            ) from exc

    def finalize(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document:
        document = self.document_service.get(
            session,
            knowledge_base_id,
            document_id,
        )

        if (
            document.parser != DocumentParser.MINERU
            or not document.external_task_id
        ):
            raise DocumentProcessingError(
                document_id,
                "Document does not have a MinerU task",
            )

        task_result = self.check_status(
            session,
            knowledge_base_id,
            document_id,
        )

        # MinerU 还没有完成时，只返回最新状态。
        if task_result.state in {
            "pending",
            "running",
            "converting",
        }:
            return document

        # MinerU 已经报告失败，check_status() 已经把
        # 数据库中的文档状态更新为 failed。
        if task_result.state == "failed":
            return document

        if not task_result.full_zip_url:
            raise DocumentProcessingError(
                document_id,
                "Completed MinerU task did not provide a result ZIP",
            )

        processing_service = self.processing_service

        try:
            processing_service = (
                processing_service
                or DocumentProcessingService()
            )
            markdown = self.mineru_client.download_markdown(
                task_result.full_zip_url
            )

            parsed_document = ParsedDocument(
                sections=(
                    ParsedSection(
                        text=markdown,
                        page_number=None,
                        metadata={
                            "parser": "mineru",
                            "source": "full.md",
                            "batch_id": (
                                document.external_task_id
                            ),
                            "original_filename": (
                                document.original_filename
                            ),
                        },
                    ),
                ),
                character_count=len(markdown),
            )

            return (
                processing_service.index_parsed_document(
                    session,
                    document,
                    parsed_document,
                )
            )

        except DocumentProcessingError:
            raise

        except Exception as exc:
            session.rollback()

            # Milvus 或 PostgreSQL 可能已经写入了一部分，
            # 出错时尽力清理，避免留下半成品。
            if processing_service is not None:
                try:
                    processing_service.vector_store.delete_document(
                        document_id
                    )
                except Exception:
                    pass

            try:
                failed_document = DocumentRepository.get(
                    session,
                    document_id,
                )

                if failed_document is not None:
                    DocumentChunkRepository.delete_for_document(
                        session,
                        document_id,
                    )

                    DocumentRepository.update_processing_state(
                        session,
                        failed_document,
                        DocumentStatus.FAILED,
                        chunk_count=0,
                        error_message=str(exc),
                        parser=DocumentParser.MINERU,
                        processing_progress=0,
                    )
                    session.commit()
            except Exception:
                session.rollback()

            raise DocumentProcessingError(
                document_id,
                str(exc),
            ) from exc

    def _resolve_file_path(
        self,
        stored_file_path: str,
    ) -> Path:
        storage_root = self.storage_service.storage_path.resolve()
        file_path = (
            storage_root / stored_file_path
        ).resolve()

        if (
            file_path != storage_root
            and storage_root not in file_path.parents
        ):
            raise ValueError(
                "Invalid document storage path"
            )

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Stored document does not exist: {file_path}"
            )

        return file_path
