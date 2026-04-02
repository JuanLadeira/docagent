"""add assumido_por to atendimento

Revision ID: a3b4c5d6e7f8
Revises: f6a7b8c9d0e1
Create Date: 2026-03-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('atendimento', sa.Column('assumido_por_id', sa.Integer(), nullable=True))
    op.add_column('atendimento', sa.Column('assumido_por_nome', sa.String(100), nullable=True))
    op.create_foreign_key(
        'fk_atendimento_assumido_por_id',
        'atendimento', 'usuario',
        ['assumido_por_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_atendimento_assumido_por_id', 'atendimento', type_='foreignkey')
    op.drop_column('atendimento', 'assumido_por_nome')
    op.drop_column('atendimento', 'assumido_por_id')
