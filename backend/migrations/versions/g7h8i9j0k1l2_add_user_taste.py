"""add_user_chat_taste

Revision ID: g7h8i9j0k1l2
Revises: f1a2b3c4d5e6
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_chat_taste',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chat_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('works', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('taste_profile', postgresql.JSONB(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_taste'),
    )
    op.create_index('ix_user_chat_taste_user_id', 'user_chat_taste', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_chat_taste_user_id', table_name='user_chat_taste')
    op.drop_table('user_chat_taste')
