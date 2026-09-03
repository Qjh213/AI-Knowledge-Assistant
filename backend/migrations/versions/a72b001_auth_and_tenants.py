"""Accounts, sessions, audit and ownership. Existing data stays with bootstrap admin."""
from alembic import op
import sqlalchemy as sa
from datetime import UTC, datetime
from uuid import UUID

revision = 'a72b001'
down_revision = '6fdd145e1b8c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=False),
        sa.Column('storage_limit_mb', sa.Integer(), nullable=False),
        sa.Column('upload_limit_mb', sa.Integer(), nullable=False),
        sa.Column('processing_limit', sa.Integer(), nullable=False),
        sa.Column('daily_ai_limit', sa.Integer(), nullable=False),
        sa.Column('ai_usage_day', sa.String(10), nullable=False),
        sa.Column('ai_usage_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'user')", name='user_role'),
        sa.CheckConstraint('storage_limit_mb >= 0 AND upload_limit_mb >= 1 AND processing_limit >= 1 AND daily_ai_limit >= 0', name='user_limits'),
    )
    # Intentionally unusable password; activation is an interactive CLI step.
    users = sa.table('users', *[sa.column(n, t) for n, t in [
        ('id', sa.Uuid()), ('username', sa.String()), ('password_hash', sa.String()),
        ('role', sa.String()), ('is_active', sa.Boolean()), ('must_change_password', sa.Boolean()),
        ('storage_limit_mb', sa.Integer()), ('upload_limit_mb', sa.Integer()),
        ('processing_limit', sa.Integer()), ('daily_ai_limit', sa.Integer()),
        ('ai_usage_day', sa.String()), ('ai_usage_count', sa.Integer()),
        ('created_at', sa.DateTime()), ('updated_at', sa.DateTime()),
    ]])
    admin_id = UUID('00000000-0000-4000-8000-000000000001')
    op.bulk_insert(users, [dict(id=admin_id, username='admin', password_hash='!', role='admin',
        is_active=False, must_change_password=False, storage_limit_mb=10240, upload_limit_mb=100,
        processing_limit=3, daily_ai_limit=1000, ai_usage_day='', ai_usage_count=0,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC))])
    op.add_column('knowledge_bases', sa.Column('owner_id', sa.Uuid(), nullable=True))
    op.execute(sa.text('UPDATE knowledge_bases SET owner_id = :owner').bindparams(owner=admin_id))
    op.alter_column('knowledge_bases', 'owner_id', nullable=False)
    op.create_foreign_key('fk_knowledge_bases_owner_id_users', 'knowledge_bases', 'users', ['owner_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_knowledge_bases_owner_id', 'knowledge_bases', ['owner_id'])
    op.drop_index('ix_knowledge_bases_name', table_name='knowledge_bases')
    op.create_index('ix_knowledge_bases_name', 'knowledge_bases', ['name'])
    op.create_unique_constraint('uq_knowledge_bases_owner_name', 'knowledge_bases', ['owner_id', 'name'])
    op.create_table('user_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_expires_at', 'user_sessions', ['expires_at'])
    op.create_table('audit_logs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('target_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('outcome', sa.String(16), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_table('auth_throttles', sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('window', sa.Integer(), nullable=False), sa.Column('hits', sa.Integer(), nullable=False))


def downgrade():
    raise RuntimeError('Ownership downgrade is intentionally blocked. Restore a verified pre-upgrade backup instead.')
