"""
Testes TDD para SessionManager (session.py).

Fase 23: interface async (get_async, update_async, delete_async).
SessionManager é alias para InMemorySessionManager.
"""
import pytest
from langchain_core.messages import HumanMessage


class TestSessionManagerGet:
    @pytest.mark.asyncio
    async def test_returns_empty_state_for_new_session(self):
        """Sessao inexistente deve retornar estado vazio padrao."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = await sm.get_async("nova-sessao")
        assert state == {"messages": [], "summary": ""}

    @pytest.mark.asyncio
    async def test_returns_stored_state_for_existing_session(self):
        """Sessao existente deve retornar o estado armazenado."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = {"messages": [HumanMessage(content="oi")], "summary": "resumo"}
        await sm.update_async("sessao-1", state)
        assert await sm.get_async("sessao-1") == state

    @pytest.mark.asyncio
    async def test_empty_state_has_messages_list(self):
        """Estado vazio deve ter campo messages como lista."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = await sm.get_async("qualquer")
        assert isinstance(state["messages"], list)

    @pytest.mark.asyncio
    async def test_empty_state_has_empty_summary(self):
        """Estado vazio deve ter campo summary como string vazia."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = await sm.get_async("qualquer")
        assert state["summary"] == ""


class TestSessionManagerUpdate:
    @pytest.mark.asyncio
    async def test_update_stores_state(self):
        """update_async() deve armazenar o estado para o session_id dado."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        state = {"messages": [], "summary": "teste"}
        await sm.update_async("sessao-1", state)
        assert await sm.get_async("sessao-1") == state

    @pytest.mark.asyncio
    async def test_update_overwrites_existing_state(self):
        """Segunda chamada de update_async() deve sobrescrever o estado anterior."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("s", {"messages": [], "summary": "antigo"})
        await sm.update_async("s", {"messages": [], "summary": "novo"})
        assert (await sm.get_async("s"))["summary"] == "novo"

    @pytest.mark.asyncio
    async def test_different_sessions_are_independent(self):
        """Sessoes diferentes nao devem interferir entre si."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("a", {"messages": [], "summary": "sessao A"})
        await sm.update_async("b", {"messages": [], "summary": "sessao B"})
        assert (await sm.get_async("a"))["summary"] == "sessao A"
        assert (await sm.get_async("b"))["summary"] == "sessao B"


class TestSessionManagerDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_session(self):
        """delete_async() deve remover a sessao do armazenamento."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("para-deletar", {"messages": [], "summary": ""})
        await sm.delete_async("para-deletar")
        assert await sm.get_async("para-deletar") == {"messages": [], "summary": ""}

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self):
        """delete_async() de sessao existente deve retornar True."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("existe", {"messages": [], "summary": ""})
        result = await sm.delete_async("existe")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self):
        """delete_async() de sessao inexistente deve retornar False."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        result = await sm.delete_async("nao-existe")
        assert result is False


class TestSessionManagerHas:
    def test_has_returns_false_for_new_session(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        assert sm.has("nova") is False

    @pytest.mark.asyncio
    async def test_has_returns_true_after_update(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("existe", {"messages": [], "summary": ""})
        assert sm.has("existe") is True

    @pytest.mark.asyncio
    async def test_has_returns_false_after_delete(self):
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("s", {"messages": [], "summary": ""})
        await sm.delete_async("s")
        assert sm.has("s") is False


class TestSessionManagerClear:
    @pytest.mark.asyncio
    async def test_clear_removes_all_sessions(self):
        """clear() deve esvaziar todas as sessoes."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("a", {"messages": [], "summary": ""})
        await sm.update_async("b", {"messages": [], "summary": ""})
        sm.clear()
        assert sm.has("a") is False
        assert sm.has("b") is False

    @pytest.mark.asyncio
    async def test_get_after_clear_returns_empty_state(self):
        """Apos clear(), get_async() deve retornar estado vazio para qualquer sessao."""
        from docagent.chat.session import SessionManager
        sm = SessionManager()
        await sm.update_async("s", {"messages": [], "summary": "tinha algo"})
        sm.clear()
        assert await sm.get_async("s") == {"messages": [], "summary": ""}
