"""add glossary to worlds

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-06-13

맞춤법 교정 보호 용어집(glossary) 컬럼. tags와 동일하게 JSON nullable.
자동 추출(LLM) + 사용자 '넘기기' 누적용. None=미추출, []=추출했으나 없음.
"""
from alembic import op
import sqlalchemy as sa

revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('worlds', sa.Column('glossary', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('worlds', 'glossary')
