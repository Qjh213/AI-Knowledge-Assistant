from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin

LEGACY_ADMIN_ID = UUID('00000000-0000-4000-8000-000000000001')


class User(TimestampMixin, Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name='user_role'),
        CheckConstraint('storage_limit_mb >= 0 AND upload_limit_mb >= 1 AND processing_limit >= 1 AND daily_ai_limit >= 0', name='user_limits'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default='user', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    upload_limit_mb: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    processing_limit: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    daily_ai_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    ai_usage_day: Mapped[str] = mapped_column(String(10), default='', nullable=False)
    ai_usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserSession(Base):
    __tablename__ = 'user_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default='success')
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthThrottle(Base):
    __tablename__ = 'auth_throttles'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
