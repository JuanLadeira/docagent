"""convert atendimento columns to native PostgreSQL enum types

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

canalatendimento = sa.Enum('WHATSAPP', 'TELEGRAM', name='canalatendimento')
atendimentostatus = sa.Enum('ATIVO', 'HUMANO', 'ENCERRADO', name='atendimentostatus')
prioridade_enum = sa.Enum('BAIXA', 'NORMAL', 'ALTA', 'URGENTE', name='prioridade')
mensagemorigem = sa.Enum('CLIENTE', 'AGENTE', 'OPERADOR', name='mensagemorigem')


def upgrade() -> None:
    bind = op.get_bind()

    canalatendimento.create(bind, checkfirst=True)
    atendimentostatus.create(bind, checkfirst=True)
    prioridade_enum.create(bind, checkfirst=True)
    mensagemorigem.create(bind, checkfirst=True)

    # Dropar server defaults antes de converter (PostgreSQL não faz cast automático)
    op.execute("ALTER TABLE atendimento ALTER COLUMN canal DROP DEFAULT")
    op.execute("ALTER TABLE atendimento ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE atendimento ALTER COLUMN prioridade DROP DEFAULT")
    op.execute("ALTER TABLE mensagem_atendimento ALTER COLUMN origem DROP DEFAULT")

    op.execute("""
        ALTER TABLE atendimento
            ALTER COLUMN canal TYPE canalatendimento USING canal::canalatendimento,
            ALTER COLUMN status TYPE atendimentostatus USING status::atendimentostatus,
            ALTER COLUMN prioridade TYPE prioridade USING prioridade::prioridade
    """)

    op.execute("""
        ALTER TABLE mensagem_atendimento
            ALTER COLUMN origem TYPE mensagemorigem USING origem::mensagemorigem
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE mensagem_atendimento ALTER COLUMN origem TYPE VARCHAR(20) USING origem::text")
    op.execute("""
        ALTER TABLE atendimento
            ALTER COLUMN prioridade TYPE VARCHAR(10) USING prioridade::text,
            ALTER COLUMN status TYPE VARCHAR(20) USING status::text,
            ALTER COLUMN canal TYPE VARCHAR(20) USING canal::text
    """)

    bind = op.get_bind()
    mensagemorigem.drop(bind, checkfirst=True)
    prioridade_enum.drop(bind, checkfirst=True)
    atendimentostatus.drop(bind, checkfirst=True)
    canalatendimento.drop(bind, checkfirst=True)
