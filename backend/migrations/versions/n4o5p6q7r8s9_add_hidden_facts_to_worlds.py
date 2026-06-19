"""add hidden_facts to worlds

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('worlds', sa.Column('hidden_facts', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('worlds', 'hidden_facts')
