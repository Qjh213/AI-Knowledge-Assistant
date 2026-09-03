"""Real cookie authentication and ORM isolation in a disposable SQLite DB.

No override of authentication or tenant get_db. PostgreSQL migration/concurrency
coverage lives separately, because SQLite cannot prove row-lock semantics.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.api.auth_dependencies import get_auth_db
from app.database.base import Base
from app.database.models import AuditLog, Conversation, Document, DocumentChunk, KnowledgeBase, Message, MessageRole, User, UserSession
from app.database.tenant import scope_session
from app.main import create_application
from app.services.auth import hash_password, verify_password

PASSWORD = 'Test-only-password-2098!'
NEW_PASSWORD = 'Changed-test-password-2098!'
HEADERS = {'X-Requested-With': 'KnowledgeAssistant'}


@compiles(JSONB, 'sqlite')
def compile_jsonb_for_test(type_, compiler, **kw):
    return 'JSON'


@pytest.fixture(scope='module')
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def env(tmp_path, monkeypatch, password_hash):
    engine = create_engine(f'sqlite:///{tmp_path / "auth-test.db"}', connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    ids = {name: uuid4() for name in ['admin', 'alice', 'bob']}
    kb_ids, doc_ids, conv_ids = {}, {}, {}
    with factory() as db:
        for name, identifier in ids.items():
            db.add(User(id=identifier, username=name, password_hash=password_hash,
                        role='admin' if name == 'admin' else 'user', must_change_password=False))
        db.flush()
        for name in ids:
            kb = KnowledgeBase(owner_id=ids[name], name='shared-name')
            db.add(kb); db.flush(); kb_ids[name] = kb.id
            doc = Document(knowledge_base_id=kb.id, original_filename=f'{name}-private.txt', stored_filename=f'{name}.txt',
                           file_path=f'{name}.txt', mime_type='text/plain', file_size=100, checksum=name.ljust(64, '0'), status='completed')
            conv = Conversation(knowledge_base_id=kb.id, title=f'{name}-private-chat')
            db.add_all([doc, conv]); db.flush()
            doc_ids[name], conv_ids[name] = doc.id, conv.id
            db.add(Message(conversation_id=conv.id, role=MessageRole.USER, content=f'{name}-secret'))
            db.add(DocumentChunk(document_id=doc.id, chunk_index=0, content=f'{name}-secret'))
        db.commit()
    app = create_application()
    def auth_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_auth_db] = auth_db
    monkeypatch.setattr('app.api.dependencies.SessionLocal', factory)
    with TestClient(app, headers=HEADERS) as client:
        yield SimpleNamespace(client=client, app=app, factory=factory, ids=ids, kb=kb_ids, doc=doc_ids, conv=conv_ids)
    engine.dispose()


def login(env, username='alice', password=PASSWORD):
    env.client.headers.pop('X-CSRF-Token', None)
    response = env.client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    env.client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return response


def test_password_hashes_are_salted_and_not_reversible(password_hash):
    assert PASSWORD not in password_hash
    assert verify_password(PASSWORD, password_hash)
    assert not verify_password('incorrect', password_hash)
    assert not verify_password(PASSWORD, '!')
    assert hash_password(PASSWORD) != password_hash


@pytest.mark.parametrize('method,path', [
    ('get', '/knowledge-bases'), ('get', '/dashboard/overview'), ('get', '/conversations/recent'),
    ('post', '/knowledge-bases'), ('get', '/admin/users'), ('get', '/admin/audit-logs'),
])
def test_anonymous_business_and_admin_requests_rejected(env, method, path):
    assert getattr(env.client, method)('/api/v1' + path).status_code == 401


def test_cookie_csrf_login_origin_and_logout(env):
    denied = env.client.post('/api/v1/auth/login', headers={'Origin': 'https://evil.example'}, json={'username': 'alice', 'password': PASSWORD})
    assert denied.status_code == 403
    response = login(env)
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    with env.factory() as db:
        token = env.client.cookies.get('aka_session')
        assert db.get(UserSession, token) is None
    env.client.headers.pop('X-CSRF-Token')
    assert env.client.post('/api/v1/knowledge-bases', json={'name': 'new'}).status_code == 403
    env.client.headers['X-CSRF-Token'] = env.client.get('/api/v1/auth/me').json()['csrf_token']
    assert env.client.post('/api/v1/auth/logout').status_code == 204
    assert env.client.get('/api/v1/auth/me').status_code == 401


def test_first_login_requires_change_and_revokes_all_sessions(env):
    with env.factory() as db:
        db.get(User, env.ids['alice']).must_change_password = True
        db.commit()
    login(env)
    assert env.client.get('/api/v1/knowledge-bases').status_code == 403
    assert env.client.post('/api/v1/auth/password', json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD}).status_code == 204
    assert env.client.get('/api/v1/auth/me').status_code == 401
    assert not login(env, password=NEW_PASSWORD).json()['must_change_password']
    assert env.client.get('/api/v1/knowledge-bases').status_code == 200


def test_lists_stats_names_and_orm_children_are_tenant_scoped(env):
    for username in ['alice', 'bob', 'admin']:
        login(env, username)
        data = env.client.get('/api/v1/knowledge-bases').json()
        assert data['total'] == 1 and data['items'][0]['id'] == str(env.kb[username])
        overview = env.client.get('/api/v1/dashboard/overview').json()
        assert overview['knowledge_base_count'] == 1
        assert overview['processed_document_count'] == 1
        assert overview['conversation_count'] == 1
        recent = env.client.get('/api/v1/conversations/recent').json()
        assert recent['total'] == 1 and username in recent['items'][0]['title']
        with env.factory() as db:
            scope_session(db, env.ids[username])
            assert [m.content for m in db.scalars(select(Message))] == [f'{username}-secret']
            assert [c.content for c in db.scalars(select(DocumentChunk))] == [f'{username}-secret']
        created = env.client.post('/api/v1/knowledge-bases', json={'name': 'same-new-name'})
        assert created.status_code == 201
        with env.factory() as db:
            assert db.scalar(select(KnowledgeBase.owner_id).where(KnowledgeBase.id == __import__('uuid').UUID(created.json()['id']))) == env.ids[username]


@pytest.mark.parametrize('method,suffix', [
    ('get',''), ('patch',''), ('delete',''), ('post','/search'), ('post','/answer'),
    ('get','/documents'), ('post','/documents'), ('get','/documents/{doc}'), ('delete','/documents/{doc}'),
    ('post','/documents/{doc}/process'), ('post','/documents/{doc}/process/background'),
    ('post','/documents/{doc}/process/retry'), ('post','/documents/{doc}/process/mineru'),
    ('post','/documents/{doc}/process/mineru/refresh'), ('get','/conversations'), ('post','/conversations'),
    ('get','/conversations/{conv}'), ('patch','/conversations/{conv}'), ('delete','/conversations/{conv}'),
    ('get','/conversations/{conv}/messages'), ('post','/conversations/{conv}/messages'),
    ('post','/conversations/{conv}/messages/stream'),
])
def test_all_foreign_resource_routes_fail_before_provider_calls(env, method, suffix):
    login(env)
    path = f'/api/v1/knowledge-bases/{env.kb["bob"]}' + suffix.format(doc=env.doc['bob'], conv=env.conv['bob'])
    response = env.client.request(method, path)
    assert response.status_code == 404, response.text


def test_foreign_child_cannot_be_accessed_under_own_parent(env):
    login(env)
    response = env.client.get(f'/api/v1/knowledge-bases/{env.kb["alice"]}/documents/{env.doc["bob"]}')
    assert response.status_code == 404


def test_administrator_has_no_implicit_content_access(env):
    login(env, 'admin')
    assert env.client.get(f'/api/v1/knowledge-bases/{env.kb["alice"]}').status_code == 404
    accounts = env.client.get('/api/v1/admin/users')
    assert accounts.status_code == 200
    assert 'password_hash' not in accounts.text and 'alice-secret' not in accounts.text


def test_normal_user_cannot_manage_accounts_or_register(env):
    login(env)
    for method, path in [('get','/admin/users'), ('post','/admin/users'), ('get','/admin/audit-logs'),
                         ('patch', f'/admin/users/{env.ids["bob"]}/status'), ('post', f'/admin/users/{env.ids["bob"]}/password')]:
        assert env.client.request(method, '/api/v1' + path).status_code == 403
    assert env.client.post('/api/v1/auth/register').status_code == 404


def test_admin_create_reset_disable_and_audit(env):
    login(env, 'admin')
    response = env.client.post('/api/v1/admin/users', json={'username': 'charlie', 'temporary_password': PASSWORD})
    assert response.status_code == 201
    assert response.json()['role'] == 'user' and response.json()['must_change_password']
    assert env.client.post('/api/v1/admin/users', json={'username':'eve', 'temporary_password':PASSWORD, 'role':'admin'}).status_code == 422
    # A genuine user's cookie must become unusable after reset/disable.
    login(env, 'bob')
    bob_cookie = env.client.cookies.get('aka_session')
    login(env, 'admin')
    target = env.ids['bob']
    assert env.client.post(f'/api/v1/admin/users/{target}/password', json={'admin_password':'wrong', 'temporary_password':NEW_PASSWORD}).status_code == 403
    assert env.client.post(f'/api/v1/admin/users/{target}/password', json={'admin_password':PASSWORD, 'temporary_password':NEW_PASSWORD}).status_code == 204
    with TestClient(env.app) as other:
        other.cookies.set('aka_session', bob_cookie)
        assert other.get('/api/v1/auth/me').status_code == 401
    assert env.client.patch(f'/api/v1/admin/users/{target}/status', json={'admin_password':PASSWORD, 'is_active':False}).status_code == 200
    assert env.client.patch(f'/api/v1/admin/users/{env.ids["admin"]}/status', json={'admin_password':PASSWORD, 'is_active':False}).status_code == 403
    logs = env.client.get('/api/v1/admin/audit-logs').text
    assert PASSWORD not in logs and NEW_PASSWORD not in logs and 'password_hash' not in logs
    assert 'reset_password' in logs and 'disable_user' in logs
    with env.factory() as db:
        assert db.get(Document, env.doc['bob']) is not None


def test_login_limit_expiration_and_password_input_redaction(env):
    for _ in range(10):
        assert env.client.post('/api/v1/auth/login', json={'username':'alice', 'password':'wrong'}).status_code == 401
    assert env.client.post('/api/v1/auth/login', json={'username':'alice', 'password':PASSWORD}).status_code == 429
    login(env, 'bob')
    with env.factory() as db:
        for session in db.scalars(select(UserSession)):
            session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert env.client.get('/api/v1/auth/me').status_code == 401
    response = env.client.post('/api/v1/auth/login', json={'username':'bob', 'password': PASSWORD * 30})
    assert response.status_code == 422 and PASSWORD not in response.text


def test_zero_ai_quota_and_legacy_processing_endpoints(env):
    login(env)
    with env.factory() as db:
        db.get(User, env.ids['alice']).daily_ai_limit = 0
        db.commit()
    response = env.client.post(f'/api/v1/knowledge-bases/{env.kb["alice"]}/answer', json={'question':'hello'})
    assert response.status_code == 429
    for suffix in ['process', 'process/mineru', 'process/mineru/refresh']:
        response = env.client.post(f'/api/v1/knowledge-bases/{env.kb["alice"]}/documents/{env.doc["alice"]}/{suffix}')
        assert response.status_code == 409


def test_storage_limit_and_processing_admission(env):
    from app.services.quotas import reserve_ai_request, upload_budget
    from fastapi import HTTPException
    with env.factory() as db:
        scope_session(db, env.ids['alice'])
        user = db.get(User, env.ids['alice'])
        user.storage_limit_mb = 0
        db.commit()
        with pytest.raises(HTTPException) as error:
            upload_budget(db)
        assert error.value.status_code == 413
        db.rollback()
        user.processing_limit = 1
        db.get(Document, env.doc['alice']).status = 'processing'
        db.commit()
        with pytest.raises(HTTPException) as error:
            reserve_ai_request(db, processing_document_id=uuid4())
        assert error.value.status_code == 429
        db.rollback()
        reserve_ai_request(db, processing_document_id=env.doc['alice'])
        db.commit()
        assert user.ai_usage_count == 1


def test_invalid_ai_payload_is_not_charged_and_cookie_secure_flag(env, monkeypatch):
    login(env)
    response = env.client.post(f'/api/v1/knowledge-bases/{env.kb["alice"]}/answer', json={})
    assert response.status_code == 422
    with env.factory() as db:
        assert db.get(User, env.ids['alice']).ai_usage_count == 0
    from app.core.config import settings
    monkeypatch.setattr(settings, 'auth_cookie_secure', True)
    assert 'Secure' in login(env).headers['set-cookie']


def test_upload_size_and_storage_quota_cleanup(env, tmp_path, monkeypatch):
    from app.api.routes.documents import document_service
    from app.services.document_storage import DocumentStorageService
    storage_path = tmp_path / 'uploads'
    monkeypatch.setattr(document_service, 'storage_service', DocumentStorageService(storage_path=storage_path))
    login(env)
    with env.factory() as db:
        user = db.get(User, env.ids['alice'])
        user.storage_limit_mb = 1
        user.upload_limit_mb = 1
        db.commit()
    # One hundred bytes are already used by Alice, Bob's files must not count.
    path = f'/api/v1/knowledge-bases/{env.kb["alice"]}/documents'
    denied = env.client.post(path, files={'file': ('big.txt', b'x' * 1048576, 'text/plain')})
    assert denied.status_code == 413
    assert not list(storage_path.iterdir())
    accepted = env.client.post(path, files={'file': ('small.txt', b'small test document', 'text/plain')})
    assert accepted.status_code == 201
    with env.factory() as db:
        scope_session(db, env.ids['alice'])
        assert len(list(db.scalars(select(Document)))) == 2


def test_stale_processing_rows_do_not_block_recovery_slots(env):
    from app.services.quotas import reserve_ai_request
    with env.factory() as db:
        scope_session(db, env.ids['alice'])
        db.get(User, env.ids['alice']).processing_limit = 1
        db.get(Document, env.doc['alice']).status = 'processing'
        db.commit()
        reserve_ai_request(db, processing_document_id=uuid4(), active_document_ids=lambda: ())
        db.commit()
        assert db.get(User, env.ids['alice']).ai_usage_count == 1


def test_old_tab_cannot_read_new_cookie_identity(env):
    login(env, 'bob')
    response = env.client.get('/api/v1/knowledge-bases', headers={'X-Account-ID': str(env.ids['alice'])})
    assert response.status_code == 401
    assert 'shared-name' not in response.text
