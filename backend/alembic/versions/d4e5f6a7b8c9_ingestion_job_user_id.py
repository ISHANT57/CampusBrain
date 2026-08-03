"""ingestion_jobs.user_id

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: tools/ingest.py creates jobs with no uploading user at all
    # (a CLI run has no "user" to attribute to), and that's an honest state,
    # not a missing value.
    op.add_column('ingestion_jobs', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_ingestion_jobs_user_id', 'ingestion_jobs', 'users', ['user_id'], ['id'],
    )
    op.create_index(op.f('ix_ingestion_jobs_user_id'), 'ingestion_jobs', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_ingestion_jobs_user_id'), table_name='ingestion_jobs')
    op.drop_constraint('fk_ingestion_jobs_user_id', 'ingestion_jobs', type_='foreignkey')
    op.drop_column('ingestion_jobs', 'user_id')
