"""add transport and url to mcp_server

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_server",
        sa.Column("transport", sa.String(10), nullable=False, server_default="stdio"),
    )
    op.add_column(
        "mcp_server",
        sa.Column("url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_server", "url")
    op.drop_column("mcp_server", "transport")
