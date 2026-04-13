"""
Script de re-encriptação de secrets — Fase 21b.

Converte valores em plaintext existentes no banco para o formato criptografado
com Fernet. Deve ser executado UMA VEZ após configurar ENCRYPTION_KEY e rodar
a migração n4o5p6q7r8s9.

Uso:
    ENCRYPTION_KEY=<sua_chave> uv run python alembic/scripts/reencrypt_secrets.py

Idempotente: valores já criptografados (prefixo "gAAAAA") são ignorados.
"""
import asyncio
import logging
import os
import sys

# Garante que o pacote docagent esteja no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)


async def reencrypt():
    from docagent.crypto import encrypt, is_encrypted

    db_url = os.getenv("DOCAGENT_DB_URL", "sqlite+aiosqlite:///./docagent.db")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        total = 0

        # ── tenant.llm_api_key ────────────────────────────────────────────────
        result = await db.execute(
            text("SELECT id, llm_api_key FROM tenant WHERE llm_api_key IS NOT NULL")
        )
        rows = result.fetchall()
        for row_id, value in rows:
            if not is_encrypted(value):
                await db.execute(
                    text("UPDATE tenant SET llm_api_key = :v WHERE id = :id"),
                    {"v": encrypt(value), "id": row_id},
                )
                total += 1
                _log.info("tenant.id=%d llm_api_key re-criptografada", row_id)

        # ── audio_config.elevenlabs_api_key ───────────────────────────────────
        result = await db.execute(
            text(
                "SELECT id, elevenlabs_api_key FROM audio_config "
                "WHERE elevenlabs_api_key IS NOT NULL"
            )
        )
        rows = result.fetchall()
        for row_id, value in rows:
            if not is_encrypted(value):
                await db.execute(
                    text(
                        "UPDATE audio_config SET elevenlabs_api_key = :v WHERE id = :id"
                    ),
                    {"v": encrypt(value), "id": row_id},
                )
                total += 1
                _log.info("audio_config.id=%d elevenlabs_api_key re-criptografada", row_id)

        # ── telegram_instancia.bot_token ──────────────────────────────────────
        result = await db.execute(
            text("SELECT id, bot_token FROM telegram_instancia WHERE bot_token IS NOT NULL")
        )
        rows = result.fetchall()
        for row_id, value in rows:
            if not is_encrypted(value):
                await db.execute(
                    text(
                        "UPDATE telegram_instancia SET bot_token = :v WHERE id = :id"
                    ),
                    {"v": encrypt(value), "id": row_id},
                )
                total += 1
                _log.info("telegram_instancia.id=%d bot_token re-criptografado", row_id)

        await db.commit()
        _log.info("Re-encriptação concluída. %d valores atualizados.", total)

    await engine.dispose()


if __name__ == "__main__":
    if not os.getenv("ENCRYPTION_KEY"):
        _log.error("ENCRYPTION_KEY não configurada. Abortando.")
        sys.exit(1)
    asyncio.run(reencrypt())
