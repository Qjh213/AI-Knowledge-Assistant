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