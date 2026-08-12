"""audit_logs.user_id nullable

Revision ID: f3a1b2c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-12 00:00:00.000000

The column was created NOT NULL for the original admin-only audit trail
(migration a1b2c3d4e5f6) and never relaxed when /search's audit logging was
added on top of it. SearchPrincipal.user_id (app/core/dependencies.py) is
documented as None for a service-API-key caller — there is no user row to
attribute a machine call to — so every service-key search call has been
inserting a NULL into a NOT NULL column and 500ing on the IntegrityError.

A plain ALTER COLUMN ... DROP NOT NULL: no table rewrite, no data loss,
existing rows (which all have a real user_id) are unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1b2c4d5e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('audit_logs', 'user_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column('audit_logs', 'user_id', existing_type=sa.Integer(), nullable=False)
