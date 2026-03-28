"""
Testes TDD para SessionManager (session.py).

SessionManager e puro Python sem dependencias externas — totalmente testavel.
"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage


class TestSessionManagerGet:
    def test_returns_empty_state_for_new_session(self):
        """Sessao inexistente deve retornar estado vazio padrao."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = sm.get("nova-sessao")
        assert state == {"messages": [], "summary": ""}

    def test_returns_stored_state_for_existing_session(self):
        """Sessao existente deve retornar o estado armazenado."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = {"messages": [HumanMessage(content="oi")], "summary": "resumo"}
        sm.update("sessao-1", state)
        assert sm.get("sessao-1") == state

    def test_empty_state_has_messages_list(self):
        """Estado vazio deve ter campo messages como lista."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = sm.get("qualquer")
        assert isinstance(state["messages"], list)

    def test_empty_state_has_empty_summary(self):
        """Estado vazio deve ter campo summary como string vazia."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = sm.get("qualquer")
        assert state["summary"] == ""


class TestSessionManagerUpdate:
    def test_update_stores_state(self):
        """update() deve armazenar o estado para o session_id dado."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = {"messages": [], "summary": "teste"}
        sm.update("sessao-1", state)
        assert sm.get("sessao-1") == state

    def test_update_overwrites_existing_state(self):
        """Segunda chamada de update() deve sobrescrever o estado anterior."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("s", {"messages": [], "summary": "antigo"})
        sm.update("s", {"messages": [], "summary": "novo"})
        assert sm.get("s")["summary"] == "novo"

    def test_different_sessions_are_independent(self):
        """Sessoes diferentes nao devem interferir entre si."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("a", {"messages": [], "summary": "sessao A"})
        sm.update("b", {"messages": [], "summary": "sessao B"})
        assert sm.get("a")["summary"] == "sessao A"
        assert sm.get("b")["summary"] == "sessao B"


class TestSessionManagerDelete:
    def test_delete_removes_session(self):
        """delete() deve remover a sessao do armazenamento."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("para-deletar", {"messages": [], "summary": ""})
        sm.delete("para-deletar")
        assert sm.get("para-deletar") == {"messages": [], "summary": ""}

    def test_delete_existing_returns_true(self):
        """delete() de sessao existente deve retornar True."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("existe", {"messages": [], "summary": ""})
        result = sm.delete("existe")
        assert result is True

    def test_delete_nonexistent_returns_false(self):
        """delete() de sessao inexistente deve retornar False."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        result = sm.delete("nao-existe")
        assert result is False


class TestSessionManagerHas:
    def test_has_returns_false_for_new_session(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        assert sm.has("nova") is False

    def test_has_returns_true_after_update(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("existe", {"messages": [], "summary": ""})
        assert sm.has("existe") is True

    def test_has_returns_false_after_delete(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("s", {"messages": [], "summary": ""})
        sm.delete("s")
        assert sm.has("s") is False


class TestSessionManagerClear:
    def test_clear_removes_all_sessions(self):
        """clear() deve esvaziar todas as sessoes."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("a", {"messages": [], "summary": ""})
        sm.update("b", {"messages": [], "summary": ""})
        sm.clear()
        assert sm.has("a") is False
        assert sm.has("b") is False

    def test_get_after_clear_returns_empty_state(self):
        """Apos clear(), get() deve retornar estado vazio para qualquer sessao."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        sm.update("s", {"messages": [], "summary": "tinha algo"})
        sm.clear()
        assert sm.get("s") == {"messages": [], "summary": ""}
