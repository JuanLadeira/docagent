"""
Testes TDD para os routers FastAPI (routers/chat.py).

Usa app.dependency_overrides para substituir as dependencias reais
por mocks — padrao recomendado pelo FastAPI para testes.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


def make_mock_service(answer="resposta mock"):
    """ChatService mockado que emite SSE valido."""
    service = MagicMock()

    _chunks = [
        f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n",
        f"data: {json.dumps({'type': 'done'})}\n\n",
    ]

    async def _astream(*args, **kwargs):
        for chunk in _chunks:
            yield chunk

    service.astream = _astream
    service.delete_session_async = AsyncMock(return_value=True)
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


def _mock_session_manager(delete_returns=True):
    sm = MagicMock()
    sm.get_async = AsyncMock(return_value={"messages": [], "summary": ""})
    sm.update_async = AsyncMock()
    sm.delete_async = AsyncMock(return_value=delete_returns)
    return sm


def _setup_overrides(app, session_delete_returns=True):
    from docagent.dependencies import get_session_manager
    from docagent.agente.services import get_agente_service
    from docagent.mcp_server.services import get_mcp_service
    from docagent.auth.current_user import get_current_user
    from unittest.mock import MagicMock
    mock_user = MagicMock(id=1, tenant_id=1, username="owner")
    app.dependency_overrides[get_agente_service] = lambda: _mock_agente_service()
    app.dependency_overrides[get_mcp_service] = lambda: _mock_mcp_service()
    app.dependency_overrides[get_session_manager] = lambda: _mock_session_manager(session_delete_returns)
    app.dependency_overrides[get_current_user] = lambda: mock_user


@pytest.fixture
def client():
    """
    TestClient com dependencias sobrescritas via dependency_overrides + patch.
    """
    from unittest.mock import patch
    from docagent.api import app

    mock_service = make_mock_service()
    _setup_overrides(app)

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


@pytest.fixture
def client_with_missing_session():
    """Client onde SessionManager.delete retorna False (sessao inexistente)."""
    from unittest.mock import patch
    from docagent.api import app

    mock_service = make_mock_service()
    _setup_overrides(app, session_delete_returns=False)
    mock_service.delete_session_async = AsyncMock(return_value=False)

    mock_llm = MagicMock()
    mock_conversa = MagicMock(id=1, titulo=None)
    mock_conversa_svc = MagicMock()
    mock_conversa_svc.return_value.criar = AsyncMock(return_value=mock_conversa)
    mock_conversa_svc.return_value.salvar_mensagem = AsyncMock()
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
        yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthRouter:
    def test_returns_200(self, client):
        tc, _ = client
        assert tc.get("/health").status_code == 200

    def test_returns_status_ok(self, client):
        tc, _ = client
        assert tc.get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

class TestChatRouter:
    def test_missing_question_returns_422(self, client):
        tc, _ = client
        assert tc.post("/chat", json={}).status_code == 422

    def test_empty_question_returns_422(self, client):
        tc, _ = client
        assert tc.post("/chat", json={"question": ""}).status_code == 422

    def test_valid_question_returns_200(self, client):
        tc, _ = client
        assert tc.post("/chat", json={"question": "pergunta"}).status_code == 200

    def test_response_is_event_stream(self, client):
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_contains_done_event(self, client):
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert "done" in response.text

    def test_stream_contains_answer(self, client):
        """O stream deve conter algum evento com type='answer' ou 'done'."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert "type" in response.text


# ---------------------------------------------------------------------------
# DELETE /session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionRouter:
    def test_delete_existing_session_returns_200(self, client):
        tc, _ = client
        assert tc.delete("/session/minha-sessao").status_code == 200

    def test_delete_nonexistent_session_returns_404(self, client_with_missing_session):
        assert client_with_missing_session.delete("/session/nao-existe").status_code == 404

    def test_delete_response_contains_session_id(self, client):
        tc, _ = client
        response = tc.delete("/session/minha-sessao")
        assert response.json()["session_id"] == "minha-sessao"
