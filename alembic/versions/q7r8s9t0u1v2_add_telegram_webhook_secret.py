"""add webhook_secret to telegram_instancia (Fase 21e)

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa


revision = 'q7r8s9t0u1v2'
down_revision = 'p6q7r8s9t0u1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("telegram_instancia") as batch_op:
        batch_op.add_column(
            sa.Column("webhook_secret", sa.String(100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("telegram_instancia") as batch_op:
        batch_op.drop_column("webhook_secret")
