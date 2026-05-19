"""
Testes TDD para ChatService (services/chat_service.py).

ChatService orquestra BaseAgent + SessionManager sem conhecimento de HTTP.
Testado com mocks das duas dependencias.
Fase 23: interface async (astream, delete_session_async).
"""
import json
import pytest
from unittest.mock import MagicMock


def make_mock_agent(answer="resposta do agente"):
    """Cria um BaseAgent mockado que emite eventos SSE validos."""
    agent = MagicMock()
    agent.stream.return_value = iter([
        f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n",
        f"data: {json.dumps({'type': 'done'})}\n\n",
    ])
    agent.last_state = {"messages": [], "summary": ""}
    return agent


def make_mock_sessions():
    """Cria um InMemorySessionManager real para testes."""
    from docagent.chat.session import InMemorySessionManager
    return InMemorySessionManager()


class TestChatServiceStream:
    @pytest.mark.asyncio
    async def test_stream_yields_events_from_agent(self):
        """astream() deve repassar os eventos do agente para o chamador."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent("resposta teste")
        service = ChatService(agent, make_mock_sessions())

        events = []
        async for chunk in service.astream("pergunta", "sessao-1"):
            events.append(chunk)
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_stream_contains_done_event(self):
        """O stream deve terminar com evento done."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        service = ChatService(agent, make_mock_sessions())

        all_text = ""
        async for chunk in service.astream("pergunta", "s"):
            all_text += chunk
        assert "done" in all_text

    @pytest.mark.asyncio
    async def test_stream_calls_agent_with_question(self):
        """astream() deve chamar agent.stream com a pergunta correta."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        service = ChatService(agent, make_mock_sessions())

        async for _ in service.astream("minha pergunta", "s"):
            pass

        agent.stream.assert_called_once()
        call_args = agent.stream.call_args
        assert call_args[0][0] == "minha pergunta"

    @pytest.mark.asyncio
    async def test_stream_passes_existing_session_state_to_agent(self):
        """astream() deve passar o estado da sessao existente para o agente."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        sessions = make_mock_sessions()
        existing_state = {"messages": [], "summary": "historico anterior"}
        await sessions.update_async("s", existing_state)

        service = ChatService(agent, sessions)
        async for _ in service.astream("pergunta", "s"):
            pass

        call_kwargs = agent.stream.call_args[1]
        passed_state = call_kwargs.get("state") or agent.stream.call_args[0][1]
        assert passed_state["summary"] == "historico anterior"

    @pytest.mark.asyncio
    async def test_stream_updates_session_after_completion(self):
        """Apos o stream, a sessao deve ser atualizada com o estado final."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        agent.last_state = {"messages": [], "summary": "novo resumo"}
        sessions = make_mock_sessions()

        service = ChatService(agent, sessions)
        async for _ in service.astream("pergunta", "minha-sessao"):
            pass

        # A sessão deve conter o estado atualizado
        state = await sessions.get_async("minha-sessao")
        assert state["summary"] == "novo resumo"


class TestChatServiceDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_existing_session_returns_true(self):
        """delete_session_async() de sessao existente deve retornar True."""
        from docagent.chat.service import ChatService

        sessions = make_mock_sessions()
        await sessions.update_async("existe", {"messages": [], "summary": ""})

        service = ChatService(MagicMock(), sessions)
        result = await service.delete_session_async("existe")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_returns_false(self):
        """delete_session_async() de sessao inexistente deve retornar False."""
        from docagent.chat.service import ChatService

        service = ChatService(MagicMock(), make_mock_sessions())
        result = await service.delete_session_async("nao-existe")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_session_from_manager(self):
        """Apos delete_session_async(), o estado deve ser vazio."""
        from docagent.chat.service import ChatService

        sessions = make_mock_sessions()
        await sessions.update_async("s", {"messages": [], "summary": ""})

        service = ChatService(MagicMock(), sessions)
        await service.delete_session_async("s")

        state = await sessions.get_async("s")
        assert state == {"messages": [], "summary": ""}
