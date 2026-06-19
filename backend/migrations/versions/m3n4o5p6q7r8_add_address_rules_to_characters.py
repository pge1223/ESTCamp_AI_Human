"""add address_rules to characters

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('characters', sa.Column('address_rules', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('characters', 'address_rules')
