"""add_mypage_tables

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Session.updated_at 추가
    op.add_column('sessions', sa.Column(
        'updated_at', sa.DateTime(), nullable=False,
        server_default=sa.func.now()
    ))

    # saved_sentences 테이블 신규 생성
    op.create_table(
        'saved_sentences',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('label', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_saved_sentences_user_id', 'saved_sentences', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_saved_sentences_user_id', table_name='saved_sentences')
    op.drop_table('saved_sentences')
    op.drop_column('sessions', 'updated_at')
