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
from app.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
)
from app.services.retrieval import RetrievalService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.quotas import charge_ai_request

from app.schemas.rag import (
    RagAnswerResponse,
    RagQuestionRequest,
)
from app.services.rag import RagService


router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)

SessionDependency = Annotated[Session, Depends(get_db)]


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


RetrievalServiceDependency = Annotated[
    RetrievalService,
    Depends(get_retrieval_service),
]


def get_rag_service() -> RagService:
    return RagService()


RagServiceDependency = Annotated[
    RagService,
    Depends(get_rag_service),
]


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


@router.post(
    "/{knowledge_base_id}/search",
    response_model=RetrievalResponse,
)
def search_knowledge_base(
    knowledge_base_id: UUID,
    request: RetrievalRequest,
    session: SessionDependency,
    retrieval_service: RetrievalServiceDependency,
) -> RetrievalResponse:
    charge_ai_request(session)
    return retrieval_service.search(
        session,
        knowledge_base_id,
        request,
    )


@router.post(
    "/{knowledge_base_id}/answer",
    response_model=RagAnswerResponse,
)
def answer_from_knowledge_base(
    knowledge_base_id: UUID,
    request: RagQuestionRequest,
    session: SessionDependency,
    rag_service: RagServiceDependency,
) -> RagAnswerResponse:
    charge_ai_request(session)
    return rag_service.answer(
        session,
        knowledge_base_id,
        request,
    )


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
