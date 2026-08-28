from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)
from app.services.conversation import ConversationService


router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/conversations",
    tags=["Conversations"],
)

SessionDependency = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    knowledge_base_id: UUID,
    data: ConversationCreate,
    session: SessionDependency,
) -> ConversationResponse:
    conversation = ConversationService.create(
        session,
        knowledge_base_id,
        data,
    )
    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationListResponse,
)
def list_conversations(
    knowledge_base_id: UUID,
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListResponse:
    items, total = ConversationService.list(
        session,
        knowledge_base_id,
        offset=offset,
        limit=limit,
    )

    return ConversationListResponse(
        items=[
            ConversationResponse.model_validate(item)
            for item in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    knowledge_base_id: UUID,
    conversation_id: UUID,
    session: SessionDependency,
) -> ConversationResponse:
    conversation = ConversationService.get(
        session,
        knowledge_base_id,
        conversation_id,
    )
    return ConversationResponse.model_validate(conversation)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def update_conversation(
    knowledge_base_id: UUID,
    conversation_id: UUID,
    data: ConversationUpdate,
    session: SessionDependency,
) -> ConversationResponse:
    conversation = ConversationService.update(
        session,
        knowledge_base_id,
        conversation_id,
        data,
    )
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    knowledge_base_id: UUID,
    conversation_id: UUID,
    session: SessionDependency,
) -> Response:
    ConversationService.delete(
        session,
        knowledge_base_id,
        conversation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)