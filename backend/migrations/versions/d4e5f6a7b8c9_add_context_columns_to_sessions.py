"""add_context_columns_to_sessions

Revision ID: d4e5f6a7b8c9
Revises: 81fac960a2a7
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = '81fac960a2a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('current_state', sa.Text(), nullable=True))
    op.add_column('sessions', sa.Column('story_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'story_summary')
    op.drop_column('sessions', 'current_state')
