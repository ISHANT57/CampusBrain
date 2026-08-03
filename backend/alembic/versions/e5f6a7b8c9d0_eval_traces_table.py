"""eval traces table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'eval_traces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('retrieval_query', sa.Text(), nullable=False),
        sa.Column('retrieved_chunk_ids', sa.Text(), nullable=False, server_default=''),
        sa.Column('retrieved_scores', sa.Text(), nullable=False, server_default=''),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('cited_chunk_ids', sa.Text(), nullable=False, server_default=''),
        sa.Column('refused', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('best_semantic_score', sa.Float(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('retrieval_ms', sa.Integer(), nullable=True),
        sa.Column('llm_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_eval_traces_org_id'), 'eval_traces', ['org_id'])
    op.create_index(op.f('ix_eval_traces_request_id'), 'eval_traces', ['request_id'])
    op.create_index(op.f('ix_eval_traces_created_at'), 'eval_traces', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_eval_traces_created_at'), table_name='eval_traces')
    op.drop_index(op.f('ix_eval_traces_request_id'), table_name='eval_traces')
    op.drop_index(op.f('ix_eval_traces_org_id'), table_name='eval_traces')
    op.drop_table('eval_traces')
