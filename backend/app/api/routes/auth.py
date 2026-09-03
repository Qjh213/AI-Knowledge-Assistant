import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select

from app.api.auth_dependencies import AuthDB, CurrentUser, COOKIE_NAME
from app.core.config import settings
from app.database.models import User, UserSession
from app.schemas.auth import LoginInput, PasswordChange
from app.services.auth import DUMMY_HASH, audit, check_browser_write, hash_password, reauthenticate, revoke_sessions, throttle, token_digest, verify_password

router = APIRouter(prefix='/auth', tags=['Authentication'])


def user_view(user: User) -> dict:
    return dict(id=str(user.id), username=user.username, role=user.role,
                must_change_password=user.must_change_password)


@router.post('/login')
def login(data: LoginInput, request: Request, response: Response, db: AuthDB):
    check_browser_write(request)
    ip = request.client.host if request.client else 'unknown'
    # Never trust a client-supplied X-Forwarded-For as an auth throttle key.
    throttle(db, f'login-ip:{ip}', 60)
    throttle(db, f'login-user:{data.username}', 10)
    user = db.scalar(select(User).where(User.username == data.username).with_for_update())
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not valid or user is None or not user.is_active:
        audit(db, None, user.id if user else None, 'login', outcome='denied')
        db.commit()
        raise HTTPException(401, '用户名或密码错误，或账号已停用。')
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        db.execute(delete(UserSession).where(UserSession.token_hash == token_digest(old_token)))
    db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=token_digest(token), user_id=user.id, csrf_token=csrf,
                       expires_at=datetime.now(UTC) + timedelta(hours=8)))
    audit(db, user.id, user.id, 'login')
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=8 * 3600, httponly=True,
                        secure=settings.auth_cookie_secure, samesite='strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {**user_view(user), 'csrf_token': csrf}


@router.get('/me')
def me(user: CurrentUser, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return {**user_view(user), 'csrf_token': request.state.auth_session.csrf_token}


@router.post('/logout', status_code=204)
def logout(user: CurrentUser, request: Request, response: Response, db: AuthDB):
    db.delete(request.state.auth_session)
    audit(db, user.id, user.id, 'logout')
    db.commit()
    response.delete_cookie(COOKIE_NAME, path='/', secure=settings.auth_cookie_secure, httponly=True, samesite='strict')


@router.post('/password', status_code=204)
def change_password(data: PasswordChange, user: CurrentUser, db: AuthDB, response: Response):
    reauthenticate(db, user, data.current_password)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(400, '新密码不能与原密码相同。')
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    revoke_sessions(db, user.id)
    audit(db, user.id, user.id, 'change_password')
    db.commit()
    response.delete_cookie(COOKIE_NAME, path='/')
