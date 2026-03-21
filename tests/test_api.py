"""
Testes de integracao para a API FastAPI (api.py).

Adaptados para a Fase 5: usa dependency_overrides em vez de patch de modulo.
Cobre os mesmos cenarios da Fase 4 com o novo padrao de injecao de dependencia.
"""
import json
import os
import pytest
from unittest.mock import MagicMock
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


@pytest.fixture
def client():
    """TestClient com ChatService mockado via dependency_overrides."""
    from docagent.api import app
    from docagent.dependencies import get_chat_service

    mock_service = make_mock_service()
    app.dependency_overrides[get_chat_service] = lambda: mock_service

    yield TestClient(app), mock_service

    app.dependency_overrides.clear()


@pytest.fixture
def client_missing_session():
    """Client onde delete_session retorna False (sessao inexistente)."""
    from docagent.api import app
    from docagent.dependencies import get_chat_service

    mock_service = make_mock_service()
    mock_service.delete_session.return_value = False
    app.dependency_overrides[get_chat_service] = lambda: mock_service

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
        """O evento 'answer' deve conter o texto gerado pelo agente."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "O que e RAG?"})
        assert "RAG e uma tecnica de busca semantica." in response.text


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
    def test_session_id_passed_to_service(self, client):
        """O session_id deve ser repassado ao ChatService."""
        tc, mock_service = client
        tc.post("/chat", json={"question": "oi", "session_id": "minha-sessao"})
        mock_service.stream.assert_called_once_with("oi", "minha-sessao")

    def test_default_session_id_is_used_when_not_provided(self, client):
        """Sem session_id, deve usar 'default'."""
        tc, mock_service = client
        tc.post("/chat", json={"question": "oi"})
        mock_service.stream.assert_called_once_with("oi", "default")

    def test_same_session_id_calls_service_twice(self, client):
        """Duas requisicoes com o mesmo session_id devem chamar o servico duas vezes."""
        from unittest.mock import MagicMock
        tc, mock_service = client

        mock_service.stream.side_effect = [
            iter([
                f"data: {json.dumps({'type': 'answer', 'content': 'r1'})}\n\n",
                f"data: {json.dumps({'type': 'done'})}\n\n",
            ]),
            iter([
                f"data: {json.dumps({'type': 'answer', 'content': 'r2'})}\n\n",
                f"data: {json.dumps({'type': 'done'})}\n\n",
            ]),
        ]

        tc.post("/chat", json={"question": "primeira", "session_id": "sess-1"})
        tc.post("/chat", json={"question": "segunda", "session_id": "sess-1"})

        assert mock_service.stream.call_count == 2

    def test_delete_session_returns_200(self, client):
        """DELETE /session/{id} deve retornar 200 para sessao existente."""
        tc, _ = client
        response = tc.delete("/session/para-deletar")
        assert response.status_code == 200

    def test_delete_session_delegates_to_service(self, client):
        """DELETE deve chamar service.delete_session com o id correto."""
        tc, mock_service = client
        tc.delete("/session/minha-sessao")
        mock_service.delete_session.assert_called_once_with("minha-sessao")

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

        with (
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.OllamaEmbeddings"),
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.Chroma"),
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.api as api_module
            importlib.reload(api_module)

        assert os.getenv("LANGCHAIN_TRACING_V2") == "true"

    def test_tracing_disabled_without_api_key(self, monkeypatch):
        """Sem LANGSMITH_API_KEY, LANGCHAIN_TRACING_V2 nao deve ser 'true'."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        with (
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.OllamaEmbeddings"),
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.Chroma"),
            __import__("unittest.mock", fromlist=["patch"]).patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.api as api_module
            importlib.reload(api_module)

        assert os.getenv("LANGCHAIN_TRACING_V2") != "true"
