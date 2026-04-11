"""add conversa e mensagem_conversa

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'conversa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('agente_id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(200), nullable=True),
        sa.Column('arquivada', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agente_id'], ['agente.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversa_usuario_updated', 'conversa', ['usuario_id', 'updated_at'])

    op.create_table(
        'mensagem_conversa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversa_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('tool_name', sa.String(100), nullable=True),
        sa.Column('tokens_entrada', sa.Integer(), nullable=True),
        sa.Column('tokens_saida', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['conversa_id'], ['conversa.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mensagem_conversa_id', 'mensagem_conversa', ['conversa_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_mensagem_conversa_id', table_name='mensagem_conversa')
    op.drop_table('mensagem_conversa')
    op.drop_index('ix_conversa_usuario_updated', table_name='conversa')
    op.drop_table('conversa')
