"""
Fase 23 — Factory para conexão assíncrona com Redis.

Retorna None se REDIS_URL não estiver configurada, permitindo
que todos os componentes funcionem em modo in-memory (dev/testes).
"""
import logging

from docagent.settings import Settings

log = logging.getLogger(__name__)


def get_redis_client():
    """
    Cria e retorna um redis.asyncio.Redis conectado a REDIS_URL.
    Retorna None se REDIS_URL estiver vazia.
    """
    if not Settings.REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            Settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # precisamos de bytes para pickle
        )
        log.info("Redis client criado: %s", Settings.REDIS_URL)
        return client
    except Exception as exc:
        log.error("Falha ao criar Redis client: %s", exc)
        return None
