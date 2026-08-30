from uuid import UUID


class KnowledgeBaseNotFoundError(Exception):
    def __init__(self, knowledge_base_id: UUID) -> None:
        self.knowledge_base_id = knowledge_base_id
        super().__init__(
            f"Knowledge base '{knowledge_base_id}' was not found"
        )


class ConversationNotFoundError(Exception):
    def __init__(
        self,
        knowledge_base_id: UUID,
        conversation_id: UUID,
    ) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.conversation_id = conversation_id
        super().__init__(
            f"Conversation '{conversation_id}' was not found in "
            f"knowledge base '{knowledge_base_id}'"
        )


class KnowledgeBaseAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Knowledge base with name '{name}' already exists"
        )


class UnsupportedDocumentTypeError(Exception):
    def __init__(self, extension: str) -> None:
        self.extension = extension
        super().__init__(
            f"Document type '{extension or 'unknown'}' is not supported"
        )


class DocumentTooLargeError(Exception):
    def __init__(self, max_size_mb: int) -> None:
        self.max_size_mb = max_size_mb
        super().__init__(
            f"Document exceeds the maximum size of {max_size_mb} MB"
        )


class EmptyDocumentError(Exception):
    def __init__(self) -> None:
        super().__init__("Document is empty")


class DocumentNotFoundError(Exception):
    def __init__(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.document_id = document_id
        super().__init__(
            f"Document '{document_id}' was not found in "
            f"knowledge base '{knowledge_base_id}'"
        )


class DocumentAlreadyExistsError(Exception):
    def __init__(
        self,
        knowledge_base_id: UUID,
        filename: str,
    ) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.filename = filename
        super().__init__(
            f"A document with the same content already exists in "
            f"knowledge base '{knowledge_base_id}'"
        )


class DocumentParseError(Exception):
    def __init__(
        self,
        filename: str,
        detail: str,
    ) -> None:
        self.filename = filename
        self.detail = detail
        super().__init__(
            f"Failed to parse document '{filename}': {detail}"
        )


class MinerUServiceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"MinerU operation failed: {detail}")


class NoExtractableTextError(DocumentParseError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            filename,
            "no extractable text was found",
        )


class DocumentChunkingError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Failed to chunk document: {detail}")


class EmbeddingServiceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Embedding generation failed: {detail}")


class VectorStoreError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Vector store operation failed: {detail}")


class DocumentProcessingError(Exception):
    def __init__(
        self,
        document_id: UUID,
        detail: str,
    ) -> None:
        self.document_id = document_id
        self.detail = detail
        super().__init__(
            f"Failed to process document '{document_id}': {detail}"
        )


class RetrievalServiceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Retrieval failed: {detail}")


class ChatServiceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Chat generation failed: {detail}")
