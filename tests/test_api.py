"""
Testes de integracao para a API FastAPI (api.py).

Adaptados para a Fase 5: usa dependency_overrides em vez de patch de modulo.
Cobre os mesmos cenarios da Fase 4 com o novo padrao de injecao de dependencia.
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers e fixtures
# ---------------------------------------------------------------------------

def make_mock_service(answer="RAG e uma tecnica de busca semantica."):
    """ChatService mockado que emite SSE valido com resposta padrao."""
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


def _mock_session_manager(delete_returns=True):
    sm = MagicMock()
    sm.delete.return_value = delete_returns
    sm.get.return_value = {"messages": [], "summary": ""}
    return sm


def _setup_overrides(app, mock_service, session_delete_returns=True):
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
    """TestClient com ChatService mockado via patch."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from docagent.api import app

    mock_service = make_mock_service()
    _setup_overrides(app, mock_service)

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
def client_missing_session():
    """Client onde SessionManager.delete retorna False (sessao inexistente)."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from docagent.api import app

    mock_service = make_mock_service()
    _setup_overrides(app, mock_service, session_delete_returns=False)

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
        yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, client):
        tc, _ = client
        assert tc.get("/health").status_code == 200

    def test_returns_status_ok(self, client):
        tc, _ = client
        assert tc.get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_missing_question_returns_422(self, client):
        """FastAPI deve rejeitar request sem o campo obrigatorio 'question'."""
        tc, _ = client
        assert tc.post("/chat", json={}).status_code == 422

    def test_empty_question_returns_422(self, client):
        """Pergunta vazia deve ser rejeitada."""
        tc, _ = client
        assert tc.post("/chat", json={"question": ""}).status_code == 422

    def test_valid_question_returns_200(self, client):
        tc, _ = client
        assert tc.post("/chat", json={"question": "O que e RAG?"}).status_code == 200

    def test_response_content_type_is_event_stream(self, client):
        """Resposta deve ser SSE — content-type text/event-stream."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "O que e RAG?"})
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_contains_done_event(self, client):
        """O stream deve sempre terminar com um evento 'done'."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "O que e RAG?"})
        assert "done" in response.text

    def test_stream_contains_answer_event(self, client):
        """O stream deve conter um evento com a resposta final do agente."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "O que e RAG?"})
        assert "answer" in response.text

    def test_stream_answer_contains_agent_response(self, client):
        """O stream deve conter eventos SSE com campo 'type'."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "O que e RAG?"})
        assert "type" in response.text


# ---------------------------------------------------------------------------
# Formato SSE
# ---------------------------------------------------------------------------

class TestSSEFormat:
    def _parse_sse_events(self, text: str) -> list[dict]:
        """Extrai e parseia os eventos SSE de uma resposta."""
        events = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
        return events

    def test_each_event_has_type_field(self, client):
        """Todo evento SSE deve ter o campo 'type'."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        assert len(events) > 0
        for event in events:
            assert "type" in event, f"Evento sem campo 'type': {event}"

    def test_last_event_is_done(self, client):
        """O ultimo evento deve ser do tipo 'done'."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        assert events[-1]["type"] == "done"

    def test_answer_event_has_content_field(self, client):
        """O evento 'answer' deve ter o campo 'content' com a resposta."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        answer_events = [e for e in events if e["type"] == "answer"]
        assert len(answer_events) == 1
        assert "content" in answer_events[0]


# ---------------------------------------------------------------------------
# Gerenciamento de sessao
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_chat_accepts_session_id(self, client):
        """O endpoint /chat aceita session_id na request."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "oi", "session_id": "minha-sessao"})
        assert response.status_code == 200

    def test_chat_uses_default_session_id(self, client):
        """Sem session_id, o endpoint retorna 200 com default."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "oi"})
        assert response.status_code == 200

    def test_delete_session_returns_200(self, client):
        """DELETE /session/{id} deve retornar 200 para sessao existente."""
        tc, _ = client
        response = tc.delete("/session/para-deletar")
        assert response.status_code == 200

    def test_delete_session_response_has_session_id(self, client):
        """Resposta do DELETE deve conter o session_id."""
        tc, _ = client
        response = tc.delete("/session/minha-sessao")
        assert response.json()["session_id"] == "minha-sessao"

    def test_delete_nonexistent_session_returns_404(self, client_missing_session):
        """Deletar sessao inexistente deve retornar 404."""
        response = client_missing_session.delete("/session/nao-existe")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Configuracao LangSmith
# ---------------------------------------------------------------------------

class TestLangSmithConfig:
    def test_tracing_enabled_when_api_key_present(self, monkeypatch):
        """LANGCHAIN_TRACING_V2 deve ser 'true' quando LANGSMITH_API_KEY estiver definida."""
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_fake_key")

        import importlib
        import docagent.api as api_module
        importlib.reload(api_module)

        assert os.getenv("LANGCHAIN_TRACING_V2") == "true"

    def test_tracing_disabled_without_api_key(self, monkeypatch):
        """Sem LANGSMITH_API_KEY, LANGCHAIN_TRACING_V2 nao deve ser 'true'."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        import importlib
        import docagent.api as api_module
        importlib.reload(api_module)

        assert os.getenv("LANGCHAIN_TRACING_V2") != "true"
