from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import AdminUser, AuthDB
from app.database.models import AuditLog, Conversation, Document, KnowledgeBase, User
from app.schemas.auth import PasswordReset, UserCreate, UserLimits, UserStatus
from app.services.auth import audit, hash_password, reauthenticate, revoke_sessions

router = APIRouter(prefix='/admin', tags=['Account administration'])


def account_view(db, user):
    owned = select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id)
    return dict(id=str(user.id), username=user.username, role=user.role,
        is_active=user.is_active, must_change_password=user.must_change_password,
        created_at=user.created_at,
        storage_limit_mb=user.storage_limit_mb, upload_limit_mb=user.upload_limit_mb,
        processing_limit=user.processing_limit, daily_ai_limit=user.daily_ai_limit,
        ai_usage_count=user.ai_usage_count if user.ai_usage_day == datetime.now(UTC).date().isoformat() else 0,
        storage_used_bytes=db.scalar(select(func.coalesce(func.sum(Document.file_size), 0)).where(Document.knowledge_base_id.in_(owned))),
        knowledge_base_count=db.scalar(select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.owner_id == user.id)),
        document_count=db.scalar(select(func.count()).select_from(Document).where(Document.knowledge_base_id.in_(owned))),
        conversation_count=db.scalar(select(func.count()).select_from(Conversation).where(Conversation.knowledge_base_id.in_(owned))))


def managed_user(db, user_id, actor_id, action):
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        audit(db, actor_id, None, action, outcome='denied')
        db.commit()
        raise HTTPException(404, '账号不存在。')
    # The only administrator is provisioned via CLI. No web role-management or
    # administrator reset/disable endpoints, even when more admins exist.
    if target.role != 'user':
        audit(db, actor_id, target.id, action, outcome='denied')
        db.commit()
        raise HTTPException(403, '后台只能管理普通账号；管理员请使用本人修改密码或服务器恢复流程。')
    return target


@router.get('/users')
def list_users(admin: AdminUser, db: AuthDB,
               offset: Annotated[int, Query(ge=0)] = 0,
               limit: Annotated[int, Query(ge=1, le=100)] = 20):
    users = db.scalars(select(User).order_by(User.created_at, User.id).offset(offset).limit(limit))
    return {'items': [account_view(db, u) for u in users],
            'total': db.scalar(select(func.count()).select_from(User))}


@router.post('/users', status_code=201)
def create_user(data: UserCreate, admin: AdminUser, db: AuthDB):
    user = User(username=data.username, password_hash=hash_password(data.temporary_password))
    db.add(user)
    try:
        db.flush()
        audit(db, admin.id, user.id, 'create_user')
        db.commit()
    except IntegrityError:
        db.rollback()
        audit(db, admin.id, None, 'create_user', outcome='conflict')
        db.commit()
        raise HTTPException(409, '用户名已存在。') from None
    return account_view(db, user)


@router.patch('/users/{user_id}/status')
def set_user_status(user_id: UUID, data: UserStatus, admin: AdminUser, db: AuthDB):
    reauthenticate(db, admin, data.admin_password)
    target = managed_user(db, user_id, admin.id, 'enable_user' if data.is_active else 'disable_user')
    target.is_active = data.is_active
    if not data.is_active:
        revoke_sessions(db, target.id)
    audit(db, admin.id, target.id, 'enable_user' if data.is_active else 'disable_user')
    db.commit()
    return account_view(db, target)


@router.post('/users/{user_id}/password', status_code=204)
def reset_password(user_id: UUID, data: PasswordReset, admin: AdminUser, db: AuthDB):
    reauthenticate(db, admin, data.admin_password)
    target = managed_user(db, user_id, admin.id, 'reset_password')
    target.password_hash = hash_password(data.temporary_password)
    target.must_change_password = True
    revoke_sessions(db, target.id)
    audit(db, admin.id, target.id, 'reset_password')
    db.commit()


@router.patch('/users/{user_id}/limits')
def set_user_limits(user_id: UUID, data: UserLimits, admin: AdminUser, db: AuthDB):
    target = managed_user(db, user_id, admin.id, 'update_limits')
    before = {key: getattr(target, key) for key in type(data).model_fields}
    for key, value in data.model_dump().items():
        setattr(target, key, value)
    audit(db, admin.id, target.id, 'update_limits', details={'before': before, 'after': data.model_dump()})
    db.commit()
    return account_view(db, target)


@router.get('/audit-logs')
def audit_logs(admin: AdminUser, db: AuthDB,
               offset: Annotated[int, Query(ge=0)] = 0,
               limit: Annotated[int, Query(ge=1, le=100)] = 20):
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id).offset(offset).limit(limit)))
    ids = {identifier for log in logs for identifier in (log.actor_id, log.target_id) if identifier}
    names = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_(ids)))}
    return {'items': [dict(id=str(log.id), actor=names.get(log.actor_id, '未登录 / 系统'),
        target=names.get(log.target_id, '—'), action=log.action, outcome=log.outcome,
        details=log.details, created_at=log.created_at) for log in logs],
        'total': db.scalar(select(func.count()).select_from(AuditLog))}
