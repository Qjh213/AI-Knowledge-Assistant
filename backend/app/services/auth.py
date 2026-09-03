"""Password and revocable server-side session primitives (no plaintext storage)."""
import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import case, delete, select
from sqlalchemy.orm import Session

from app.database.models import AuditLog, AuthThrottle, User, UserSession

PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(iterations) != PASSWORD_ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# Constant dummy workload for unknown users; never usable as an account hash.
DUMMY_HASH = f'pbkdf2_sha256${PASSWORD_ITERATIONS}$' + '00' * 16 + '$' + '00' * 32


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def audit(db: Session, actor_id, target_id, action: str, *, outcome='success', details=None):
    db.add(AuditLog(actor_id=actor_id, target_id=target_id, action=action,
                    outcome=outcome, details=details or {}, created_at=datetime.now(UTC)))


def revoke_sessions(db: Session, user_id):
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))


def throttle(db: Session, key: str, limit: int = 10):
    """Persistent atomic fixed-window limits, including across server restarts."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    now = int(time.time()) // 300
    insert = sqlite_insert if db.get_bind().dialect.name == 'sqlite' else pg_insert
    statement = insert(AuthThrottle).values(key=token_digest(key), window=now, hits=1)
    statement = statement.on_conflict_do_update(index_elements=['key'], set_={
        'window': now,
        'hits': case((AuthThrottle.window == now, AuthThrottle.hits + 1), else_=1),
    }).returning(AuthThrottle.hits)
    hits = db.scalar(statement)
    db.execute(delete(AuthThrottle).where(AuthThrottle.window < now - 288))
    db.commit()
    if hits > limit:
        raise HTTPException(429, '尝试过于频繁，请 5 分钟后再试。', headers={'Retry-After': '300'})


def check_browser_write(request: Request):
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return
    # Custom header forces cross-origin browsers through CORS preflight, even
    # for login. SameSite cookies alone do not protect same-site subdomains.
    if request.headers.get('X-Requested-With') != 'KnowledgeAssistant':
        raise HTTPException(403, '缺少安全请求头，请刷新页面。')
    from app.core.config import settings
    origin = request.headers.get('origin')
    if origin and origin not in settings.cors_origins and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403, '请求来源不受信任。')


def reauthenticate(db: Session, actor, password: str):
    throttle(db, f'reauth:{actor.id}')
    # Refresh after the rate-limit transaction; a reset may have just occurred.
    actor = db.scalar(select(User).where(User.id == actor.id).with_for_update().execution_options(populate_existing=True))
    if not actor.is_active or not verify_password(password, actor.password_hash):
        audit(db, actor.id, actor.id, 'reauthenticate', outcome='denied')
        db.commit()
        raise HTTPException(403, '管理员密码不正确或账号已停用。')
