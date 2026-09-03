from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models import User, KnowledgeBase, Document, Conversation
from app.database.tenant import scope_session
from app.api.auth_dependencies import require_user
from app.core.exceptions import KnowledgeBaseNotFoundError, DocumentNotFoundError, ConversationNotFoundError


def get_db(request: Request, user: Annotated[User, Depends(require_user)]) -> Iterator[Session]:
    with SessionLocal() as session:
        scope_session(session, user.id)
        # Validate every path resource before any provider call or quota charge.
        for key, model in [('knowledge_base_id', KnowledgeBase), ('document_id', Document), ('conversation_id', Conversation)]:
            if key not in request.path_params:
                continue
            try:
                resource_id = UUID(str(request.path_params[key]))
            except ValueError:
                raise HTTPException(422, '资源 ID 无效。') from None
            obj = session.scalar(select(model).where(model.id == resource_id))
            if obj is None or (key != 'knowledge_base_id' and str(obj.knowledge_base_id) != str(request.path_params['knowledge_base_id'])):
                if key == 'knowledge_base_id':
                    raise KnowledgeBaseNotFoundError(resource_id)
                parent_id = UUID(str(request.path_params['knowledge_base_id']))
                if key == 'document_id':
                    raise DocumentNotFoundError(parent_id, resource_id)
                raise ConversationNotFoundError(parent_id, resource_id)
        route_name = request.scope['route'].name
        # Old synchronous processing endpoints cannot enforce the common worker
        # queue reliably. Keep one authenticated, quota-checked admission path.
        if route_name in {'process_document', 'submit_document_to_mineru', 'refresh_mineru_document_processing'}:
            raise HTTPException(409, '请使用后台解析或恢复处理入口。')
        yield session
