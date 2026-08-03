"""ingestion jobs table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ingestion_job_status = sa.Enum(
    'pending', 'processing', 'completed', 'failed', name='ingestion_job_status',
)


def upgrade() -> None:
    ingestion_job_status.create(op.get_bind())
    op.create_table(
        'ingestion_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('status', ingestion_job_status, nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ingestion_jobs_org_id'), 'ingestion_jobs', ['org_id'])
    op.create_index(op.f('ix_ingestion_jobs_document_id'), 'ingestion_jobs', ['document_id'])
    # The claim query filters on (status, next_attempt_at); the reaper
    # filters on (status, claimed_at). Composite indexes matching both.
    op.create_index('ix_ingestion_jobs_claim', 'ingestion_jobs', ['status', 'next_attempt_at'])
    op.create_index('ix_ingestion_jobs_reap', 'ingestion_jobs', ['status', 'claimed_at'])


def downgrade() -> None:
    op.drop_index('ix_ingestion_jobs_reap', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_claim', table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_document_id'), table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_org_id'), table_name='ingestion_jobs')
    op.drop_table('ingestion_jobs')
    ingestion_job_status.drop(op.get_bind())
