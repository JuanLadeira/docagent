"""add candidatura_simplificada to vagas and simplificada to candidaturas

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'vagas',
        sa.Column('candidatura_simplificada', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'candidaturas',
        sa.Column('simplificada', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('vagas', 'candidatura_simplificada')
    op.drop_column('candidaturas', 'simplificada')
