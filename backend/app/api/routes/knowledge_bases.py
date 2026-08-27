from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_base import KnowledgeBaseService


router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)

SessionDependency = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_base(
    data: KnowledgeBaseCreate,
    session: SessionDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = KnowledgeBaseService.create(session, data)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
)
def list_knowledge_bases(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeBaseListResponse:
    items, total = KnowledgeBaseService.list(
        session,
        offset=offset,
        limit=limit,
    )

    return KnowledgeBaseListResponse(
        items=[
            KnowledgeBaseResponse.model_validate(item)
            for item in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
)
def get_knowledge_base(
    knowledge_base_id: UUID,
    session: SessionDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = KnowledgeBaseService.get(
        session,
        knowledge_base_id,
    )
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.patch(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
)
def update_knowledge_base(
    knowledge_base_id: UUID,
    data: KnowledgeBaseUpdate,
    session: SessionDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = KnowledgeBaseService.update(
        session,
        knowledge_base_id,
        data,
    )
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.delete(
    "/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_knowledge_base(
    knowledge_base_id: UUID,
    session: SessionDependency,
) -> Response:
    KnowledgeBaseService.delete(session, knowledge_base_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)