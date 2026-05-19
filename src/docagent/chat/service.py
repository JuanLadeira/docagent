"""
Fase 5 — ChatService: orquestra o agente e o gerenciador de sessao.

Camada de servico sem conhecimento de HTTP — testavel de forma isolada.
Fase 23: interface async para suportar RedisSessionManager.
"""
from typing import AsyncIterator

from docagent.agent.base import BaseAgent


class ChatService:
    def __init__(self, agent: BaseAgent, session_manager):
        self.agent = agent
        self.session_manager = session_manager

    async def astream(self, question: str, session_id: str) -> AsyncIterator[str]:
        """Executa o agente em modo streaming e atualiza a sessao ao fim."""
        state = await self.session_manager.get_async(session_id)
        for chunk in self.agent.stream(question, state):
            yield chunk
        if self.agent.last_state is not None:
            await self.session_manager.update_async(session_id, self.agent.last_state)

    async def delete_session_async(self, session_id: str) -> bool:
        """Remove uma sessao. Retorna True se existia, False caso contrario."""
        return await self.session_manager.delete_async(session_id)
