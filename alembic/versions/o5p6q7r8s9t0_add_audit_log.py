"""add audit_log table (Fase 21c)

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa


revision = 'o5p6q7r8s9t0'
down_revision = 'n4o5p6q7r8s9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "actor_tipo",
            sa.Enum("admin", "usuario", name="actortipo"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer, nullable=False),
        sa.Column("actor_username", sa.String(100), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer,
            sa.ForeignKey("tenant.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acao", sa.String(100), nullable=False),
        sa.Column("recurso_tipo", sa.String(50), nullable=True),
        sa.Column("recurso_id", sa.Integer, nullable=True),
        sa.Column("dados_antes", sa.JSON, nullable=True),
        sa.Column("dados_depois", sa.JSON, nullable=True),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_acao", "audit_log", ["acao"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", "audit_log")
    op.drop_index("ix_audit_log_acao", "audit_log")
    op.drop_index("ix_audit_log_tenant_id", "audit_log")
    op.drop_index("ix_audit_log_actor_id", "audit_log")
    op.drop_table("audit_log")
    op.execute("DROP TYPE IF EXISTS actortipo")
