"""Disposable loopback-only UI acceptance environment. Ctrl+C cleans its schema.

Run from backend: .venv/Scripts/python tests/manual_auth_preview.py
Never deploy this test harness. Accounts/passwords below are public test data.
"""
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.orm import sessionmaker
import uvicorn

from app.core.config import settings
from app.database.base import Base
from app.database.models import User
from app.database.models.user import LEGACY_ADMIN_ID
from app.services.auth import hash_password
from app.api.auth_dependencies import get_auth_db
from app.main import create_application
import app.api.dependencies as dependencies


def main():
    schema = 'aka_auth_preview_' + uuid4().hex
    engine = create_engine(settings.database_url)
    scoped = create_engine(settings.database_url)
    @event.listens_for(scoped, 'connect')
    def set_schema(connection, record):
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        Base.metadata.create_all(scoped)
        factory = sessionmaker(scoped)
        with factory() as db:
            db.add(User(id=LEGACY_ADMIN_ID, username='preview-admin', role='admin',
                password_hash=hash_password('Preview-only-password-123!'),
                is_active=True, must_change_password=False, daily_ai_limit=0))
            db.commit()
        def auth_db():
            with factory() as db:
                yield db
        settings.cors_origins = ['http://127.0.0.1:5174']
        settings.auth_cookie_secure = False
        application = create_application()
        application.dependency_overrides[get_auth_db] = auth_db
        dependencies.SessionLocal = factory
        uvicorn.run(application, host='127.0.0.1', port=18181, log_level='warning', access_log=False)
    finally:
        scoped.dispose()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()


if __name__ == '__main__':
    main()
