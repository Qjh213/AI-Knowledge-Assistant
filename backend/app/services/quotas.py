from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Document, DocumentStatus, User


def locked_user(session):
    if not isinstance(session, Session):
        return None
    owner_id = session.info.get('owner_id')
    if owner_id is None:
        return None  # Internal worker and isolated service tests only.
    user = session.scalar(select(User).where(User.id == owner_id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active:
        raise HTTPException(401, '账号已停用。')
    return user


def reserve_ai_request(session, *, processing_document_id=None, active_document_ids=None):
    """One unit per accepted AI operation, including failed provider attempts.

    This is a request budget, not a token/currency accounting system. The user
    row lock serializes counters and processing admission before service commit.
    """
    user = locked_user(session)
    if user is None:
        return
    if processing_document_id is not None:
        statement = select(func.count()).select_from(Document).where(
            Document.status == DocumentStatus.PROCESSING, Document.id != processing_document_id)
        if active_document_ids is not None:
            # Snapshot after acquiring the user lock. Stale rows after restart
            # must not consume every slot and prevent manual recovery.
            statement = statement.where(Document.id.in_(active_document_ids()))
        running = session.scalar(statement) or 0
        if running >= user.processing_limit:
            raise HTTPException(429, '已达到账号的解析并发上限，请等待现有任务结束。')
    today = datetime.now(UTC).date().isoformat()
    if user.ai_usage_day != today:
        user.ai_usage_day, user.ai_usage_count = today, 0
    if user.ai_usage_count >= user.daily_ai_limit:
        raise HTTPException(429, '今日 AI 请求额度已用完，请联系管理员。')
    user.ai_usage_count += 1
    session.flush()


def upload_budget(session):
    user = locked_user(session)
    if user is None:
        return None
    used = session.scalar(select(func.coalesce(func.sum(Document.file_size), 0))) or 0
    remaining = user.storage_limit_mb * 1024 * 1024 - used
    if remaining <= 0:
        raise HTTPException(413, '账号存储额度已用完，请联系管理员。')
    return min(remaining, user.upload_limit_mb * 1024 * 1024)


def charge_ai_request(session):
    # Called by validated route handlers, not dependencies: malformed payloads
    # must not consume quota before FastAPI returns its validation error.
    if not isinstance(session, Session) or session.info.get('owner_id') is None:
        return
    reserve_ai_request(session)
    session.commit()
