"""add totp fields to admin (Fase 21d)

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa


revision = 'p6q7r8s9t0u1'
down_revision = 'o5p6q7r8s9t0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin") as batch_op:
        batch_op.add_column(
            sa.Column("totp_secret", sa.String(700), nullable=True)
        )
        batch_op.add_column(
            sa.Column("totp_habilitado", sa.Boolean, nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("admin") as batch_op:
        batch_op.drop_column("totp_habilitado")
        batch_op.drop_column("totp_secret")
