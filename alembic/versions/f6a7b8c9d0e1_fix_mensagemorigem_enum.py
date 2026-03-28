"""fix mensagemorigem enum: add CONTATO value

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migration d4e5f6a7b8c9 created the enum with ('CLIENTE', 'AGENTE', 'OPERADOR')
    # but the model MensagemOrigem uses CONTATO (not CLIENTE).
    # PostgreSQL allows adding values to an existing enum with ALTER TYPE ... ADD VALUE.
    op.execute("ALTER TYPE mensagemorigem ADD VALUE IF NOT EXISTS 'CONTATO'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type without recreating it.
    # Downgrade is a no-op — CONTATO will remain in the type.
    pass
