"""add candidato cv_texto

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'candidatos',
        sa.Column('cv_texto', sa.Text(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('candidatos', 'cv_texto')
