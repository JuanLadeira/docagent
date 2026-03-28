"""add telegram

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Criar tabela telegram_instancia (pode já existir se create_all rodou antes)
    if "telegram_instancia" not in existing_tables:
        op.create_table(
            "telegram_instancia",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("bot_token", sa.String(200), nullable=False),
            sa.Column("bot_username", sa.String(100), nullable=True),
            sa.Column("webhook_configured", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(10), nullable=False, server_default="ATIVA"),
            sa.Column("cria_atendimentos", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("agente_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("bot_token"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["agente_id"], ["agente.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_telegram_instancia_tenant_id", "telegram_instancia", ["tenant_id"])

    # Adicionar colunas ao atendimento apenas se ainda não existirem
    existing_cols = {c["name"] for c in inspector.get_columns("atendimento")}

    # Modificar tabela atendimento — batch_alter_table para SQLite
    needs_batch = (
        "canal" not in existing_cols
        or "telegram_instancia_id" not in existing_cols
    )
    if needs_batch:
        with op.batch_alter_table("atendimento") as batch_op:
            batch_op.alter_column(
                "instancia_id",
                existing_type=sa.Integer(),
                nullable=True,
            )
            if "canal" not in existing_cols:
                batch_op.add_column(
                    sa.Column("canal", sa.String(20), nullable=False, server_default="WHATSAPP")
                )
            if "telegram_instancia_id" not in existing_cols:
                batch_op.add_column(
                    sa.Column("telegram_instancia_id", sa.Integer(), nullable=True)
                )
                batch_op.create_foreign_key(
                    "fk_atendimento_telegram_instancia",
                    "telegram_instancia",
                    ["telegram_instancia_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    with op.batch_alter_table("atendimento") as batch_op:
        batch_op.drop_constraint("fk_atendimento_telegram_instancia", type_="foreignkey")
        batch_op.drop_column("telegram_instancia_id")
        batch_op.drop_column("canal")
        batch_op.alter_column(
            "instancia_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    op.drop_index("ix_telegram_instancia_tenant_id", table_name="telegram_instancia")
    op.drop_table("telegram_instancia")
