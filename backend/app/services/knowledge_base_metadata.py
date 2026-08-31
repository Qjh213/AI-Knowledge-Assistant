import re
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.models import Document, DocumentParser, DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.knowledge_base import KnowledgeBaseService


STATUS_LABELS = {
    DocumentStatus.PENDING: "等待处理",
    DocumentStatus.PROCESSING: "处理中",
    DocumentStatus.COMPLETED: "处理完成",
    DocumentStatus.FAILED: "处理失败",
}

PARSER_LABELS = {
    DocumentParser.LOCAL: "本地解析",
    DocumentParser.MINERU: "MinerU 解析",
}

METADATA_PATTERNS = (
    re.compile(
        r"(当前|这个|本).*(库).*(有什么|有哪些|多少|几个).*(文件|文档)"
    ),
    re.compile(r"(列出|列一下|查看|显示).*(文件|文档)(列表|清单)?"),
    re.compile(r"(文件|文档).*(列表|清单|数量|总数)"),
    re.compile(r"(多少|几个).*(文件|文档)"),
    re.compile(r"哪些.*(文件|文档).*(失败|完成|处理中|等待|未处理)"),
    re.compile(r"(失败|完成|处理中|等待处理|未处理).*(文件|文档)"),
    re.compile(r"哪些.*(文件|文档).*(mineru|本地).*(解析|处理)?"),
    re.compile(r"(mineru|本地).*(解析|处理).*(文件|文档)"),
)


class KnowledgeBaseMetadataService:
    """Answer deterministic questions about documents in a knowledge base."""

    def answer(
        self,
        session: Session,
        knowledge_base_id: UUID,
        question: str,
    ) -> str | None:
        normalized = " ".join(question.strip().lower().split())
        if not normalized or not any(
            pattern.search(normalized) for pattern in METADATA_PATTERNS
        ):
            return None

        KnowledgeBaseService.get(session, knowledge_base_id)
        documents = DocumentRepository.list_all_for_knowledge_base(
            session,
            knowledge_base_id,
        )
        filtered, description = self._apply_filters(documents, normalized)
        return self._format_answer(filtered, description)

    @staticmethod
    def _apply_filters(
        documents: list[Document],
        question: str,
    ) -> tuple[list[Document], str]:
        status_filter: DocumentStatus | None = None
        status_description = ""

        if "失败" in question:
            status_filter = DocumentStatus.FAILED
            status_description = "处理失败的"
        elif "处理中" in question:
            status_filter = DocumentStatus.PROCESSING
            status_description = "正在处理的"
        elif "等待" in question or "未处理" in question:
            status_filter = DocumentStatus.PENDING
            status_description = "等待处理的"
        elif "完成" in question or "已处理" in question:
            status_filter = DocumentStatus.COMPLETED
            status_description = "处理完成的"

        extension_filter: str | None = None
        extension_description = ""
        extension_candidates = (
            ("pdf", ".pdf", "PDF "),
            ("docx", ".docx", "DOCX "),
            ("markdown", ".md", "Markdown "),
            ("md 文件", ".md", "Markdown "),
            ("txt", ".txt", "TXT "),
        )
        for keyword, extension, description in extension_candidates:
            if keyword in question:
                extension_filter = extension
                extension_description = description
                break

        parser_filter: DocumentParser | None = None
        parser_description = ""
        if "mineru" in question:
            parser_filter = DocumentParser.MINERU
            parser_description = "使用 MinerU 解析的"
        elif "本地" in question and (
            "解析" in question or "处理" in question
        ):
            parser_filter = DocumentParser.LOCAL
            parser_description = "使用本地解析的"

        filtered = [
            document
            for document in documents
            if (
                status_filter is None
                or document.status == status_filter
            )
            and (
                extension_filter is None
                or Path(document.original_filename).suffix.lower()
                == extension_filter
            )
            and (
                parser_filter is None
                or document.parser == parser_filter
            )
        ]
        return (
            filtered,
            f"{status_description}{parser_description}{extension_description}文件",
        )

    @staticmethod
    def _format_answer(
        documents: list[Document],
        description: str,
    ) -> str:
        if not documents:
            return f"当前知识库中没有{description}。"

        lines = [
            f"当前知识库共有 {len(documents)} 个{description}：",
            "",
        ]
        for index, document in enumerate(documents, start=1):
            parser = PARSER_LABELS[document.parser]
            status = STATUS_LABELS[document.status]
            lines.append(
                f"{index}. {document.original_filename}"
                f"（{status}，{parser}，{document.chunk_count} 个分块）"
            )
        return "\n".join(lines)
