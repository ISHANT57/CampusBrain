"""document content_hash

Revision ID: 9a1c4e7b2d18
Revises: 7642de34db53
Create Date: 2026-07-22 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1c4e7b2d18'
down_revision: Union[str, None] = '7642de34db53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: every document uploaded through the API before this migration
    # has no hash, and backfilling would mean re-reading every blob from
    # object storage. Only the ingestion tool sets it, and only the ingestion
    # tool reads it for dedup — an API upload leaving it NULL is expected, not
    # a broken row.
    op.add_column('documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    # Dedup does `WHERE org_id = ? AND content_hash = ?` once per file per run;
    # over hundreds of documents that's a seq scan per lookup without this.
    op.create_index(
        'ix_documents_org_content_hash', 'documents', ['org_id', 'content_hash'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_documents_org_content_hash', table_name='documents')
    op.drop_column('documents', 'content_hash')
