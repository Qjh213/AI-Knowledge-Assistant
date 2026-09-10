from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DocumentProcessingError, MinerUResultDownloadError
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

    MAX_MINERU_PAGES = 200
    SPLIT_PAGE_COUNT = 180

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

    def pdf_page_count(self, stored_file_path: str) -> int | None:
        file_path = self._resolve_file_path(stored_file_path)
        if file_path.suffix.casefold() != ".pdf":
            return None
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            raise ValueError("encrypted PDF files are not supported")
        return len(reader.pages)

    def requires_split(self, stored_file_path: str) -> bool:
        page_count = self.pdf_page_count(stored_file_path)
        return page_count is not None and page_count > self.MAX_MINERU_PAGES

    def process_long_pdf(
        self,
        session: Session,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document:
        """Parse an oversized PDF as internal parts while keeping one document."""
        document = self.document_service.get(session, knowledge_base_id, document_id)
        source_path = self._resolve_file_path(document.file_path)
        reader = PdfReader(str(source_path))
        total_pages = len(reader.pages)
        if total_pages <= self.MAX_MINERU_PAGES:
            raise ValueError("PDF does not require splitting")

        processing_service = self.processing_service or DocumentProcessingService()
        markdown_parts: list[str] = []
        ranges = [
            (start, min(start + self.SPLIT_PAGE_COUNT, total_pages))
            for start in range(0, total_pages, self.SPLIT_PAGE_COUNT)
        ]

        try:
            DocumentRepository.mark_processing_started(
                session, document, DocumentParser.MINERU
            )
            document.external_task_id = None
            document.chunk_count = 0
            session.commit()
            session.refresh(document)

            with TemporaryDirectory(prefix="mineru-parts-") as temp_dir:
                for part_number, (start, end) in enumerate(ranges, start=1):
                    part_path = Path(temp_dir) / (
                        f"{source_path.stem}-part-{part_number:03d}-"
                        f"pages-{start + 1:04d}-{end:04d}.pdf"
                    )
                    writer = PdfWriter()
                    for page in reader.pages[start:end]:
                        writer.add_page(page)
                    with part_path.open("wb") as output:
                        writer.write(output)

                    upload_task = self.mineru_client.request_upload_url(part_path.name)
                    self.mineru_client.upload_file(upload_task.upload_url, part_path)
                    document.external_task_id = upload_task.batch_id
                    session.commit()

                    deadline = monotonic() + settings.mineru_timeout_seconds
                    while True:
                        result = self.mineru_client.get_batch_result(
                            upload_task.batch_id,
                            file_name=part_path.name,
                        )
                        if result.state == "failed":
                            raise RuntimeError(
                                result.error_message or f"MinerU part {part_number} failed"
                            )
                        if result.state == "done":
                            if not result.full_zip_url:
                                raise RuntimeError(
                                    f"MinerU part {part_number} did not provide a result ZIP"
                                )
                            markdown = self.mineru_client.download_markdown(
                                result.full_zip_url
                            )
                            markdown_parts.append(
                                f"\n\n<!-- original_pages:{start + 1}-{end} -->\n\n{markdown}"
                            )
                            break
                        if monotonic() >= deadline:
                            raise TimeoutError(f"MinerU part {part_number} timed out")
                        sleep(settings.mineru_poll_interval_seconds)

                    progress = round(part_number / len(ranges) * 90)
                    DocumentRepository.update_processing_state(
                        session,
                        document,
                        DocumentStatus.PROCESSING,
                        parser=DocumentParser.MINERU,
                        processing_progress=progress,
                    )
                    session.commit()
                    session.refresh(document)

            merged_markdown = "".join(markdown_parts).strip()
            parsed_document = ParsedDocument(
                sections=(ParsedSection(
                    text=merged_markdown,
                    page_number=None,
                    metadata={
                        "parser": "mineru",
                        "source": "split-full.md",
                        "original_filename": document.original_filename,
                        "page_count": total_pages,
                        "part_count": len(ranges),
                    },
                ),),
                character_count=len(merged_markdown),
            )
            return processing_service.index_parsed_document(
                session, document, parsed_document
            )
        except Exception as exc:
            session.rollback()
            try:
                processing_service.vector_store.delete_document(document_id)
            except Exception:
                pass
            failed_document = DocumentRepository.get(session, document_id)
            if failed_document is not None:
                DocumentChunkRepository.delete_for_document(session, document_id)
                DocumentRepository.update_processing_state(
                    session,
                    failed_document,
                    DocumentStatus.FAILED,
                    chunk_count=0,
                    error_message=str(exc),
                    parser=DocumentParser.MINERU,
                    processing_progress=0,
                )
                DocumentRepository.mark_processing_finished(session, failed_document)
                session.commit()
            raise DocumentProcessingError(document_id, str(exc)) from exc

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
            if not (
                document.status == DocumentStatus.PROCESSING
                and document.parser == DocumentParser.MINERU
            ):
                DocumentRepository.mark_processing_started(
                    session,
                    document,
                    DocumentParser.MINERU,
                )

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
                    DocumentRepository.mark_processing_finished(
                        session,
                        failed_document,
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
                DocumentRepository.mark_processing_finished(
                    session,
                    document,
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

        # Refresh requests can overlap in browsers. Once indexing has
        # completed, return the stored result instead of downloading and
        # indexing the same MinerU archive again.
        if document.status == DocumentStatus.COMPLETED:
            return document

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
                        processing_progress=(
                            99 if isinstance(exc, MinerUResultDownloadError) else 0
                        ),
                    )
                    DocumentRepository.mark_processing_finished(
                        session,
                        failed_document,
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
