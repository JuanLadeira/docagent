"""add auth_type to mcp_server

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mcp_server") as batch_op:
        batch_op.add_column(
            sa.Column("auth_type", sa.String(20), nullable=False, server_default="none")
        )


def downgrade() -> None:
    with op.batch_alter_table("mcp_server") as batch_op:
        batch_op.drop_column("auth_type")
