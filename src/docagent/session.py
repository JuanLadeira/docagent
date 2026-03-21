"""
Fase 5 — SessionManager: gerencia o estado das sessoes de conversa.

Armazenamento em memoria (dict). Em producao, substituir por Redis.
"""


class SessionManager:
    """Gerencia estados de sessao em memoria."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get(self, session_id: str) -> dict:
        """Retorna o estado da sessao ou estado vazio se nao existir."""
        return self._sessions.get(session_id, {"messages": [], "summary": ""})

    def update(self, session_id: str, state: dict) -> None:
        """Armazena ou atualiza o estado de uma sessao."""
        self._sessions[session_id] = state

    def delete(self, session_id: str) -> bool:
        """Remove uma sessao. Retorna True se existia, False caso contrario."""
        return self._sessions.pop(session_id, None) is not None

    def has(self, session_id: str) -> bool:
        """Verifica se uma sessao existe."""
        return session_id in self._sessions

    def clear(self) -> None:
        """Remove todas as sessoes."""
        self._sessions.clear()
