"""
Testes TDD para os routers FastAPI (routers/chat.py).

Usa app.dependency_overrides para substituir as dependencias reais
por mocks — padrao recomendado pelo FastAPI para testes.
"""
import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def make_mock_service(answer="resposta mock"):
    """ChatService mockado que emite SSE valido."""
    service = MagicMock()
    service.stream.return_value = iter([
        f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n",
        f"data: {json.dumps({'type': 'done'})}\n\n",
    ])
    service.delete_session.return_value = True
    return service


@pytest.fixture
def client():
    """
    TestClient com dependencias sobrescritas via dependency_overrides.
    Este e o padrao recomendado pelo FastAPI — sem mocks de modulo.
    """
    from docagent.api import app
    from docagent.dependencies import get_chat_service

    mock_service = make_mock_service()
    app.dependency_overrides[get_chat_service] = lambda: mock_service

    yield TestClient(app), mock_service

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_missing_session():
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
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert "resposta mock" in response.text

    def test_delegates_to_chat_service(self, client):
        """O router deve delegar a logica ao ChatService injetado."""
        tc, mock_service = client
        tc.post("/chat", json={"question": "minha pergunta", "session_id": "s-1"})
        mock_service.stream.assert_called_once_with("minha pergunta", "s-1")

    def test_default_session_id_is_default(self, client):
        """Sem session_id, deve usar 'default'."""
        tc, mock_service = client
        tc.post("/chat", json={"question": "pergunta"})
        mock_service.stream.assert_called_once_with("pergunta", "default")


# ---------------------------------------------------------------------------
# DELETE /session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionRouter:
    def test_delete_existing_session_returns_200(self, client):
        tc, _ = client
        assert tc.delete("/session/minha-sessao").status_code == 200

    def test_delete_nonexistent_session_returns_404(self, client_with_missing_session):
        assert client_with_missing_session.delete("/session/nao-existe").status_code == 404

    def test_delete_delegates_to_service(self, client):
        tc, mock_service = client
        tc.delete("/session/s-1")
        mock_service.delete_session.assert_called_once_with("s-1")

    def test_delete_response_contains_session_id(self, client):
        tc, _ = client
        response = tc.delete("/session/minha-sessao")
        assert response.json()["session_id"] == "minha-sessao"
