"""Request sessions are tenant-scoped; internal worker sessions are separate.

Never execute raw SQL for business reads in a tenant session. Authorization at
the route boundary and these ORM filters both apply, including to administrators.
"""
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.database.models import KnowledgeBase, Document, DocumentChunk, Conversation, Message


def scope_session(session: Session, owner_id) -> None:
    if 'owner_id' in session.info and session.info['owner_id'] != owner_id:
        raise ValueError('Cannot switch tenant on an existing session')
    session.info['owner_id'] = owner_id


@event.listens_for(Session, 'do_orm_execute')
def tenant_filter(state):
    owner_id = state.session.info.get('owner_id')
    if owner_id is None or not (state.is_select or state.is_update or state.is_delete):
        return
    kb = KnowledgeBase.__table__
    docs = Document.__table__
    conv = Conversation.__table__
    owned = select(kb.c.id).where(kb.c.owner_id == owner_id)
    state.statement = state.statement.options(
        with_loader_criteria(KnowledgeBase, KnowledgeBase.owner_id == owner_id, include_aliases=True),
        with_loader_criteria(Document, Document.knowledge_base_id.in_(owned), include_aliases=True),
        with_loader_criteria(Conversation, Conversation.knowledge_base_id.in_(owned), include_aliases=True),
        with_loader_criteria(DocumentChunk, DocumentChunk.document_id.in_(select(docs.c.id).where(docs.c.knowledge_base_id.in_(owned))), include_aliases=True),
        with_loader_criteria(Message, Message.conversation_id.in_(select(conv.c.id).where(conv.c.knowledge_base_id.in_(owned))), include_aliases=True),
    )


@event.listens_for(Session, 'before_flush')
def tenant_writes(session, flush_context, instances):
    owner_id = session.info.get('owner_id')
    if owner_id is None:
        return
    for obj in session.new.union(session.dirty).union(session.deleted):
        if isinstance(obj, KnowledgeBase):
            if obj in session.new and obj.owner_id is None:
                obj.owner_id = owner_id
            if obj.owner_id != owner_id:
                raise ValueError('Cross-user write denied')
        elif isinstance(obj, (Document, Conversation)):
            kb = session.scalar(select(KnowledgeBase).where(KnowledgeBase.id == obj.knowledge_base_id))
            if kb is None:
                raise ValueError('Cross-user parent denied')
        elif isinstance(obj, (Message, DocumentChunk)):
            parent_type = Conversation if isinstance(obj, Message) else Document
            parent_id = obj.conversation_id if isinstance(obj, Message) else obj.document_id
            if session.scalar(select(parent_type).where(parent_type.id == parent_id)) is None:
                raise ValueError('Cross-user parent denied')
