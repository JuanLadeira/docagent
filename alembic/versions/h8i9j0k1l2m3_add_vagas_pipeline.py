"""add_vagas_pipeline

Revision ID: h8i9j0k1l2m3
Revises: 02c972d3cdb6
Create Date: 2026-04-04

Fase 17b — Pipeline Multi-Agente de Vagas:
- Cria tabela candidatos
- Cria tabela pipeline_runs
- Cria tabela vagas
- Cria tabela candidaturas
"""
from alembic import op
import sqlalchemy as sa

revision = "h8i9j0k1l2m3"
down_revision = "02c972d3cdb6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidatos",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("telefone", sa.String(50), nullable=False, server_default=""),
        sa.Column("skills", sa.JSON, nullable=False),
        sa.Column("experiencias", sa.JSON, nullable=False),
        sa.Column("formacao", sa.JSON, nullable=False),
        sa.Column("cargo_desejado", sa.String(200), nullable=False, server_default=""),
        sa.Column("resumo", sa.Text, nullable=False, server_default=""),
        sa.Column("cv_filename", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_candidatos_tenant_id", "candidatos", ["tenant_id"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidato_id", sa.Integer, sa.ForeignKey("candidatos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDENTE"),
        sa.Column("etapa_atual", sa.String(100), nullable=False, server_default=""),
        sa.Column("erro", sa.Text, nullable=True),
        sa.Column("vagas_encontradas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("candidaturas_criadas", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_pipeline_runs_tenant_id", "pipeline_runs", ["tenant_id"])

    op.create_table(
        "vagas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False, server_default=""),
        sa.Column("empresa", sa.String(200), nullable=False, server_default=""),
        sa.Column("localizacao", sa.String(200), nullable=False, server_default=""),
        sa.Column("descricao", sa.Text, nullable=False, server_default=""),
        sa.Column("requisitos", sa.Text, nullable=False, server_default=""),
        sa.Column("url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("fonte", sa.String(50), nullable=False, server_default="DUCKDUCKGO"),
        sa.Column("match_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("raw_data", sa.JSON, nullable=False),
    )
    op.create_index("ix_vagas_tenant_id", "vagas", ["tenant_id"])
    op.create_index("ix_vagas_pipeline_run_id", "vagas", ["pipeline_run_id"])

    op.create_table(
        "candidaturas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vaga_id", sa.Integer, sa.ForeignKey("vagas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidato_id", sa.Integer, sa.ForeignKey("candidatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resumo_personalizado", sa.Text, nullable=False, server_default=""),
        sa.Column("carta_apresentacao", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="AGUARDANDO_ENVIO"),
    )
    op.create_index("ix_candidaturas_tenant_id", "candidaturas", ["tenant_id"])
    op.create_index("ix_candidaturas_pipeline_run_id", "candidaturas", ["pipeline_run_id"])


def downgrade() -> None:
    op.drop_table("candidaturas")
    op.drop_table("vagas")
    op.drop_table("pipeline_runs")
    op.drop_table("candidatos")
