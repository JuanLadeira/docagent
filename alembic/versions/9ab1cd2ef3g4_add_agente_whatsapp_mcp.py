"""add agente, whatsapp_instancia e mcp tables

Revision ID: 9ab1cd2ef3g4
Revises: 8fa0cf79480e
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9ab1cd2ef3g4'
down_revision: Union[str, None] = '8fa0cf79480e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agente
    op.create_table(
        'agente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(100), nullable=False),
        sa.Column('descricao', sa.String(500), nullable=False, server_default=''),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('skill_names', sa.JSON(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # documento
    op.create_table(
        'documento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agente_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('chunks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['agente_id'], ['agente.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # whatsapp_instancia
    op.create_table(
        'whatsapp_instancia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instance_name', sa.String(100), nullable=False),
        sa.Column(
            'status',
            sa.Enum('CRIADA', 'CONECTANDO', 'CONECTADA', 'DESCONECTADA', name='conexaostatus'),
            nullable=False,
            server_default='CRIADA',
        ),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agente_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agente_id'], ['agente.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instance_name'),
    )
    op.create_index('ix_whatsapp_instancia_instance_name', 'whatsapp_instancia', ['instance_name'])

    # mcp_server
    op.create_table(
        'mcp_server',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(255), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False, server_default=''),
        sa.Column('command', sa.String(255), nullable=False),
        sa.Column('args', sa.JSON(), nullable=False),
        sa.Column('env', sa.JSON(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # mcp_tool
    op.create_table(
        'mcp_tool',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['server_id'], ['mcp_server.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('mcp_tool')
    op.drop_table('mcp_server')
    op.drop_index('ix_whatsapp_instancia_instance_name', table_name='whatsapp_instancia')
    op.drop_table('whatsapp_instancia')
    op.drop_table('documento')
    op.drop_table('agente')
    op.execute("DROP TYPE IF EXISTS conexaostatus")
