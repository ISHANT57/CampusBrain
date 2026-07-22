"""seed default organization

Revision ID: b3e1f0a72c44
Revises: 9a1c4e7b2d18
Create Date: 2026-07-22 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3e1f0a72c44'
down_revision: Union[str, None] = '9a1c4e7b2d18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.org_id is a FK to organizations.id, and nothing in the API creates
    # an organization — so on a fresh database (Neon, on the Render deploy)
    # every self-registration was a FK violation surfacing as an opaque 500.
    # Seeding org 1 here rather than by hand in the SQL console means any
    # future fresh DB self-heals: render-start.sh already runs
    # `alembic upgrade head` on every boot.
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, created_at, updated_at)
        VALUES (1, 'Default Organization', 'default', now(), now())
        ON CONFLICT (id) DO NOTHING
        """
    )
    # Explicit id=1 bypasses the identity sequence, which would still hand out
    # 1 to the next real organization and collide. Fast-forward it past the
    # rows that now exist.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('organizations', 'id'), "
        "(SELECT max(id) FROM organizations))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM organizations WHERE slug = 'default'")
