"""add_assinatura_e_campos_plano

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-01

Fase 17 — Billing & Quotas:
- Adiciona colunas limite_agentes e ciclo_dias ao modelo planos
- Cria tabela assinatura (1:1 com tenant, FK para planos)
"""
from alembic import op
import sqlalchemy as sa

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Novos campos no Plano
    op.add_column("planos", sa.Column("limite_agentes", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("planos", sa.Column("ciclo_dias", sa.Integer(), nullable=False, server_default="30"))

    # Tabela Assinatura
    op.create_table(
        "assinatura",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("data_inicio", sa.DateTime(), nullable=False),
        sa.Column("data_proxima_renovacao", sa.DateTime(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"]),
        sa.UniqueConstraint("tenant_id", name="uq_assinatura_tenant"),
    )


def downgrade() -> None:
    op.drop_table("assinatura")
    op.drop_column("planos", "ciclo_dias")
    op.drop_column("planos", "limite_agentes")
