"""add atendimento tables

Revision ID: a1b2c3d4e5f6
Revises: 8fa0cf79480e
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8fa0cf79480e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "atendimento",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("nome_contato", sa.String(100), nullable=True),
        sa.Column(
            "instancia_id",
            sa.Integer,
            sa.ForeignKey("whatsapp_instancia.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Integer,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_atendimento_tenant_status", "atendimento", ["tenant_id", "status"])
    op.create_index("ix_atendimento_instancia_numero", "atendimento", ["instancia_id", "numero"])

    op.create_table(
        "mensagem_atendimento",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "atendimento_id",
            sa.Integer,
            sa.ForeignKey("atendimento.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("conteudo", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_mensagem_atendimento_id", "mensagem_atendimento", ["atendimento_id"])


def downgrade() -> None:
    op.drop_index("ix_mensagem_atendimento_id", table_name="mensagem_atendimento")
    op.drop_table("mensagem_atendimento")
    op.drop_index("ix_atendimento_instancia_numero", table_name="atendimento")
    op.drop_index("ix_atendimento_tenant_status", table_name="atendimento")
    op.drop_table("atendimento")
