"""Interactive, server-console-only administrator activation/recovery.

Usage: python -m app.bootstrap_admin [--reset]
Never pass passwords in arguments or environment variables.
"""
import argparse
import getpass

from sqlalchemy import select
from app.database.models import User
from app.database.models.user import LEGACY_ADMIN_ID
from app.database.session import SessionLocal
from app.schemas.auth import UserCreate
from app.services.auth import audit, hash_password, revoke_sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset', action='store_true', help='Explicitly reset the existing administrator password and revoke sessions')
    args = parser.parse_args()
    username = input('Administrator username [admin]: ').strip() or 'admin'
    password = getpass.getpass('New password (12–128 characters): ')
    confirmation = getpass.getpass('Repeat password: ')
    if password != confirmation:
        raise SystemExit('Passwords do not match; nothing changed.')
    try:
        data = UserCreate(username=username, temporary_password=password)
    except ValueError:
        raise SystemExit('Invalid username or password length; nothing changed.') from None
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == LEGACY_ADMIN_ID).with_for_update())
        if user is None:
            raise SystemExit('Run alembic upgrade head first.')
        if user.password_hash != '!' and not args.reset:
            raise SystemExit('Administrator already initialized; use --reset only for intentional recovery.')
        if db.scalar(select(User).where(User.username == data.username, User.id != user.id)):
            raise SystemExit('Username already used; nothing changed.')
        user.username = data.username
        user.password_hash = hash_password(data.temporary_password)
        user.is_active = True
        user.must_change_password = False
        revoke_sessions(db, user.id)
        audit(db, None, user.id, 'bootstrap_admin_reset' if args.reset else 'bootstrap_admin')
        db.commit()
    print('Administrator ready. Existing knowledge bases retain their ownership.')


if __name__ == '__main__':
    main()
