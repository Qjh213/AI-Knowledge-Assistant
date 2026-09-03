from collections.abc import Iterator
from typing import Annotated
from datetime import UTC, datetime
import hmac

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models import User, UserSession
from app.services.auth import check_browser_write, token_digest

COOKIE_NAME = 'aka_session'


def get_auth_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


AuthDB = Annotated[Session, Depends(get_auth_db)]


def get_current_user(request: Request, db: AuthDB) -> User:
    check_browser_write(request)
    token = request.cookies.get(COOKIE_NAME, '')
    session = db.get(UserSession, token_digest(token)) if token else None
    if session is None or session.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise HTTPException(401, '请登录后继续。')
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, '账号已停用或会话已失效。')
    # Prevent an old tab from displaying responses for a newly logged-in cookie
    # identity. This header is a consistency check, never an identity credential.
    account_id = request.headers.get('X-Account-ID')
    if account_id and account_id != str(user.id):
        raise HTTPException(401, '浏览器账号已切换，请重新登录。')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf_token):
            raise HTTPException(403, '安全令牌已失效，请刷新页面。')
    request.state.auth_session = session
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_user(user: CurrentUser) -> User:
    if user.must_change_password:
        raise HTTPException(403, '首次登录或密码重置后，必须先修改密码。', headers={'X-Password-Change-Required': 'true'})
    return user


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if user.role != 'admin':
        raise HTTPException(403, '仅管理员可访问。')
    return user


AdminUser = Annotated[User, Depends(require_admin)]
