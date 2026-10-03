"""add documents table and harness_sessions.document_id

Revision ID: a1b2c3d4e5f6
Revises: ec5b9364608a
Create Date: 2026-06-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ec5b9364608a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('file_data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_documents_project_id', 'documents', ['project_id'])

    # Clean slate: existing sessions have no Document and their temp PDFs are gone.
    op.execute('TRUNCATE harness_sessions CASCADE')

    op.add_column('harness_sessions', sa.Column('document_id', UUID(as_uuid=True), nullable=False))
    op.create_index('ix_harness_sessions_document_id', 'harness_sessions', ['document_id'])
    op.create_foreign_key(
        'fk_harness_sessions_document_id', 'harness_sessions', 'documents',
        ['document_id'], ['id'], ondelete='CASCADE',
    )
    op.drop_column('harness_sessions', 'input_file_path')


def downgrade() -> None:
    op.add_column('harness_sessions', sa.Column('input_file_path', sa.String(length=1000), nullable=True))
    op.drop_constraint('fk_harness_sessions_document_id', 'harness_sessions', type_='foreignkey')
    op.drop_index('ix_harness_sessions_document_id', table_name='harness_sessions')
    op.drop_column('harness_sessions', 'document_id')
    op.drop_index('ix_documents_project_id', table_name='documents')
    op.drop_table('documents')
