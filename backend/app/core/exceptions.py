from uuid import UUID


class KnowledgeBaseNotFoundError(Exception):
    def __init__(self, knowledge_base_id: UUID) -> None:
        self.knowledge_base_id = knowledge_base_id
        super().__init__(
            f"Knowledge base '{knowledge_base_id}' was not found"
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