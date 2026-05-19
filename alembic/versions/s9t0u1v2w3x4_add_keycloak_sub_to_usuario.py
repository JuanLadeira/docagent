"""add keycloak_sub to usuario

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(
            sa.Column("keycloak_sub", sa.String(255), nullable=True)
        )
        batch_op.create_unique_constraint("uq_usuario_keycloak_sub", ["keycloak_sub"])
        batch_op.create_index("ix_usuario_keycloak_sub", ["keycloak_sub"])


def downgrade() -> None:
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_index("ix_usuario_keycloak_sub")
        batch_op.drop_constraint("uq_usuario_keycloak_sub", type_="unique")
        batch_op.drop_column("keycloak_sub")
