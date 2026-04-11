"""
Testes TDD para as evolucoes do router de chat na Fase 6.

Cobre: agent_id no ChatRequest, selecao de agente por sessao,
e validacao do campo agent_id contra o AGENT_REGISTRY.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


def make_mock_service(answer="resposta mock"):
    service = MagicMock()
    service.stream.return_value = iter([
        f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n",
        f"data: {json.dumps({'type': 'done'})}\n\n",
    ])
    service.delete_session.return_value = True
    return service


def _mock_agente_service():
    svc = MagicMock()
    agente = MagicMock(id=1, nome="Agent", skill_names=[], ativo=True, system_prompt=None, descricao="")
    svc.get_by_id = AsyncMock(return_value=agente)
    return svc


def _mock_mcp_service():
    svc = MagicMock()
    svc.get_all = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def client():
    from unittest.mock import patch, MagicMock, AsyncMock
    from docagent.api import app
    from docagent.agente.services import get_agente_service
    from docagent.mcp_server.services import get_mcp_service
    from docagent.auth.current_user import get_current_user

    mock_user = MagicMock(id=1, tenant_id=1, username="owner")
    mock_service = make_mock_service()
    app.dependency_overrides[get_agente_service] = lambda: _mock_agente_service()
    app.dependency_overrides[get_mcp_service] = lambda: _mock_mcp_service()
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_llm = MagicMock()
    mock_conversa = MagicMock(id=1, titulo=None)
    mock_conversa_svc = MagicMock()
    mock_conversa_svc.return_value.criar = AsyncMock(return_value=mock_conversa)
    mock_conversa_svc.return_value.get_by_id = AsyncMock(return_value=mock_conversa)
    mock_conversa_svc.return_value.carregar_historico = AsyncMock(return_value=[])
    mock_conversa_svc.return_value.salvar_mensagem = AsyncMock()
    mock_conversa_svc.return_value.gerar_titulo = AsyncMock()
    from docagent.database import get_db
    app.dependency_overrides[get_db] = lambda: (x for x in [MagicMock()])
    with patch("docagent.chat.router.ChatService", return_value=mock_service), \
         patch("docagent.chat.router.ConfigurableAgent") as MockCA, \
         patch("docagent.chat.router.get_tenant_llm", new=AsyncMock(return_value=mock_llm)), \
         patch("docagent.chat.router.ConversaService", mock_conversa_svc), \
         patch("docagent.chat.router.AsyncSessionLocal") as mock_sl:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_db
        MockCA.return_value.build.return_value = MagicMock()
        yield TestClient(app), mock_service

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema ChatRequest — campo agent_id
# ---------------------------------------------------------------------------

class TestChatRequestAgentId:
    def test_default_agent_id_is_1(self):
        """Agentes agora vêm do banco (ID numérico); default é "1"."""
        from docagent.chat.schemas import ChatRequest
        req = ChatRequest(question="teste")
        assert req.agent_id == "1"

    def test_accepts_custom_agent_id(self):
        from docagent.chat.schemas import ChatRequest
        req = ChatRequest(question="teste", agent_id="2")
        assert req.agent_id == "2"

    def test_agent_id_is_string(self):
        """agent_id é string livre; validação ocorre no router (int conversion)."""
        from docagent.chat.schemas import ChatRequest
        req = ChatRequest(question="teste", agent_id="42")
        assert req.agent_id == "42"


# ---------------------------------------------------------------------------
# Endpoint POST /chat com agent_id
# ---------------------------------------------------------------------------

class TestChatEndpointAgentId:
    def test_valid_numeric_agent_id_returns_200(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "1",
        })
        assert response.status_code == 200

    def test_missing_agent_id_uses_default(self, client):
        """Sem agent_id, usa "1" como default e retorna 200."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert response.status_code == 200

    def test_non_numeric_agent_id_returns_400(self, client):
        """ID não numérico (ex: 'doc-analyst') retorna 400 (não é inteiro)."""
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "agente-que-nao-existe",
        })
        assert response.status_code == 400

    def test_stream_still_works_with_agent_id(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "1",
        })
        assert "done" in response.text
