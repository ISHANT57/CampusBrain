"""usage logs table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('operation', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_usage_logs_org_id'), 'usage_logs', ['org_id'])
    op.create_index(op.f('ix_usage_logs_user_id'), 'usage_logs', ['user_id'])
    op.create_index(op.f('ix_usage_logs_document_id'), 'usage_logs', ['document_id'])
    op.create_index(op.f('ix_usage_logs_request_id'), 'usage_logs', ['request_id'])
    op.create_index(op.f('ix_usage_logs_created_at'), 'usage_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_usage_logs_created_at'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_request_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_document_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_user_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_org_id'), table_name='usage_logs')
    op.drop_table('usage_logs')
