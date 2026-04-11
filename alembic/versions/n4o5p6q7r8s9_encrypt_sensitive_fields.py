"""encrypt sensitive fields (Fase 21b)

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-04-11

Aumenta o tamanho das colunas que passam a armazenar valores criptografados
com Fernet. O ciphertext Fernet é ~1.37× o plaintext + overhead base64,
então 500 chars plaintext → ~700 chars ciphertext.

Colunas afetadas:
  - tenant.llm_api_key         String(500) → String(700)
  - audio_config.elevenlabs_api_key  String → String(700)
  - telegram_instancia.bot_token  String(200) → String(700)

NOTA: a re-encriptação dos valores existentes em plaintext é feita pelo
script alembic/scripts/reencrypt_secrets.py, que deve ser rodado manualmente
após o deploy (ou via entrypoint.sh).
"""
from alembic import op
import sqlalchemy as sa


revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.alter_column(
            "llm_api_key",
            existing_type=sa.String(500),
            type_=sa.String(700),
            existing_nullable=True,
        )

    with op.batch_alter_table("audio_config") as batch_op:
        batch_op.alter_column(
            "elevenlabs_api_key",
            existing_type=sa.String(),
            type_=sa.String(700),
            existing_nullable=True,
        )

    with op.batch_alter_table("telegram_instancia") as batch_op:
        batch_op.alter_column(
            "bot_token",
            existing_type=sa.String(200),
            type_=sa.String(700),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("telegram_instancia") as batch_op:
        batch_op.alter_column(
            "bot_token",
            existing_type=sa.String(700),
            type_=sa.String(200),
            existing_nullable=False,
        )

    with op.batch_alter_table("audio_config") as batch_op:
        batch_op.alter_column(
            "elevenlabs_api_key",
            existing_type=sa.String(700),
            type_=sa.String(),
            existing_nullable=True,
        )

    with op.batch_alter_table("tenant") as batch_op:
        batch_op.alter_column(
            "llm_api_key",
            existing_type=sa.String(700),
            type_=sa.String(500),
            existing_nullable=True,
        )
