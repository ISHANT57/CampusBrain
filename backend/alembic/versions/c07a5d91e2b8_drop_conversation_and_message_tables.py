"""drop conversation and message tables

Revision ID: c07a5d91e2b8
Revises: b3e1f0a72c44
Create Date: 2026-07-22 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c07a5d91e2b8'
down_revision: Union[str, None] = 'b3e1f0a72c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Students now chat anonymously, so there is no user row to own a
    # conversation and no server-side transcript at all — the browser keeps
    # the history it already kept in localStorage and replays recent turns
    # with each question. These two tables have no remaining writer.
    #
    # DESTRUCTIVE: any stored transcript is gone. Safe on this deploy (student
    # self-registration was broken from day one, so no user — and therefore no
    # conversation — ever existed); check `select count(*) from messages`
    # before running this anywhere that had working accounts.
    op.drop_index('ix_messages_org_id', table_name='messages')
    op.drop_index('ix_messages_conversation_id', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_conversations_user_id', table_name='conversations')
    op.drop_index('ix_conversations_org_id', table_name='conversations')
    op.drop_table('conversations')
    # drop_table leaves the Postgres enum type behind — and a leftover
    # message_role type would collide with the CREATE TYPE that downgrade's
    # sa.Enum issues if this migration is ever rolled back and re-applied.
    op.execute('DROP TYPE IF EXISTS message_role')


def downgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversations_org_id', 'conversations', ['org_id'], unique=False)
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'], unique=False)
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column(
            'role',
            sa.Enum('user', 'assistant', name='message_role'),
            nullable=False,
        ),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)
    op.create_index('ix_messages_org_id', 'messages', ['org_id'], unique=False)
