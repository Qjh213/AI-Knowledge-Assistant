from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.conversation import (
    ConversationResponse,
    RecentConversationListResponse,
    RecentConversationResponse,
)
from app.services.conversation import ConversationService


router = APIRouter(prefix="/conversations", tags=["Conversations"])
SessionDependency = Annotated[Session, Depends(get_db)]


@router.get("/recent", response_model=RecentConversationListResponse)
def list_recent_conversations(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RecentConversationListResponse:
    items, total = ConversationService.list_recent(
        session,
        offset=offset,
        limit=limit,
    )
    return RecentConversationListResponse(
        items=[
            RecentConversationResponse(
                **ConversationResponse.model_validate(
                    conversation,
                    from_attributes=True,
                ).model_dump(),
                knowledge_base_name=knowledge_base_name,
            )
            for conversation, knowledge_base_name in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
