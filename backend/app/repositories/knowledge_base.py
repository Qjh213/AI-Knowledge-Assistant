from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import KnowledgeBase
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
)


class KnowledgeBaseRepository:
    @staticmethod
    def get(
        session: Session,
        knowledge_base_id: UUID,
    ) -> KnowledgeBase | None:
        return session.get(KnowledgeBase, knowledge_base_id)

    @staticmethod
    def get_by_name(
        session: Session,
        name: str,
    ) -> KnowledgeBase | None:
        statement = select(KnowledgeBase).where(
            KnowledgeBase.name == name,
        )
        return session.scalar(statement)

    @staticmethod
    def list(
        session: Session,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[KnowledgeBase], int]:
        count_statement = select(func.count()).select_from(KnowledgeBase)
        total = session.scalar(count_statement) or 0

        statement = (
            select(KnowledgeBase)
            .order_by(KnowledgeBase.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(session.scalars(statement).all())

        return items, total

    @staticmethod
    def create(
        session: Session,
        data: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(**data.model_dump())

        session.add(knowledge_base)
        session.flush()
        session.refresh(knowledge_base)

        return knowledge_base

    @staticmethod
    def update(
        session: Session,
        knowledge_base: KnowledgeBase,
        data: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(knowledge_base, field, value)

        session.flush()
        session.refresh(knowledge_base)

        return knowledge_base

    @staticmethod
    def delete(
        session: Session,
        knowledge_base: KnowledgeBase,
    ) -> None:
        session.delete(knowledge_base)
        session.flush()