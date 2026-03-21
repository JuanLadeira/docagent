"""
Testes TDD para a API FastAPI (api.py).

Escritos ANTES da implementacao — guiam o desenvolvimento.
Todos devem falhar inicialmente e passar apos a implementacao.

Cobre:
- GET /health
- POST /chat (SSE streaming)
- DELETE /session/{session_id}
- Gerenciamento de sessao
- Formato SSE
- Configuracao do LangSmith
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, AIMessage


# ---------------------------------------------------------------------------
# Fixture: client com agente mockado
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_graph():
    """Grafo mockado que retorna uma resposta simples sem chamar o Ollama."""
    graph = MagicMock()
    graph.stream.return_value = iter([
        {
            "messages": [
                HumanMessage(content="O que e RAG?"),
                AIMessage(content="RAG e uma tecnica de busca semantica."),
            ],
            "summary": "",
        }
    ])
    return graph


@pytest.fixture
def client(mock_graph):
    """TestClient com sessoes e grafo resetados a cada teste."""
    with (
        patch("docagent.tools.OllamaEmbeddings"),
        patch("docagent.tools.Chroma"),
        patch("docagent.tools.DuckDuckGoSearchRun"),
        patch("docagent.api.build_graph", return_value=mock_graph),
    ):
        from docagent.api import app, sessions
        sessions.clear()
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_status_ok(self, client):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_missing_question_returns_422(self, client):
        """FastAPI deve rejeitar request sem o campo obrigatorio 'question'."""
        response = client.post("/chat", json={})
        assert response.status_code == 422

    def test_empty_question_returns_422(self, client):
        """Pergunta vazia deve ser rejeitada."""
        response = client.post("/chat", json={"question": ""})
        assert response.status_code == 422

    def test_valid_question_returns_200(self, client):
        response = client.post("/chat", json={"question": "O que e RAG?"})
        assert response.status_code == 200

    def test_response_content_type_is_event_stream(self, client):
        """Resposta deve ser SSE — content-type text/event-stream."""
        response = client.post("/chat", json={"question": "O que e RAG?"})
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_contains_done_event(self, client):
        """O stream deve sempre terminar com um evento 'done'."""
        response = client.post("/chat", json={"question": "O que e RAG?"})
        assert "done" in response.text

    def test_stream_contains_answer_event(self, client):
        """O stream deve conter um evento com a resposta final do agente."""
        response = client.post("/chat", json={"question": "O que e RAG?"})
        assert "answer" in response.text

    def test_stream_answer_contains_agent_response(self, client):
        """O evento 'answer' deve conter o texto gerado pelo agente."""
        response = client.post("/chat", json={"question": "O que e RAG?"})
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
        response = client.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        assert len(events) > 0
        for event in events:
            assert "type" in event, f"Evento sem campo 'type': {event}"

    def test_last_event_is_done(self, client):
        """O ultimo evento deve ser do tipo 'done'."""
        response = client.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        assert events[-1]["type"] == "done"

    def test_answer_event_has_content_field(self, client):
        """O evento 'answer' deve ter o campo 'content' com a resposta."""
        response = client.post("/chat", json={"question": "teste"})
        events = self._parse_sse_events(response.text)
        answer_events = [e for e in events if e["type"] == "answer"]
        assert len(answer_events) == 1
        assert "content" in answer_events[0]


# ---------------------------------------------------------------------------
# Gerenciamento de sessao
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_session_created_on_first_request(self, client):
        """A primeira requisicao com um session_id deve criar a sessao."""
        from docagent.api import sessions
        assert "minha-sessao" not in sessions

        client.post("/chat", json={"question": "oi", "session_id": "minha-sessao"})

        assert "minha-sessao" in sessions

    def test_default_session_id_is_used_when_not_provided(self, client):
        """Sem session_id, deve usar 'default'."""
        from docagent.api import sessions
        client.post("/chat", json={"question": "oi"})
        assert "default" in sessions

    def test_same_session_id_reuses_existing_state(self, client, mock_graph):
        """Duas requisicoes com o mesmo session_id devem compartilhar o estado."""
        from docagent.api import sessions

        client.post("/chat", json={"question": "primeira", "session_id": "sess-1"})
        state_after_first = sessions.get("sess-1")

        client.post("/chat", json={"question": "segunda", "session_id": "sess-1"})
        state_after_second = sessions.get("sess-1")

        # O grafo deve ter sido chamado duas vezes com a mesma sessao
        assert mock_graph.stream.call_count == 2

        # Estado deve existir apos ambas as chamadas
        assert state_after_first is not None
        assert state_after_second is not None

    def test_delete_session_returns_200(self, client):
        """DELETE /session/{id} deve retornar 200."""
        client.post("/chat", json={"question": "oi", "session_id": "para-deletar"})
        response = client.delete("/session/para-deletar")
        assert response.status_code == 200

    def test_delete_session_clears_state(self, client):
        """Apos DELETE, a sessao nao deve mais existir."""
        from docagent.api import sessions
        client.post("/chat", json={"question": "oi", "session_id": "para-deletar"})
        assert "para-deletar" in sessions

        client.delete("/session/para-deletar")
        assert "para-deletar" not in sessions

    def test_delete_nonexistent_session_returns_404(self, client):
        """Deletar sessao inexistente deve retornar 404."""
        response = client.delete("/session/nao-existe")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Configuracao LangSmith
# ---------------------------------------------------------------------------

class TestLangSmithConfig:
    def test_tracing_enabled_when_api_key_present(self, monkeypatch):
        """LANGCHAIN_TRACING_V2 deve ser 'true' quando LANGSMITH_API_KEY estiver definida."""
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_fake_key")

        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
            patch("docagent.api.build_graph", return_value=MagicMock()),
        ):
            import importlib
            import docagent.api as api_module
            importlib.reload(api_module)

        import os
        assert os.getenv("LANGCHAIN_TRACING_V2") == "true"

    def test_tracing_disabled_without_api_key(self, monkeypatch):
        """Sem LANGSMITH_API_KEY, LANGCHAIN_TRACING_V2 nao deve ser 'true'."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
            patch("docagent.api.build_graph", return_value=MagicMock()),
        ):
            import importlib
            import docagent.api as api_module
            importlib.reload(api_module)

        import os
        assert os.getenv("LANGCHAIN_TRACING_V2") != "true"
