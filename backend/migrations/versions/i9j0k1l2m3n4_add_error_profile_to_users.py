"""add error_profile to users

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-11

오탈자 개인 오답노트(error_profile) 컬럼. voice_profile과 동일하게 JSON nullable.
"""
from alembic import op
import sqlalchemy as sa

revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('error_profile', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'error_profile')
