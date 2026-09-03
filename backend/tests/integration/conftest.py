"""Legacy business integration tests now use disposable, authenticated tenants.

The auth migration test owns its own schema and does not use this fixture.
No application schema, files or vector collection are used for test writes.
"""
from uuid import uuid4
import pytest


@pytest.fixture(autouse=True)
def isolated_business_infrastructure(request, monkeypatch, tmp_path):
    if not request.node.get_closest_marker('integration') or request.module.__name__.endswith('test_auth_postgres'):
        yield
        return
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.schema import CreateSchema, DropSchema
    from app.core.config import settings
    from app.database.base import Base
    from app.database.models import User
    from app.database.models.user import LEGACY_ADMIN_ID
    from app.api.auth_dependencies import get_auth_db
    from app.api.routes.documents import document_service
    from app.main import app
    from app.services.auth import hash_password
    from app.services.document_storage import DocumentStorageService
    from app.services.vector_store import VectorStoreService

    schema = 'aka_business_test_' + uuid4().hex
    engine = create_engine(settings.database_url)
    scoped = create_engine(settings.database_url)
    @event.listens_for(scoped, 'connect')
    def search_path(connection, record):
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
    previous_overrides = dict(app.dependency_overrides)
    client = getattr(request.module, 'client', None)
    old_headers = dict(client.headers) if client else None
    vector_store = None
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        Base.metadata.create_all(scoped)
        factory = sessionmaker(scoped)
        with factory() as db:
            db.add(User(id=LEGACY_ADMIN_ID, username='integration-admin', role='admin',
                password_hash=hash_password('Integration-only-password!'), must_change_password=False))
            db.commit()
        monkeypatch.setattr(request.module, 'SessionLocal', factory, raising=False)
        monkeypatch.setattr('app.api.dependencies.SessionLocal', factory)
        monkeypatch.setattr(settings, 'document_storage_path', tmp_path / 'documents')
        monkeypatch.setattr(settings, 'milvus_collection_name', schema)
        monkeypatch.setattr(document_service, 'storage_service', DocumentStorageService())
        def auth_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_auth_db] = auth_db
        if client:
            client.cookies.clear()
            client.headers['X-Requested-With'] = 'KnowledgeAssistant'
            response = client.post('/api/v1/auth/login', json={'username': 'integration-admin', 'password': 'Integration-only-password!'})
            assert response.status_code == 200
            client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        vector_store = VectorStoreService(collection_name=schema)
        yield
    finally:
        if client:
            client.cookies.clear()
            client.headers.clear()
            client.headers.update(old_headers)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        scoped.dispose()
        try:
            if vector_store is not None and vector_store.client.has_collection(schema):
                vector_store.client.drop_collection(schema)
        finally:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True, if_exists=True))
            engine.dispose()
