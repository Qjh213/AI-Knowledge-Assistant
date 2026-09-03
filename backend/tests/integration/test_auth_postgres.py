"""Explicitly run against PostgreSQL; all writes confined to a fresh test schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from fastapi import HTTPException

from app.core.config import settings
from app.database.models import Document, KnowledgeBase, User
from app.database.models.user import LEGACY_ADMIN_ID
from app.database.tenant import scope_session
from app.services.quotas import reserve_ai_request

pytestmark = pytest.mark.integration


def test_legacy_migration_and_concurrent_quota_reservation():
    # Generated and created here; never use public or a user-provided schema.
    schema = 'aka_auth_test_' + uuid4().hex
    engine = create_engine(settings.database_url)
    scoped = None
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config('alembic.ini')
            config.attributes['connection'] = connection
            command.upgrade(config, '6fdd145e1b8c')
            legacy_id = uuid4()
            connection.execute(text('INSERT INTO knowledge_bases (id, name, created_at, updated_at) VALUES (:id, :name, :now, :now)'),
                               {'id': legacy_id, 'name': 'legacy-preserved', 'now': datetime.now(UTC)})
            command.upgrade(config, 'head')
            owner = connection.scalar(text('SELECT owner_id FROM knowledge_bases WHERE id=:id'), {'id': legacy_id})
            assert owner == LEGACY_ADMIN_ID
            assert connection.scalar(text('SELECT is_active FROM users WHERE id=:id'), {'id': owner}) is False
            assert connection.scalar(text('SELECT password_hash FROM users WHERE id=:id'), {'id': owner}) == '!'
        scoped = create_engine(settings.database_url)
        @event.listens_for(scoped, 'connect')
        def schema_search_path(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}"')
            dbapi_connection.commit()
        factory = sessionmaker(scoped, expire_on_commit=False)
        user_id = uuid4()
        with factory() as db:
            db.add(User(id=user_id, username='quota-test', password_hash='!', is_active=True,
                        must_change_password=False, daily_ai_limit=1))
            db.commit()
        def reserve_one(_):
            with factory() as db:
                scope_session(db, user_id)
                try:
                    reserve_ai_request(db)
                    db.commit()
                    return 'accepted'
                except HTTPException as error:
                    db.rollback()
                    assert error.status_code == 429
                    return 'denied'
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(reserve_one, range(4)))
        assert results.count('accepted') == 1
        assert results.count('denied') == 3
        with factory() as db:
            assert db.get(User, user_id).ai_usage_count == 1
            assert db.get(KnowledgeBase, legacy_id).name == 'legacy-preserved'
    finally:
        if scoped is not None:
            scoped.dispose()
        # Drop only the exact schema created by this test, never application data.
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()
