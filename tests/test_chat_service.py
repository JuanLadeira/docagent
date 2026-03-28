"""
Testes TDD para ChatService (services/chat_service.py).

ChatService orquestra BaseAgent + SessionManager sem conhecimento de HTTP.
Testado com mocks das duas dependencias.
"""
import json
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
    """Cria um SessionManager mockado."""
    from docagent.chat.session import SessionManager
    sm = SessionManager()
    return sm


class TestChatServiceStream:
    def test_stream_yields_events_from_agent(self):
        """stream() deve repassar os eventos do agente para o chamador."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent("resposta teste")
        service = ChatService(agent, make_mock_sessions())

        events = list(service.stream("pergunta", "sessao-1"))
        assert len(events) > 0

    def test_stream_contains_done_event(self):
        """O stream deve terminar com evento done."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        service = ChatService(agent, make_mock_sessions())

        all_text = "".join(service.stream("pergunta", "s"))
        assert "done" in all_text

    def test_stream_calls_agent_with_question(self):
        """stream() deve chamar agent.stream com a pergunta correta."""
        from docagent.chat.service import ChatService

        agent = make_mock_agent()
        service = ChatService(agent, make_mock_sessions())

        list(service.stream("minha pergunta", "s"))

        agent.stream.assert_called_once()
        call_args = agent.stream.call_args
        assert call_args[0][0] == "minha pergunta"

    def test_stream_passes_existing_session_state_to_agent(self):
        """stream() deve passar o estado da sessao existente para o agente."""
        from docagent.chat.service import ChatService
        from docagent.chat.session import SessionManager

        agent = make_mock_agent()
        sessions = SessionManager()
        existing_state = {"messages": [], "summary": "historico anterior"}
        sessions.update("s", existing_state)

        service = ChatService(agent, sessions)
        list(service.stream("pergunta", "s"))

        call_kwargs = agent.stream.call_args[1]
        passed_state = call_kwargs.get("state") or agent.stream.call_args[0][1]
        assert passed_state["summary"] == "historico anterior"

    def test_stream_updates_session_after_completion(self):
        """Apos o stream, a sessao deve ser atualizada com o estado final."""
        from docagent.chat.service import ChatService
        from docagent.chat.session import SessionManager

        agent = make_mock_agent()
        agent.last_state = {"messages": [], "summary": "novo resumo"}
        sessions = SessionManager()

        service = ChatService(agent, sessions)
        list(service.stream("pergunta", "minha-sessao"))

        assert sessions.has("minha-sessao")


class TestChatServiceDeleteSession:
    def test_delete_existing_session_returns_true(self):
        """delete_session() de sessao existente deve retornar True."""
        from docagent.chat.service import ChatService
        from docagent.chat.session import SessionManager

        sessions = SessionManager()
        sessions.update("existe", {"messages": [], "summary": ""})

        service = ChatService(MagicMock(), sessions)
        result = service.delete_session("existe")

        assert result is True

    def test_delete_nonexistent_session_returns_false(self):
        """delete_session() de sessao inexistente deve retornar False."""
        from docagent.chat.service import ChatService
        from docagent.chat.session import SessionManager

        service = ChatService(MagicMock(), SessionManager())
        result = service.delete_session("nao-existe")

        assert result is False

    def test_delete_removes_session_from_manager(self):
        """Apos delete_session(), a sessao nao deve mais existir."""
        from docagent.chat.service import ChatService
        from docagent.chat.session import SessionManager

        sessions = SessionManager()
        sessions.update("s", {"messages": [], "summary": ""})

        service = ChatService(MagicMock(), sessions)
        service.delete_session("s")

        assert not sessions.has("s")
