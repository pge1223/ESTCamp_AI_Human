"""add speaker to dialogues

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dialogues', sa.Column('speaker', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('dialogues', 'speaker')
