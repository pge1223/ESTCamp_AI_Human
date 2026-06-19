"""add_illustrations_table

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-06-14

세션별 삽화 저장(이미지 base64 data URL + 장면 설명 caption).
다른 기기/계정에서도 보이도록 DB 영속(localStorage 대체).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'illustrations',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_illustrations_session_id', 'illustrations', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_illustrations_session_id', table_name='illustrations')
    op.drop_table('illustrations')
