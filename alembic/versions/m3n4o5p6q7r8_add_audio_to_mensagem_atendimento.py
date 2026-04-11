"""add tipo e media_ref to mensagem_atendimento

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'mensagem_atendimento',
        sa.Column('tipo', sa.String(10), nullable=False, server_default='text'),
    )
    op.add_column(
        'mensagem_atendimento',
        sa.Column('media_ref', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('mensagem_atendimento', 'media_ref')
    op.drop_column('mensagem_atendimento', 'tipo')
