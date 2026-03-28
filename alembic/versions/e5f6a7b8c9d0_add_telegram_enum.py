"""convert telegram_instancia.status to native PostgreSQL enum

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

telegrambotstatus = sa.Enum('ATIVA', 'INATIVA', name='telegrambotstatus')


def upgrade() -> None:
    bind = op.get_bind()
    telegrambotstatus.create(bind, checkfirst=True)

    op.execute("ALTER TABLE telegram_instancia ALTER COLUMN status DROP DEFAULT")
    op.execute("""
        ALTER TABLE telegram_instancia
            ALTER COLUMN status TYPE telegrambotstatus
            USING status::telegrambotstatus
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE telegram_instancia ALTER COLUMN status TYPE VARCHAR(10) USING status::text"
    )
    bind = op.get_bind()
    telegrambotstatus.drop(bind, checkfirst=True)
