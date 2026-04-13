"""
Fase 5 — SessionManager: gerencia o estado das sessoes de conversa.
Fase 23 — RedisSessionManager: versão distribuída via Redis.

Usa InMemorySessionManager quando REDIS_URL não está configurada.
"""
import pickle


class InMemorySessionManager:
    """Gerencia estados de sessao em memoria (single-worker)."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    async def get_async(self, session_id: str) -> dict:
        """Retorna o estado da sessao ou estado vazio se nao existir."""
        return self._sessions.get(session_id, {"messages": [], "summary": ""})

    async def update_async(self, session_id: str, state: dict) -> None:
        """Armazena ou atualiza o estado de uma sessao."""
        self._sessions[session_id] = state

    async def delete_async(self, session_id: str) -> bool:
        """Remove uma sessao. Retorna True se existia, False caso contrario."""
        return self._sessions.pop(session_id, None) is not None

    def has(self, session_id: str) -> bool:
        """Verifica se uma sessao existe."""
        return session_id in self._sessions

    def clear(self) -> None:
        """Remove todas as sessoes."""
        self._sessions.clear()


# Alias para compatibilidade
SessionManager = InMemorySessionManager


class RedisSessionManager:
    """Gerencia estados de sessao via Redis (multi-worker)."""

    def __init__(self, redis, ttl: int = 3600):
        self._r = redis
        self._ttl = ttl

    async def get_async(self, session_id: str) -> dict:
        data = await self._r.get(f"session:{session_id}")
        if data:
            return pickle.loads(data)
        return {"messages": [], "summary": ""}

    async def update_async(self, session_id: str, state: dict) -> None:
        await self._r.setex(f"session:{session_id}", self._ttl, pickle.dumps(state))

    async def delete_async(self, session_id: str) -> bool:
        return bool(await self._r.delete(f"session:{session_id}"))


def get_session_manager_instance(redis=None):
    """Factory: retorna RedisSessionManager se redis disponível, senão InMemory."""
    if redis is not None:
        return RedisSessionManager(redis)
    return InMemorySessionManager()
