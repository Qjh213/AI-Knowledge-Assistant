"""add document parser task fields

Revision ID: cee4d772f766
Revises: 0be292f48fe9
Create Date: 2026-08-31 01:30:58.252244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cee4d772f766'
down_revision: Union[str, Sequence[str], None] = '0be292f48fe9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_parser_enum = postgresql.ENUM(
    'local',
    'mineru',
    name='document_parser',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    document_parser_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'documents',
        sa.Column(
            'parser',
            document_parser_enum,
            server_default='local',
            nullable=False,
        ),
    )
    op.add_column('documents', sa.Column('external_task_id', sa.String(length=128), nullable=True))
    op.add_column(
        'documents',
        sa.Column(
            'processing_progress',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
    )
    op.create_index(op.f('ix_documents_external_task_id'), 'documents', ['external_task_id'], unique=False)
    op.create_check_constraint(
        op.f('ck_documents_processing_progress_range'),
        'documents',
        'processing_progress >= 0 AND processing_progress <= 100',
    )
    op.alter_column('documents', 'parser', server_default=None)
    op.alter_column('documents', 'processing_progress', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f('ck_documents_processing_progress_range'),
        'documents',
        type_='check',
    )
    op.drop_index(op.f('ix_documents_external_task_id'), table_name='documents')
    op.drop_column('documents', 'processing_progress')
    op.drop_column('documents', 'external_task_id')
    op.drop_column('documents', 'parser')
    document_parser_enum.drop(op.get_bind(), checkfirst=True)
