"""
Fase 5 — ChatService: orquestra o agente e o gerenciador de sessao.

Camada de servico sem conhecimento de HTTP — testavel de forma isolada.
"""
from typing import Iterator

from docagent.agent.base import BaseAgent
from docagent.chat.session import SessionManager


class ChatService:
    def __init__(self, agent: BaseAgent, session_manager: SessionManager):
        self.agent = agent
        self.session_manager = session_manager

    def stream(self, question: str, session_id: str) -> Iterator[str]:
        """Executa o agente em modo streaming e atualiza a sessao ao fim."""
        state = self.session_manager.get(session_id)
        yield from self.agent.stream(question, state)
        if self.agent.last_state is not None:
            self.session_manager.update(session_id, self.agent.last_state)

    def delete_session(self, session_id: str) -> bool:
        """Remove uma sessao. Retorna True se existia, False caso contrario."""
        return self.session_manager.delete(session_id)
