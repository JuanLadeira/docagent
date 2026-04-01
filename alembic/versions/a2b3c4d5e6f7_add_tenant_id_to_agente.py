"""add tenant_id to agente

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adiciona nullable primeiro para não quebrar linhas existentes
    op.add_column('agente', sa.Column('tenant_id', sa.Integer(), nullable=True))

    # Atribui todos os agentes existentes ao primeiro tenant (seed padrão)
    op.execute("UPDATE agente SET tenant_id = (SELECT id FROM tenant ORDER BY id LIMIT 1)")

    # Torna NOT NULL após preencher
    op.alter_column('agente', 'tenant_id', nullable=False)

    op.create_index('ix_agente_tenant_id', 'agente', ['tenant_id'])
    op.create_foreign_key(
        'fk_agente_tenant_id', 'agente', 'tenant', ['tenant_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_agente_tenant_id', 'agente', type_='foreignkey')
    op.drop_index('ix_agente_tenant_id', table_name='agente')
    op.drop_column('agente', 'tenant_id')
