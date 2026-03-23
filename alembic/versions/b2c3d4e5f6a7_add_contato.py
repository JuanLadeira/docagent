"""add contato table and atendimento fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contato",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("notas", sa.Text, nullable=True),
        sa.Column("instancia_id", sa.Integer, nullable=False),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("numero", "tenant_id", "instancia_id", name="uq_contato_numero_tenant_instancia"),
        sa.ForeignKeyConstraint(["instancia_id"], ["whatsapp_instancia.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_contato_tenant", "contato", ["tenant_id"])

    # SQLite does not support ADD COLUMN with FK constraints via ALTER TABLE.
    # FKs are declared at ORM level; SQLite doesn't enforce them anyway.
    op.add_column("atendimento", sa.Column("contato_id", sa.Integer, nullable=True))
    op.add_column(
        "atendimento",
        sa.Column("prioridade", sa.String(10), nullable=False, server_default="NORMAL"),
    )


def downgrade() -> None:
    op.drop_column("atendimento", "prioridade")
    op.drop_column("atendimento", "contato_id")
    op.drop_index("ix_contato_tenant", table_name="contato")
    op.drop_table("contato")
